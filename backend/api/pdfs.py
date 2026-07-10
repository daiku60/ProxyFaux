import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from django.conf import settings
from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.lib.colors import black
from reportlab.pdfgen import canvas

from api.models import CrewCard, Model, Upgrade

MM_TO_POINTS = 72 / 25.4
CARD_WIDTH_MM = 70
CARD_HEIGHT_MM = 120
CARD_WIDTH = CARD_WIDTH_MM * MM_TO_POINTS
CARD_HEIGHT = CARD_HEIGHT_MM * MM_TO_POINTS
SHEET_SIZES_MM = {
    "a4": (210, 297),
    "letter": (215.9, 279.4),
}

VARIANT_PATTERN = re.compile(r"\{([A-Z](?:\|[A-Z])*)\}")
TRAILING_VARIANT_PATTERN = re.compile(r"^(?P<name>.+?)\s+(?P<variant>[A-Z])$")
TRAILING_PARENTHETICAL_PATTERN = re.compile(r"^(?P<name>.+?)\s+\([^)]*\)$")


class PdfCompositionError(ValueError):
    pass


@dataclass(frozen=True)
class RequestedCard:
    raw_name: str
    card: Model | CrewCard | Upgrade
    variant: str | None = None
    language: str = "en"

    @property
    def model(self) -> Model | CrewCard | Upgrade:
        return self.card


@dataclass(frozen=True)
class PdfPlacement:
    source_path: Path
    page_indexes: tuple[int, int]


@dataclass(frozen=True)
class SheetLayout:
    page_width: float
    page_height: float
    left_right_margin: float
    top_bottom_margin: float


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def build_card_lookup(
    cards: list[Model | CrewCard | Upgrade],
) -> dict[str, Model | CrewCard | Upgrade]:
    lookup: dict[str, Model | CrewCard | Upgrade] = {}
    for card in cards:
        for candidate in iter_card_name_candidates(card):
            lookup.setdefault(normalize_name(candidate), card)
    return lookup


def iter_card_name_candidates(card: Model | CrewCard | Upgrade) -> list[str]:
    candidates: list[str] = []

    files = card.files if isinstance(card.files, dict) else {}
    versions = files.get("versions")
    if isinstance(versions, list):
        for version in versions:
            if isinstance(version, dict):
                display_name = version.get("displayName")
                if isinstance(display_name, str) and display_name.strip():
                    candidates.append(display_name.strip())

    name = getattr(card, "name", "")
    title = getattr(card, "title", "")
    if name and title:
        candidates.append(f"{name}, {title}")
        candidates.append(f"{name} {title}")
    if name:
        candidates.append(name)

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = normalize_name(candidate)
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(candidate)
    return deduped


def parse_requested_cards(
    text: str,
    cards: list[Model | CrewCard | Upgrade],
) -> list[RequestedCard]:
    lookup = build_card_lookup(cards)
    requested: list[RequestedCard] = []

    for raw_line in text.splitlines():
        cleaned_line = clean_input_line(raw_line)
        if not cleaned_line:
            continue

        resolved_line = resolve_requested_card(cleaned_line, lookup)
        if resolved_line is not None:
            requested.append(resolved_line)
            continue

        parts = [part.strip() for part in cleaned_line.split(",") if part.strip()]
        if len(parts) > 1:
            resolved_parts = [resolve_requested_card(part, lookup) for part in parts]
            if all(resolved_parts):
                requested.extend(
                    resolved_part
                    for resolved_part in resolved_parts
                    if resolved_part is not None
                )
                continue

    if not requested:
        raise PdfCompositionError("No model names were found in the provided text.")

    return requested


def clean_input_line(raw_line: str) -> str:
    line = raw_line.strip()
    if not line:
        return ""
    if line.startswith("(") and line.endswith(")"):
        return ""
    if line.endswith(":"):
        return ""

    return re.sub(r"^[\-\*\u2022]+\s*", "", line).strip()


def resolve_requested_card(
    raw_name: str,
    lookup: dict[str, Model | CrewCard | Upgrade],
) -> RequestedCard | None:
    normalized_name = normalize_name(raw_name)
    if not normalized_name:
        return None

    card = lookup.get(normalized_name)
    if card is not None:
        return RequestedCard(raw_name=raw_name, card=card)

    match = TRAILING_VARIANT_PATTERN.match(raw_name)
    if not match:
        return resolve_requested_card_without_parenthetical(raw_name, lookup)

    variant = match.group("variant")
    base_name = match.group("name").strip()
    card = lookup.get(normalize_name(base_name))
    if card is None:
        return resolve_requested_card_without_parenthetical(raw_name, lookup)

    return RequestedCard(raw_name=raw_name, card=card, variant=variant)


