import json
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from api.models import Model

FACTION_DIRECTORY_OVERRIDES = {
    "Resurrectionist": "Resurrectionists",
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


def build_failure_entry(
    model: Model,
    reason: str,
    should_map_to: str = "",
) -> dict[str, object]:
    entry: dict[str, object] = {
        "source_id": model.source_id,
        "name": model.name,
        "title": model.title,
        "faction": model.faction,
        "reason": reason,
        "should_map_to": should_map_to,
    }
    if model.keywords:
        entry["keywords"] = model.keywords
    return entry


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def phrase_in_text(phrase: str, text: str) -> bool:
    normalized_phrase = normalize_text(phrase)
    normalized_text = normalize_text(text)
    return bool(normalized_phrase) and normalized_phrase in normalized_text


def words_in_order(phrase: str, text: str) -> bool:
    phrase_words = [word for word in normalize_text(phrase).split() if word]
    text_words = [word for word in normalize_text(text).split() if word]
    if not phrase_words:
        return False

    text_index = 0
    for phrase_word in phrase_words:
        while text_index < len(text_words) and text_words[text_index] != phrase_word:
            text_index += 1
        if text_index == len(text_words):
            return False
        text_index += 1

    return True


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
    matching_name = next(
        (candidate for candidate in name_candidates if phrase_in_text(candidate, pdf_stem)),
        None,
    )
    partial_name_match = False
    if not matching_name:
        matching_name = next(
            (
                candidate
                for candidate in name_candidates
                if len(normalize_text(candidate).split()) > 1 and words_in_order(candidate, pdf_stem)
            ),
            None,
        )
        partial_name_match = matching_name is not None

    if not matching_name:
        return (-1, None)

    keywords = model.keywords if isinstance(model.keywords, list) else []
    keyword_score = sum(1 for keyword in keywords if isinstance(keyword, str) and phrase_in_text(keyword, pdf_stem))

    score = 80 if partial_name_match else 100
    score += keyword_score * 10 + len(normalize_text(matching_name))
    return (score, matching_name)


def prefer_pdf_candidate(candidate: Path, current_best: Path | None) -> bool:
    if current_best is None:
        return True

    return candidate.name.startswith("M4E_Stat_") and not current_best.name.startswith("M4E_Stat_")


def resolve_manual_override(
    override_value: str,
    search_dir: Path,
    faction_dir: Path,
    pdf_data_root: Path,
) -> Path | None:
    candidate = Path(override_value)

    possible_paths: list[Path] = []
    if candidate.is_absolute():
        possible_paths.append(candidate)
    else:
        possible_paths.append(search_dir / override_value)
        possible_paths.append(faction_dir / override_value)
        possible_paths.append(pdf_data_root / override_value)

    for path in possible_paths:
        if path.exists() and path.is_file() and path.suffix.lower() == ".pdf":
            return path

    return None


def build_pdf_storage_path(pdf_path: Path, pdf_data_root: Path) -> str:
    match = re.match(r"^(?P<prefix>.+)_([A-Z])$", pdf_path.stem)
    if not match:
        return str(pdf_path.relative_to(pdf_data_root))

    prefix = match.group("prefix")
    variant_paths = sorted(pdf_path.parent.glob(f"{prefix}_[A-Z].pdf"))
    variant_letters = [
        variant_path.stem.rsplit("_", 1)[-1]
        for variant_path in variant_paths
        if re.match(rf"^{re.escape(prefix)}_[A-Z]$", variant_path.stem)
    ]

    if len(variant_letters) <= 1:
        return str(pdf_path.relative_to(pdf_data_root))

    grouped_name = f"{prefix}_{{{'|'.join(variant_letters)}}}.pdf"
    return str((pdf_path.parent / grouped_name).relative_to(pdf_data_root))


def resolve_faction_dir(pdf_root: Path, faction: str) -> Path | None:
    direct_dir = pdf_root / faction
    if direct_dir.exists():
        return direct_dir

    override_dir = pdf_root / FACTION_DIRECTORY_OVERRIDES.get(faction, faction)
    if override_dir.exists():
        return override_dir

    return None


def resolve_search_dir(model: Model, faction_dir: Path) -> Path | None:
    keywords = model.keywords if isinstance(model.keywords, list) else []
    first_keyword = next((keyword for keyword in keywords if isinstance(keyword, str) and keyword.strip()), None)

    if first_keyword:
        keyword_dir = faction_dir / first_keyword
        if keyword_dir.exists():
            return keyword_dir

    versatile_dir = faction_dir / f"Versatile - {faction_dir.name}"
    if versatile_dir.exists():
        return versatile_dir

    return None


def iter_search_dirs(model: Model, pdf_root: Path, faction_dir: Path) -> list[Path]:
    search_dirs: list[Path] = []
    seen: set[Path] = set()

    def add_dir(path: Path | None) -> None:
        if path and path.exists() and path.is_dir() and path not in seen:
            seen.add(path)
            search_dirs.append(path)

    keywords = [
        keyword.strip()
        for keyword in (model.keywords if isinstance(model.keywords, list) else [])
        if isinstance(keyword, str) and keyword.strip()
    ]
    chosen_keyword: str | None = None
    keyword_dir_exists = False
    for keyword in keywords:
        keyword_dir = faction_dir / keyword
        if keyword_dir.exists() and keyword_dir.is_dir():
            add_dir(keyword_dir)
            chosen_keyword = keyword
            keyword_dir_exists = True
            break

    versatile_dir = faction_dir / f"Versatile - {faction_dir.name}"
    add_dir(versatile_dir)

    if keywords and not keyword_dir_exists:
        first_keyword = keywords[0]
        for other_faction_dir in sorted(path for path in pdf_root.iterdir() if path.is_dir()):
            if other_faction_dir == faction_dir:
                continue
            add_dir(other_faction_dir / first_keyword)

    if len(keywords) > 1:
        alternate_keywords = [keyword for keyword in keywords if keyword != chosen_keyword]
        for alternate_keyword in alternate_keywords:
            for other_faction_dir in sorted(path for path in pdf_root.iterdir() if path.is_dir()):
                if other_faction_dir == faction_dir:
                    continue
                add_dir(other_faction_dir / alternate_keyword)

    return search_dirs


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
            faction_dir = resolve_faction_dir(pdf_root, model.faction)

            if not faction_dir:
                if not model.pdf:
                    model.pdf = ""
                    model.save(update_fields=["pdf"])
                failures.append(
                    build_failure_entry(
                        model,
                        f"Faction directory not found: {model.faction}",
                        manual_overrides.get(model.source_id, ""),
                    )
                )
                continue

            search_dirs = iter_search_dirs(model, pdf_root, faction_dir)
            if not search_dirs:
                if not model.pdf:
                    model.pdf = ""
                    model.save(update_fields=["pdf"])
                failures.append(
                    build_failure_entry(
                        model,
                        "Keyword directory not found",
                        manual_overrides.get(model.source_id, ""),
                    )
                )
                continue

            manual_override = manual_overrides.get(model.source_id, "")
            if manual_override:
                resolved_override = None
                for search_dir in search_dirs:
                    resolved_override = resolve_manual_override(
                        manual_override,
                        search_dir,
                        faction_dir,
                        pdf_data_root,
                    )
                    if resolved_override:
                        break
                if resolved_override:
                    model.pdf = build_pdf_storage_path(resolved_override, pdf_data_root)
                    model.save(update_fields=["pdf"])
                    matched += 1
                    failures.append(
                        build_failure_entry(
                            model,
                            "Matched manually",
                            manual_override,
                        )
                    )
                    continue

                if not model.pdf:
                    model.pdf = ""
                    model.save(update_fields=["pdf"])
                failures.append(
                    build_failure_entry(
                        model,
                        f"Manual override did not resolve to a PDF: {manual_override}",
                        manual_override,
                    )
                )
                continue

            best_match: Path | None = None
            best_score = -1

            for search_dir in search_dirs:
                for pdf_path in sorted(search_dir.glob("*.pdf")):
                    score, _ = score_pdf(model, pdf_path.stem)
                    if score > best_score:
                        best_score = score
                        best_match = pdf_path
                    elif (
                        score == best_score
                        and score >= 0
                        and prefer_pdf_candidate(pdf_path, best_match)
                    ):
                        best_match = pdf_path

            if not best_match:
                if not model.pdf:
                    model.pdf = ""
                    model.save(update_fields=["pdf"])
                failures.append(
                    build_failure_entry(model, "No matching PDF found")
                )
                continue

            model.pdf = build_pdf_storage_path(best_match, pdf_data_root)
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
