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
class CardSlot:
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class PlacedRect:
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class SheetLayout:
    page_width: float
    page_height: float
    placements_per_page: int
    slots: tuple[CardSlot, ...]


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
    layout_mode: str = "paper",
    mobile_cards_per_page: int = 1,
    mobile_device: str = "phone",
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
        sheet_layout=build_sheet_layout(
            sheet_size,
            layout_mode=layout_mode,
            mobile_cards_per_page=mobile_cards_per_page,
            mobile_device=mobile_device,
        ),
        border=border,
        cut_lines=cut_lines,
    )


def compose_selected_cards_pdf(
    requested_cards: list[RequestedCard],
    *,
    border: bool = False,
    cut_lines: bool = False,
    layout_mode: str = "paper",
    mobile_cards_per_page: int = 1,
    mobile_device: str = "phone",
    sheet_size: str = "a4",
) -> bytes:
    placements = resolve_pdf_placements(requested_cards)
    return render_composed_pdf(
        placements,
        sheet_layout=build_sheet_layout(
            sheet_size,
            layout_mode=layout_mode,
            mobile_cards_per_page=mobile_cards_per_page,
            mobile_device=mobile_device,
        ),
        border=border,
        cut_lines=cut_lines,
    )


def resolve_pdf_placements(requested_cards: list[RequestedCard]) -> list[PdfPlacement]:
    counters: dict[str, int] = {}
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
                counter_key = getattr(requested_card.card, "source_id", requested_card.raw_name)
                current_index = counters.get(counter_key, 0)
                chosen_variant = variants[current_index % len(variants)]
                counters[counter_key] = current_index + 1

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

    if normalized_language == "en":
        return Path(settings.PDF_ROOT)

    pdf_data_root = Path(getattr(settings, "PDF_DATA_ROOT", Path(settings.PDF_ROOT).parent))
    language_pdf_root = pdf_data_root / normalized_language / "pdfs"
    if language_pdf_root.exists():
        return language_pdf_root

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


def build_sheet_layout(
    sheet_size: str,
    *,
    layout_mode: str = "paper",
    mobile_cards_per_page: int = 1,
    mobile_device: str = "phone",
) -> SheetLayout:
    normalized_layout_mode = layout_mode.lower()
    if normalized_layout_mode == "mobile":
        if mobile_device == "phone":
            return build_phone_layout()
        if mobile_device == "tablet":
            return build_tablet_layout(mobile_cards_per_page)
        raise PdfCompositionError(
            f"Unsupported mobile device `{mobile_device}`. Use `phone` or `tablet`."
        )
    if normalized_layout_mode != "paper":
        raise PdfCompositionError(
            f"Unsupported layout mode `{layout_mode}`. Use `paper` or `mobile`."
        )

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
        placements_per_page=2,
        slots=(
            CardSlot(
                x=left_right_margin,
                y=page_height - top_bottom_margin - CARD_HEIGHT,
                width=CARD_WIDTH,
                height=CARD_HEIGHT,
            ),
            CardSlot(
                x=left_right_margin + CARD_WIDTH,
                y=page_height - top_bottom_margin - CARD_HEIGHT,
                width=CARD_WIDTH,
                height=CARD_HEIGHT,
            ),
            CardSlot(
                x=left_right_margin,
                y=page_height - top_bottom_margin - (CARD_HEIGHT * 2),
                width=CARD_WIDTH,
                height=CARD_HEIGHT,
            ),
            CardSlot(
                x=left_right_margin + CARD_WIDTH,
                y=page_height - top_bottom_margin - (CARD_HEIGHT * 2),
                width=CARD_WIDTH,
                height=CARD_HEIGHT,
            ),
        ),
    )

def build_phone_layout() -> SheetLayout:
    # iPhone 16 logical viewport size in portrait orientation.
    page_width = 393
    page_height = 852
    horizontal_margin = 16
    vertical_margin = 20
    gap = 20
    available_width = page_width - (horizontal_margin * 2)
    available_height = page_height - (vertical_margin * 2) - gap
    slot_height = available_height / 2
    slot_width = min(available_width, slot_height * (CARD_WIDTH / CARD_HEIGHT))

    return SheetLayout(
        page_width=page_width,
        page_height=page_height,
        placements_per_page=1,
        slots=(
            CardSlot(
                x=(page_width - slot_width) / 2,
                y=page_height - vertical_margin - slot_height,
                width=slot_width,
                height=slot_height,
            ),
            CardSlot(
                x=(page_width - slot_width) / 2,
                y=vertical_margin,
                width=slot_width,
                height=slot_height,
            ),
        ),
    )