def resolve_requested_card_without_parenthetical(
    raw_name: str,
    lookup: dict[str, Model | CrewCard | Upgrade],
) -> RequestedCard | None:
    match = TRAILING_PARENTHETICAL_PATTERN.match(raw_name)
    if not match:
        return None

    stripped_name = match.group("name").strip()
    if stripped_name == raw_name:
        return None

    return resolve_requested_card(stripped_name, lookup)


def compose_model_pdf(
    text: str,
    *,
    border: bool = False,
    cut_lines: bool = False,
    sheet_size: str = "a4",
) -> bytes:
    requested_cards = parse_requested_cards(
        text,
        [
            *list(Model.objects.exclude(pdf="")),
            *list(CrewCard.objects.exclude(pdf="")),
            *list(Upgrade.objects.exclude(pdf="")),
        ],
    )
    placements = resolve_pdf_placements(requested_cards)
    return render_composed_pdf(
        placements,
        sheet_layout=build_sheet_layout(sheet_size),
        border=border,
        cut_lines=cut_lines,
    )


def compose_selected_cards_pdf(
    requested_cards: list[RequestedCard],
    *,
    border: bool = False,
    cut_lines: bool = False,
    sheet_size: str = "a4",
) -> bytes:
    placements = resolve_pdf_placements(requested_cards)
    return render_composed_pdf(
        placements,
        sheet_layout=build_sheet_layout(sheet_size),
        border=border,
        cut_lines=cut_lines,
    )


def resolve_pdf_placements(requested_cards: list[RequestedCard]) -> list[PdfPlacement]:
    counters: dict[int, int] = {}
    placements: list[PdfPlacement] = []

    for requested_card in requested_cards:
        pdf_path, variants = resolve_pdf_path_and_variants(
            requested_card.card.pdf,
            language=requested_card.language,
        )
        chosen_variant: str | None = None
        if variants:
            if requested_card.variant is not None:
                if requested_card.variant not in variants:
                    raise PdfCompositionError(
                        f"{requested_card.raw_name} requested variant {requested_card.variant}, "
                        f"but available variants are {', '.join(variants)}."
                    )
                chosen_variant = requested_card.variant
            else:
                current_index = counters.get(requested_card.card.pk or -1, 0)
                chosen_variant = variants[current_index % len(variants)]
                counters[requested_card.card.pk or -1] = current_index + 1

        resolved_path = build_variant_pdf_path(pdf_path, chosen_variant)
        if not resolved_path.exists():
            raise PdfCompositionError(
                f"Missing PDF for {requested_card.raw_name}: {resolved_path}"
            )

        reader = PdfReader(str(resolved_path))
        if len(reader.pages) < 2:
            raise PdfCompositionError(
                f"PDF for {requested_card.raw_name} must contain at least two pages."
            )

        placements.append(PdfPlacement(source_path=resolved_path, page_indexes=(0, 1)))

    return placements


def resolve_pdf_path_and_variants(
    pdf_value: str,
    *,
    language: str = "en",
) -> tuple[Path, list[str]]:
    pdf_root = get_pdf_root_for_language(language)
    raw_path = Path(pdf_value)
    resolved_path = normalize_pdf_storage_path(raw_path, pdf_root)
    match = VARIANT_PATTERN.search(resolved_path.name)
    if not match:
        return resolved_path, []

    variants = match.group(1).split("|")
    return resolved_path, variants


def normalize_pdf_storage_path(pdf_path: Path, pdf_root: Path) -> Path:
    if pdf_path.is_absolute():
        return pdf_path

    if path_starts_with_parts(pdf_path, pdf_root.parts):
        return pdf_path

    if pdf_path.parts and pdf_path.parts[0] == pdf_root.name:
        return pdf_root / Path(*pdf_path.parts[1:])

    return pdf_root / pdf_path


def get_pdf_root_for_language(language: str) -> Path:
    normalized_language = language.lower()
    if normalized_language not in {"en", "es"}:
        raise PdfCompositionError(
            f"Unsupported language `{language}`. Use `en` or `es`."
        )

    pdf_data_root = Path(getattr(settings, "PDF_DATA_ROOT", Path(settings.PDF_ROOT).parent))
    language_pdf_root = pdf_data_root / normalized_language / "pdfs"
    if language_pdf_root.exists():
        return language_pdf_root

    if normalized_language == "en":
        return Path(settings.PDF_ROOT)

    return language_pdf_root


def parse_requested_models(
    text: str,
    models: list[Model],
) -> list[RequestedCard]:
    return parse_requested_cards(text, models)


def path_starts_with_parts(path: Path, prefix_parts: tuple[str, ...]) -> bool:
    if len(path.parts) < len(prefix_parts):
        return False

    return path.parts[: len(prefix_parts)] == prefix_parts


def build_variant_pdf_path(path_with_pattern: Path, variant: str | None) -> Path:
    if variant is None:
        return path_with_pattern

    resolved_name = VARIANT_PATTERN.sub(variant, path_with_pattern.name)
    return path_with_pattern.with_name(resolved_name)


