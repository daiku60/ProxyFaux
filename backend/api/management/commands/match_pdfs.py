import json
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from api.models import Model

FACTION_DIRECTORY_OVERRIDES = {
    "Explorer's Society": "Explorers Society",
}


def load_manual_overrides(report_path: Path) -> dict[str, str]:
    if not report_path.exists():
        return {}

    try:
        raw_data = json.loads(report_path.read_text())
    except json.JSONDecodeError:
        return {}

    if not isinstance(raw_data, list):
        return {}

    overrides: dict[str, str] = {}
    for entry in raw_data:
        if not isinstance(entry, dict):
            continue

        source_id = entry.get("source_id")
        override_value = entry.get("shoud_map_to") or entry.get("should_map_to")
        if isinstance(source_id, str) and isinstance(override_value, str) and override_value.strip():
            overrides[source_id] = override_value.strip()

    return overrides


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def phrase_in_text(phrase: str, text: str) -> bool:
    normalized_phrase = normalize_text(phrase)
    normalized_text = normalize_text(text)
    return bool(normalized_phrase) and normalized_phrase in normalized_text


def build_model_name_candidates(model: Model) -> list[str]:
    candidates: list[str] = []

    files = model.files if isinstance(model.files, dict) else {}
    versions = files.get("versions")
    if isinstance(versions, list):
        for version in versions:
            if isinstance(version, dict):
                display_name = version.get("displayName")
                if isinstance(display_name, str) and display_name.strip():
                    candidates.append(display_name.strip())

    full_name = " ".join(part for part in [model.name, model.title] if part).strip()
    if full_name:
        candidates.append(full_name)
    if model.name:
        candidates.append(model.name)

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = normalize_text(candidate)
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(candidate)
    return deduped


def score_pdf(model: Model, pdf_stem: str) -> tuple[int, str | None]:
    name_candidates = build_model_name_candidates(model)
    matching_name = next((candidate for candidate in name_candidates if phrase_in_text(candidate, pdf_stem)), None)
    if not matching_name:
        return (-1, None)

    keywords = model.keywords if isinstance(model.keywords, list) else []
    keyword_score = sum(1 for keyword in keywords if isinstance(keyword, str) and phrase_in_text(keyword, pdf_stem))

    score = 100 + keyword_score * 10 + len(normalize_text(matching_name))
    return (score, matching_name)


def resolve_manual_override(
    override_value: str,
    faction_dir: Path,
    pdf_data_root: Path,
) -> Path | None:
    candidate = Path(override_value)

    possible_paths: list[Path] = []
    if candidate.is_absolute():
        possible_paths.append(candidate)
    else:
        possible_paths.append(faction_dir / override_value)
        possible_paths.append(pdf_data_root / override_value)

    for path in possible_paths:
        if path.exists() and path.is_file() and path.suffix.lower() == ".pdf":
            return path

    return None


class Command(BaseCommand):
    help = "Match Model rows to PDFs in backend/data/pdfs and store the relative PDF path."

    def handle(self, *args, **options) -> None:
        backend_dir = Path(__file__).resolve().parents[3]
        pdf_root = Path(settings.PDF_ROOT)
        report_path = backend_dir / "data" / "match_pdfs_failures.json"
        pdf_data_root = pdf_root.parent
        manual_overrides = load_manual_overrides(report_path)

        failures: list[dict[str, object]] = []
        matched = 0

        for model in Model.objects.all():
            faction_dir_name = FACTION_DIRECTORY_OVERRIDES.get(model.faction, model.faction)
            faction_dir = pdf_root / faction_dir_name

            if not faction_dir.exists():
                model.pdf = ""
                model.save(update_fields=["pdf"])
                failures.append(
                    {
                        "source_id": model.source_id,
                        "name": model.name,
                        "title": model.title,
                        "faction": model.faction,
                        "reason": f"Faction directory not found: {faction_dir_name}",
                        "shoud_map_to": manual_overrides.get(model.source_id, ""),
                    }
                )
                continue

            manual_override = manual_overrides.get(model.source_id, "")
            if manual_override:
                resolved_override = resolve_manual_override(manual_override, faction_dir, pdf_data_root)
                if resolved_override:
                    model.pdf = str(resolved_override.relative_to(pdf_data_root))
                    model.save(update_fields=["pdf"])
                    matched += 1
                    continue

                model.pdf = ""
                model.save(update_fields=["pdf"])
                failures.append(
                    {
                        "source_id": model.source_id,
                        "name": model.name,
                        "title": model.title,
                        "faction": model.faction,
                        "keywords": model.keywords,
                        "reason": f"Manual override did not resolve to a PDF: {manual_override}",
                        "shoud_map_to": manual_override,
                    }
                )
                continue

            best_match: Path | None = None
            best_score = -1

            for pdf_path in sorted(faction_dir.glob("*.pdf")):
                if not pdf_path.name.startswith("M4E_Stat_"):
                    continue

                score, _ = score_pdf(model, pdf_path.stem)
                if score > best_score:
                    best_score = score
                    best_match = pdf_path

            if not best_match:
                model.pdf = ""
                model.save(update_fields=["pdf"])
                failures.append(
                    {
                        "source_id": model.source_id,
                        "name": model.name,
                        "title": model.title,
                        "faction": model.faction,
                        "keywords": model.keywords,
                        "reason": "No matching PDF found",
                        "shoud_map_to": "",
                    }
                )
                continue

            model.pdf = str(best_match.relative_to(pdf_data_root))
            model.save(update_fields=["pdf"])
            matched += 1

        report_path.write_text(json.dumps(failures, indent=2))

        self.stdout.write(
            self.style.SUCCESS(
                f"Matched {matched} model PDFs. "
                f"Failures: {len(failures)}. "
                f"Report written to {report_path}"
            )
        )