def build_tablet_layout(cards_per_page: int) -> SheetLayout:
    if cards_per_page not in {1, 2, 3, 4, 6}:
        raise PdfCompositionError(
            f"Unsupported tablet cards-per-page value `{cards_per_page}`. Use 1, 2, 3, 4, or 6."
        )

    page_width = 1194
    page_height = 834
    horizontal_margin = 24
    vertical_margin = 24
    pair_gap = 12
    grid_gap_x = 18
    grid_gap_y = 18

    if cards_per_page in {1, 2, 3}:
        return build_pair_grid_layout(
            page_width=page_width,
            page_height=page_height,
            horizontal_margin=horizontal_margin,
            vertical_margin=vertical_margin,
            placements_across=cards_per_page,
            placements_down=1,
            pair_gap=pair_gap,
            grid_gap_x=grid_gap_x,
            grid_gap_y=grid_gap_y,
        )

    if cards_per_page == 4:
        return build_pair_grid_layout(
            page_width=page_width,
            page_height=page_height,
            horizontal_margin=horizontal_margin,
            vertical_margin=vertical_margin,
            placements_across=2,
            placements_down=2,
            pair_gap=pair_gap,
            grid_gap_x=grid_gap_x,
            grid_gap_y=grid_gap_y,
        )

    return build_pair_grid_layout(
        page_width=page_width,
        page_height=page_height,
        horizontal_margin=horizontal_margin,
        vertical_margin=vertical_margin,
        placements_across=3,
        placements_down=2,
        pair_gap=pair_gap,
        grid_gap_x=grid_gap_x,
        grid_gap_y=grid_gap_y,
    )


def build_pair_grid_layout(
    *,
    page_width: float,
    page_height: float,
    horizontal_margin: float,
    vertical_margin: float,
    placements_across: int,
    placements_down: int,
    pair_gap: float,
    grid_gap_x: float,
    grid_gap_y: float,
) -> SheetLayout:
    cell_width = (
        page_width
        - (horizontal_margin * 2)
        - (grid_gap_x * (placements_across - 1))
    ) / placements_across
    cell_height = (
        page_height
        - (vertical_margin * 2)
        - (grid_gap_y * (placements_down - 1))
    ) / placements_down
    slot_width = (cell_width - pair_gap) / 2

    slots: list[CardSlot] = []
    for row_index in range(placements_down):
        for column_index in range(placements_across):
            cell_x = horizontal_margin + (column_index * (cell_width + grid_gap_x))
            cell_y = (
                page_height
                - vertical_margin
                - ((row_index + 1) * cell_height)
                - (row_index * grid_gap_y)
            )
            slots.append(
                CardSlot(
                    x=cell_x,
                    y=cell_y,
                    width=slot_width,
                    height=cell_height,
                )
            )
            slots.append(
                CardSlot(
                    x=cell_x + slot_width + pair_gap,
                    y=cell_y,
                    width=slot_width,
                    height=cell_height,
                )
            )

    return SheetLayout(
        page_width=page_width,
        page_height=page_height,
        placements_per_page=placements_across * placements_down,
        slots=tuple(slots),
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

    for start_index in range(0, len(placements), sheet_layout.placements_per_page):
        page_placements = placements[start_index : start_index + sheet_layout.placements_per_page]
        output_page = writer.add_blank_page(
            width=sheet_layout.page_width,
            height=sheet_layout.page_height,
        )
        page_pair_rects: list[tuple[PlacedRect, ...]] = []
        for placement_index, placement in enumerate(page_placements):
            reader = PdfReader(str(placement.source_path))
            readers.append(reader)
            pair_rects: list[PlacedRect] = []
            for page_offset, page_index in enumerate(placement.page_indexes):
                source_page = reader.pages[page_index]
                slot = sheet_layout.slots[(placement_index * 2) + page_offset]
                pair_rects.append(
                    place_page_in_slot(
                    output_page,
                    source_page,
                    slot=slot,
                    )
                )
            page_pair_rects.append(tuple(pair_rects))

        overlay_page = build_overlay_page(
            page_pair_rects,
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
    slot = sheet_layout.slots[(row_index * 2) + column_index]
    place_page_in_slot(output_page, source_page, slot=slot)


def place_page_in_slot(
    output_page,
    source_page,
    *,
    slot: CardSlot,
) -> PlacedRect:
    source_width = float(source_page.mediabox.width)
    source_height = float(source_page.mediabox.height)
    scale = min(slot.width / source_width, slot.height / source_height)

    translate_x = slot.x + ((slot.width - (source_width * scale)) / 2)
    translate_y = slot.y + ((slot.height - (source_height * scale)) / 2)

    transformation = Transformation().scale(scale).translate(translate_x, translate_y)
    output_page.merge_transformed_page(source_page, transformation)
    return PlacedRect(
        x=translate_x,
        y=translate_y,
        width=source_width * scale,
        height=source_height * scale,
    )


def build_overlay_page(
    pair_rects: list[tuple[PlacedRect, ...]],
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

    for rect_group in pair_rects:
        x = min(rect.x for rect in rect_group)
        y = min(rect.y for rect in rect_group)
        right = max(rect.x + rect.width for rect in rect_group)
        top = max(rect.y + rect.height for rect in rect_group)
        pair_width = right - x
        pair_height = top - y

        if border:
            pdf_canvas.rect(x, y, pair_width, pair_height, stroke=1, fill=0)

        if cut_lines:
            draw_cut_lines(
                pdf_canvas,
                sheet_layout=sheet_layout,
                x=x,
                y=y,
                width=pair_width,
                height=pair_height,
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