def build_sheet_layout(sheet_size: str) -> SheetLayout:
    try:
        page_width_mm, page_height_mm = SHEET_SIZES_MM[sheet_size.lower()]
    except KeyError as exc:
        raise PdfCompositionError(
            f"Unsupported sheet size `{sheet_size}`. Use `a4` or `letter`."
        ) from exc

    page_width = page_width_mm * MM_TO_POINTS
    page_height = page_height_mm * MM_TO_POINTS
    left_right_margin = ((page_width_mm - (CARD_WIDTH_MM * 2)) / 2) * MM_TO_POINTS
    top_bottom_margin = ((page_height_mm - (CARD_HEIGHT_MM * 2)) / 2) * MM_TO_POINTS
    return SheetLayout(
        page_width=page_width,
        page_height=page_height,
        left_right_margin=left_right_margin,
        top_bottom_margin=top_bottom_margin,
    )


def render_composed_pdf(
    placements: list[PdfPlacement],
    *,
    sheet_layout: SheetLayout,
    border: bool = False,
    cut_lines: bool = False,
) -> bytes:
    writer = PdfWriter()
    readers: list[PdfReader] = []

    for start_index in range(0, len(placements), 2):
        page_placements = placements[start_index : start_index + 2]
        output_page = writer.add_blank_page(
            width=sheet_layout.page_width,
            height=sheet_layout.page_height,
        )
        for row_index, placement in enumerate(page_placements):
            reader = PdfReader(str(placement.source_path))
            readers.append(reader)
            for column_index, page_index in enumerate(placement.page_indexes):
                source_page = reader.pages[page_index]
                place_page_on_sheet(
                    output_page,
                    source_page,
                    sheet_layout=sheet_layout,
                    row_index=row_index,
                    column_index=column_index,
                )

        overlay_page = build_overlay_page(
            len(page_placements),
            sheet_layout=sheet_layout,
            border=border,
            cut_lines=cut_lines,
        )
        if overlay_page is not None:
            output_page.merge_page(overlay_page)

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def place_page_on_sheet(
    output_page,
    source_page,
    *,
    sheet_layout: SheetLayout,
    row_index: int,
    column_index: int,
) -> None:
    source_width = float(source_page.mediabox.width)
    source_height = float(source_page.mediabox.height)
    scale = min(CARD_WIDTH / source_width, CARD_HEIGHT / source_height)

    x = sheet_layout.left_right_margin + (column_index * CARD_WIDTH)
    y = sheet_layout.page_height - sheet_layout.top_bottom_margin - ((row_index + 1) * CARD_HEIGHT)
    translate_x = x + ((CARD_WIDTH - (source_width * scale)) / 2)
    translate_y = y + ((CARD_HEIGHT - (source_height * scale)) / 2)

    transformation = Transformation().scale(scale).translate(translate_x, translate_y)
    output_page.merge_transformed_page(source_page, transformation)


def build_overlay_page(
    pair_count: int,
    *,
    sheet_layout: SheetLayout,
    border: bool = False,
    cut_lines: bool = False,
):
    if not border and not cut_lines:
        return None

    buffer = BytesIO()
    pdf_canvas = canvas.Canvas(buffer, pagesize=(sheet_layout.page_width, sheet_layout.page_height))
    pdf_canvas.setStrokeColor(black)
    pdf_canvas.setLineWidth(1)

    for row_index in range(pair_count):
        x = sheet_layout.left_right_margin
        y = (
            sheet_layout.page_height
            - sheet_layout.top_bottom_margin
            - ((row_index + 1) * CARD_HEIGHT)
        )
        pair_width = CARD_WIDTH * 2

        if border:
            pdf_canvas.rect(x, y, pair_width, CARD_HEIGHT, stroke=1, fill=0)

        if cut_lines:
            draw_cut_lines(
                pdf_canvas,
                sheet_layout=sheet_layout,
                x=x,
                y=y,
                width=pair_width,
                height=CARD_HEIGHT,
            )

    pdf_canvas.showPage()
    pdf_canvas.save()
    buffer.seek(0)
    return PdfReader(buffer).pages[0]


def draw_cut_lines(
    pdf_canvas,
    *,
    sheet_layout: SheetLayout,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    right = x + width
    top = y + height

    pdf_canvas.line(0, top, x, top)
    pdf_canvas.line(right, top, sheet_layout.page_width, top)
    pdf_canvas.line(0, y, x, y)
    pdf_canvas.line(right, y, sheet_layout.page_width, y)

    pdf_canvas.line(x, top, x, sheet_layout.page_height)
    pdf_canvas.line(right, top, right, sheet_layout.page_height)
    pdf_canvas.line(x, 0, x, y)
    pdf_canvas.line(right, 0, right, y)
