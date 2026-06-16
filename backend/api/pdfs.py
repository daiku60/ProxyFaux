import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from django.conf import settings
from pypdf import PdfReader, PdfWriter, Transformation

from api.models import Model

MM_TO_POINTS = 72 / 25.4
A4_WIDTH_MM = 210
A4_HEIGHT_MM = 297
CARD_WIDTH_MM = 70
CARD_HEIGHT_MM = 120

PAGE_WIDTH = A4_WIDTH_MM * MM_TO_POINTS
PAGE_HEIGHT = A4_HEIGHT_MM * MM_TO_POINTS
CARD_WIDTH = CARD_WIDTH_MM * MM_TO_POINTS
CARD_HEIGHT = CARD_HEIGHT_MM * MM_TO_POINTS
LEFT_RIGHT_MARGIN = ((A4_WIDTH_MM - (CARD_WIDTH_MM * 2)) / 2) * MM_TO_POINTS
TOP_BOTTOM_MARGIN = ((A4_HEIGHT_MM - (CARD_HEIGHT_MM * 2)) / 2) * MM_TO_POINTS

VARIANT_PATTERN = re.compile(r"\{([A-Z](?:\|[A-Z])*)\}")
TRAILING_VARIANT_PATTERN = re.compile(r"^(?P<name>.+?)\s+(?P<variant>[A-Z])$")


class PdfCompositionError(ValueError):
    pass


@dataclass(frozen=True)
class RequestedModel:
    raw_name: str
    model: Model
    variant: str | None = None


@dataclass(frozen=True)
class PdfPlacement:
    source_path: Path
    page_indexes: tuple[int, int]


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def build_model_lookup(models: list[Model]) -> dict[str, Model]:
    lookup: dict[str, Model] = {}
    for model in models:
        for candidate in iter_model_name_candidates(model):
            lookup.setdefault(normalize_name(candidate), model)
    return lookup


def iter_model_name_candidates(model: Model) -> list[str]:
    candidates: list[str] = []

    files = model.files if isinstance(model.files, dict) else {}
    versions = files.get("versions")
    if isinstance(versions, list):
        for version in versions:
            if isinstance(version, dict):
                display_name = version.get("displayName")
                if isinstance(display_name, str) and display_name.strip():
                    candidates.append(display_name.strip())

    if model.name and model.title:
        candidates.append(f"{model.name}, {model.title}")
        candidates.append(f"{model.name} {model.title}")
    if model.name:
        candidates.append(model.name)

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = normalize_name(candidate)
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(candidate)
    return deduped


def parse_requested_models(text: str, models: list[Model]) -> list[RequestedModel]:
    lookup = build_model_lookup(models)
    requested: list[RequestedModel] = []
    unresolved: list[str] = []

    for raw_line in text.splitlines():
        cleaned_line = clean_input_line(raw_line)
        if not cleaned_line:
            continue

        resolved_line = resolve_requested_model(cleaned_line, lookup)
        if resolved_line is not None:
            requested.append(resolved_line)
            continue

        parts = [part.strip() for part in cleaned_line.split(",") if part.strip()]
        if len(parts) > 1:
            resolved_parts = [resolve_requested_model(part, lookup) for part in parts]
            if all(resolved_parts):
                requested.extend(
                    resolved_part
                    for resolved_part in resolved_parts
                    if resolved_part is not None
                )
                continue

        unresolved.append(cleaned_line)

    if unresolved:
        unresolved_display = ", ".join(unresolved)
        raise PdfCompositionError(f"Could not resolve model names from: {unresolved_display}")

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


def resolve_requested_model(raw_name: str, lookup: dict[str, Model]) -> RequestedModel | None:
    normalized_name = normalize_name(raw_name)
    if not normalized_name:
        return None

    model = lookup.get(normalized_name)
    if model is not None:
        return RequestedModel(raw_name=raw_name, model=model)

    match = TRAILING_VARIANT_PATTERN.match(raw_name)
    if not match:
        return None

    variant = match.group("variant")
    base_name = match.group("name").strip()
    model = lookup.get(normalize_name(base_name))
    if model is None:
        return None

    return RequestedModel(raw_name=raw_name, model=model, variant=variant)


def compose_model_pdf(text: str) -> bytes:
    requested_models = parse_requested_models(text, list(Model.objects.exclude(pdf="")))
    placements = resolve_pdf_placements(requested_models)
    return render_composed_pdf(placements)


def resolve_pdf_placements(requested_models: list[RequestedModel]) -> list[PdfPlacement]:
    counters: dict[int, int] = {}
    placements: list[PdfPlacement] = []

    for requested_model in requested_models:
        pdf_path, variants = resolve_pdf_path_and_variants(requested_model.model.pdf)
        chosen_variant: str | None = None
        if variants:
            if requested_model.variant is not None:
                if requested_model.variant not in variants:
                    raise PdfCompositionError(
                        f"{requested_model.raw_name} requested variant {requested_model.variant}, "
                        f"but available variants are {', '.join(variants)}."
                    )
                chosen_variant = requested_model.variant
            else:
                current_index = counters.get(requested_model.model.pk or -1, 0)
                chosen_variant = variants[current_index % len(variants)]
                counters[requested_model.model.pk or -1] = current_index + 1

        resolved_path = build_variant_pdf_path(pdf_path, chosen_variant)
        if not resolved_path.exists():
            raise PdfCompositionError(
                f"Missing PDF for {requested_model.raw_name}: {resolved_path}"
            )

        reader = PdfReader(str(resolved_path))
        if len(reader.pages) < 2:
            raise PdfCompositionError(
                f"PDF for {requested_model.raw_name} must contain at least two pages."
            )

        placements.append(PdfPlacement(source_path=resolved_path, page_indexes=(0, 1)))

    return placements


def resolve_pdf_path_and_variants(pdf_value: str) -> tuple[Path, list[str]]:
    pdf_root = Path(settings.PDF_ROOT)
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


def path_starts_with_parts(path: Path, prefix_parts: tuple[str, ...]) -> bool:
    if len(path.parts) < len(prefix_parts):
        return False

    return path.parts[: len(prefix_parts)] == prefix_parts


def build_variant_pdf_path(path_with_pattern: Path, variant: str | None) -> Path:
    if variant is None:
        return path_with_pattern

    resolved_name = VARIANT_PATTERN.sub(variant, path_with_pattern.name)
    return path_with_pattern.with_name(resolved_name)


def render_composed_pdf(placements: list[PdfPlacement]) -> bytes:
    writer = PdfWriter()
    readers: list[PdfReader] = []

    for start_index in range(0, len(placements), 2):
        output_page = writer.add_blank_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        for row_index, placement in enumerate(placements[start_index : start_index + 2]):
            reader = PdfReader(str(placement.source_path))
            readers.append(reader)
            for column_index, page_index in enumerate(placement.page_indexes):
                source_page = reader.pages[page_index]
                place_page_on_sheet(
                    output_page,
                    source_page,
                    row_index=row_index,
                    column_index=column_index,
                )

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def place_page_on_sheet(output_page, source_page, *, row_index: int, column_index: int) -> None:
    source_width = float(source_page.mediabox.width)
    source_height = float(source_page.mediabox.height)
    scale = min(CARD_WIDTH / source_width, CARD_HEIGHT / source_height)

    x = LEFT_RIGHT_MARGIN + (column_index * CARD_WIDTH)
    y = PAGE_HEIGHT - TOP_BOTTOM_MARGIN - ((row_index + 1) * CARD_HEIGHT)
    translate_x = x + ((CARD_WIDTH - (source_width * scale)) / 2)
    translate_y = y + ((CARD_HEIGHT - (source_height * scale)) / 2)

    transformation = Transformation().scale(scale).translate(translate_x, translate_y)
    output_page.merge_transformed_page(source_page, transformation)
