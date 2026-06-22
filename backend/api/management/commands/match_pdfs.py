import json
import re
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

from api.models import Model

FACTION_DIRECTORY_OVERRIDES = {
    "Resurrectionist": "Resurrectionists",
}


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


def build_override_key(entity_type: str, source_id: str) -> str:
    return f"{entity_type}:{source_id}"


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
        if not isinstance(source_id, str) or not isinstance(override_value, str):
            continue
        if not override_value.strip():
            continue

        entity_type = entry.get("entity_type")
        if not isinstance(entity_type, str) or not entity_type.strip():
            entity_type = "model"

        overrides[build_override_key(entity_type, source_id)] = override_value.strip()

    return overrides


def build_model_failure_entry(
    model: Model,
    reason: str,
    should_map_to: str = "",
) -> dict[str, object]:
    entry: dict[str, object] = {
        "entity_type": "model",
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


def build_crew_card_failure_entry(
    source_id: str,
    card_data: dict[str, Any],
    reason: str,
    should_map_to: str = "",
) -> dict[str, object]:
    entry: dict[str, object] = {
        "entity_type": "crew_card",
        "source_id": source_id,
        "name": card_data.get("name", ""),
        "faction": card_data.get("faction", ""),
        "reason": reason,
        "should_map_to": should_map_to,
    }

    text = card_data.get("text")
    if isinstance(text, str) and text.strip():
        entry["text"] = text

    keywords = card_data.get("keywords")
    if isinstance(keywords, list) and keywords:
        entry["keywords"] = keywords

    return entry


def build_upgrade_failure_entry(
    source_id: str,
    upgrade_data: dict[str, Any],
    reason: str,
    should_map_to: str = "",
) -> dict[str, object]:
    entry: dict[str, object] = {
        "entity_type": "upgrade",
        "source_id": source_id,
        "name": upgrade_data.get("name", ""),
        "faction": upgrade_data.get("faction", ""),
        "reason": reason,
        "should_map_to": should_map_to,
    }

    text = upgrade_data.get("text")
    if isinstance(text, str) and text.strip():
        entry["text"] = text

    keywords = upgrade_data.get("keywords")
    if isinstance(keywords, list) and keywords:
        entry["keywords"] = keywords

    return entry


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

    return dedupe_candidates(candidates)


def dedupe_candidates(candidates: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = normalize_text(candidate)
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(candidate)
    return deduped


def score_candidate(
    name_candidates: list[str],
    keywords: list[str],
    pdf_stem: str,
    partial_match_score: int = 80,
    exact_match_score: int = 100,
) -> tuple[int, str | None]:
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

    keyword_score = sum(
        1 for keyword in keywords if isinstance(keyword, str) and phrase_in_text(keyword, pdf_stem)
    )

    score = partial_match_score if partial_name_match else exact_match_score
    score += keyword_score * 10 + len(normalize_text(matching_name))
    return (score, matching_name)


def score_pdf(model: Model, pdf_stem: str) -> tuple[int, str | None]:
    keywords = model.keywords if isinstance(model.keywords, list) else []
    return score_candidate(build_model_name_candidates(model), keywords, pdf_stem)


def build_crew_card_name_candidates(source_id: str, card_data: dict[str, Any]) -> list[str]:
    candidates: list[str] = []

    name = card_data.get("name")
    if isinstance(name, str) and name.strip():
        candidates.append(name.strip())

    text = card_data.get("text")
    if isinstance(text, str) and text.strip():
        candidates.append(text.strip())

    files = card_data.get("files")
    if isinstance(files, dict):
        versions = files.get("versions")
        if isinstance(versions, list):
            for version in versions:
                if not isinstance(version, dict):
                    continue
                display_name = version.get("displayName")
                if isinstance(display_name, str) and display_name.strip():
                    candidates.append(display_name.strip())

                front_path = version.get("front")
                if isinstance(front_path, str) and front_path.strip():
                    candidates.extend(extract_candidates_from_front_path(front_path))

    candidates.append(source_id)
    return dedupe_candidates(candidates)


def build_upgrade_name_candidates(source_id: str, upgrade_data: dict[str, Any]) -> list[str]:
    candidates: list[str] = []

    name = upgrade_data.get("name")
    if isinstance(name, str) and name.strip():
        candidates.append(name.strip())

    text = upgrade_data.get("text")
    if isinstance(text, str) and text.strip():
        candidates.append(text.strip())

    files = upgrade_data.get("files")
    if isinstance(files, dict):
        versions = files.get("versions")
        if isinstance(versions, list):
            for version in versions:
                if not isinstance(version, dict):
                    continue
                display_name = version.get("displayName")
                if isinstance(display_name, str) and display_name.strip():
                    candidates.append(display_name.strip())

    candidates.append(source_id)
    return dedupe_candidates(candidates)


def extract_candidates_from_front_path(front_path: str) -> list[str]:
    stem = Path(front_path).stem
    if stem.endswith("-front"):
        stem = stem[: -len("-front")]
    elif stem.endswith("-back"):
        stem = stem[: -len("-back")]

    if stem.startswith("Crew-"):
        stem = stem[len("Crew-") :]

    parts = [part for part in stem.split("-") if part]
    if not parts:
        return []

    joined = " ".join(parts)
    candidates = [joined]

    if len(parts) >= 2:
        for split_index in range(1, len(parts)):
            left = " ".join(parts[:split_index])
            right = " ".join(parts[split_index:])
            if left and right:
                candidates.append(f"{left} {right}")

    return candidates


def prefer_model_pdf_candidate(candidate: Path, current_best: Path | None) -> bool:
    if current_best is None:
        return True
    return candidate.name.startswith("M4E_Stat_") and not current_best.name.startswith("M4E_Stat_")


def prefer_crew_card_pdf_candidate(candidate: Path, current_best: Path | None) -> bool:
    if current_best is None:
        return True
    return candidate.name.startswith("M4E_Crew_") and not current_best.name.startswith("M4E_Crew_")


def prefer_upgrade_pdf_candidate(candidate: Path, current_best: Path | None) -> bool:
    if current_best is None:
        return True
    return candidate.name.startswith("M4E_Upgrade_") and not current_best.name.startswith(
        "M4E_Upgrade_"
    )


def prefer_stat_pdf_path(path: Path) -> Path:
    if path.name.startswith("M4E_Stat_"):
        return path

    if not path.name.startswith("M4E_Crew_"):
        return path

    stat_candidate = path.with_name(path.name.replace("M4E_Crew_", "M4E_Stat_", 1))
    if stat_candidate.exists() and stat_candidate.is_file():
        return stat_candidate

    return path


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


def iter_search_dirs_for_keywords(
    keywords: list[str],
    pdf_root: Path,
    faction_dir: Path,
) -> list[Path]:
    search_dirs: list[Path] = []
    seen: set[Path] = set()

    def add_dir(path: Path | None) -> None:
        if path and path.exists() and path.is_dir() and path not in seen:
            seen.add(path)
            search_dirs.append(path)

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


def iter_search_dirs(model: Model, pdf_root: Path, faction_dir: Path) -> list[Path]:
    keywords = [
        keyword.strip()
        for keyword in (model.keywords if isinstance(model.keywords, list) else [])
        if isinstance(keyword, str) and keyword.strip()
    ]
    return iter_search_dirs_for_keywords(keywords, pdf_root, faction_dir)


def iter_crew_card_search_dirs(
    card_data: dict[str, Any],
    pdf_root: Path,
    faction_dir: Path,
) -> list[Path]:
    keywords = [
        keyword.strip()
        for keyword in (card_data.get("keywords") if isinstance(card_data.get("keywords"), list) else [])
        if isinstance(keyword, str) and keyword.strip()
    ]
    return iter_search_dirs_for_keywords(keywords, pdf_root, faction_dir)


def iter_upgrade_search_dirs(
    upgrade_data: dict[str, Any],
    pdf_root: Path,
    faction_dir: Path,
) -> list[Path]:
    keywords = [
        keyword.strip()
        for keyword in (
            upgrade_data.get("keywords")
            if isinstance(upgrade_data.get("keywords"), list)
            else []
        )
        if isinstance(keyword, str) and keyword.strip()
    ]
    return iter_search_dirs_for_keywords(keywords, pdf_root, faction_dir)


def match_model_pdfs(
    pdf_root: Path,
    pdf_data_root: Path,
    manual_overrides: dict[str, str],
) -> tuple[int, list[dict[str, object]]]:
    failures: list[dict[str, object]] = []
    matched = 0

    for model in Model.objects.all():
        override_key = build_override_key("model", model.source_id)
        faction_dir = resolve_faction_dir(pdf_root, model.faction)

        if not faction_dir:
            if not model.pdf:
                model.pdf = ""
                model.save(update_fields=["pdf"])
            failures.append(
                build_model_failure_entry(
                    model,
                    f"Faction directory not found: {model.faction}",
                    manual_overrides.get(override_key, ""),
                )
            )
            continue

        search_dirs = iter_search_dirs(model, pdf_root, faction_dir)
        if not search_dirs:
            if not model.pdf:
                model.pdf = ""
                model.save(update_fields=["pdf"])
            failures.append(
                build_model_failure_entry(
                    model,
                    "Keyword directory not found",
                    manual_overrides.get(override_key, ""),
                )
            )
            continue

        manual_override = manual_overrides.get(override_key, "")
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
                model.pdf = build_pdf_storage_path(
                    prefer_stat_pdf_path(resolved_override),
                    pdf_data_root,
                )
                model.save(update_fields=["pdf"])
                matched += 1
                failures.append(
                    build_model_failure_entry(
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
                build_model_failure_entry(
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
                    and prefer_model_pdf_candidate(pdf_path, best_match)
                ):
                    best_match = pdf_path

        if not best_match:
            if not model.pdf:
                model.pdf = ""
                model.save(update_fields=["pdf"])
            failures.append(build_model_failure_entry(model, "No matching PDF found"))
            continue

        model.pdf = build_pdf_storage_path(prefer_stat_pdf_path(best_match), pdf_data_root)
        model.save(update_fields=["pdf"])
        matched += 1

    return matched, failures


def match_crew_card_pdfs(
    cards_json_path: Path,
    pdf_root: Path,
    pdf_data_root: Path,
    manual_overrides: dict[str, str],
) -> tuple[int, list[dict[str, object]]]:
    cards_data = json.loads(cards_json_path.read_text())
    crew_cards = cards_data.get("crewCards")
    if not isinstance(crew_cards, dict):
        return 0, []

    failures: list[dict[str, object]] = []
    matched = 0

    for source_id, raw_card_data in crew_cards.items():
        if not isinstance(source_id, str) or not isinstance(raw_card_data, dict):
            continue

        card_data = raw_card_data
        override_key = build_override_key("crew_card", source_id)
        faction = card_data.get("faction")
        faction_dir = resolve_faction_dir(pdf_root, faction) if isinstance(faction, str) else None

        if not faction_dir:
            card_data["pdf"] = ""
            failures.append(
                build_crew_card_failure_entry(
                    source_id,
                    card_data,
                    f"Faction directory not found: {faction}",
                    manual_overrides.get(override_key, ""),
                )
            )
            continue

        search_dirs = iter_crew_card_search_dirs(card_data, pdf_root, faction_dir)
        if not search_dirs:
            card_data["pdf"] = ""
            failures.append(
                build_crew_card_failure_entry(
                    source_id,
                    card_data,
                    "Keyword directory not found",
                    manual_overrides.get(override_key, ""),
                )
            )
            continue

        manual_override = manual_overrides.get(override_key, "")
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
                card_data["pdf"] = build_pdf_storage_path(resolved_override, pdf_data_root)
                matched += 1
                failures.append(
                    build_crew_card_failure_entry(
                        source_id,
                        card_data,
                        "Matched manually",
                        manual_override,
                    )
                )
                continue

            card_data["pdf"] = ""
            failures.append(
                build_crew_card_failure_entry(
                    source_id,
                    card_data,
                    f"Manual override did not resolve to a PDF: {manual_override}",
                    manual_override,
                )
            )
            continue

        keywords = [
            keyword
            for keyword in card_data.get("keywords", [])
            if isinstance(keyword, str) and keyword.strip()
        ]
        name_candidates = build_crew_card_name_candidates(source_id, card_data)
        best_match: Path | None = None
        best_score = -1

        for search_dir in search_dirs:
            for pdf_path in sorted(search_dir.glob("*.pdf")):
                score, _ = score_candidate(name_candidates, keywords, pdf_path.stem)
                if score > best_score:
                    best_score = score
                    best_match = pdf_path
                elif (
                    score == best_score
                    and score >= 0
                    and prefer_crew_card_pdf_candidate(pdf_path, best_match)
                ):
                    best_match = pdf_path

        if not best_match:
            card_data["pdf"] = ""
            failures.append(
                build_crew_card_failure_entry(source_id, card_data, "No matching PDF found")
            )
            continue

        card_data["pdf"] = build_pdf_storage_path(best_match, pdf_data_root)
        matched += 1

    cards_json_path.write_text(json.dumps(cards_data, indent=4))
    return matched, failures


def match_upgrade_pdfs(
    cards_json_path: Path,
    pdf_root: Path,
    pdf_data_root: Path,
    manual_overrides: dict[str, str],
) -> tuple[int, list[dict[str, object]]]:
    cards_data = json.loads(cards_json_path.read_text())
    upgrades = cards_data.get("upgrades")
    if not isinstance(upgrades, dict):
        return 0, []

    failures: list[dict[str, object]] = []
    matched = 0

    for source_id, raw_upgrade_data in upgrades.items():
        if not isinstance(source_id, str) or not isinstance(raw_upgrade_data, dict):
            continue

        upgrade_data = raw_upgrade_data
        override_key = build_override_key("upgrade", source_id)
        faction = upgrade_data.get("faction")
        faction_dir = resolve_faction_dir(pdf_root, faction) if isinstance(faction, str) else None

        if not faction_dir:
            upgrade_data["pdf"] = ""
            failures.append(
                build_upgrade_failure_entry(
                    source_id,
                    upgrade_data,
                    f"Faction directory not found: {faction}",
                    manual_overrides.get(override_key, ""),
                )
            )
            continue

        search_dirs = iter_upgrade_search_dirs(upgrade_data, pdf_root, faction_dir)
        if not search_dirs:
            upgrade_data["pdf"] = ""
            failures.append(
                build_upgrade_failure_entry(
                    source_id,
                    upgrade_data,
                    "Keyword directory not found",
                    manual_overrides.get(override_key, ""),
                )
            )
            continue

        manual_override = manual_overrides.get(override_key, "")
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
                upgrade_data["pdf"] = build_pdf_storage_path(resolved_override, pdf_data_root)
                matched += 1
                failures.append(
                    build_upgrade_failure_entry(
                        source_id,
                        upgrade_data,
                        "Matched manually",
                        manual_override,
                    )
                )
                continue

            upgrade_data["pdf"] = ""
            failures.append(
                build_upgrade_failure_entry(
                    source_id,
                    upgrade_data,
                    f"Manual override did not resolve to a PDF: {manual_override}",
                    manual_override,
                )
            )
            continue

        keywords = [
            keyword
            for keyword in upgrade_data.get("keywords", [])
            if isinstance(keyword, str) and keyword.strip()
        ]
        name_candidates = build_upgrade_name_candidates(source_id, upgrade_data)
        best_match: Path | None = None
        best_score = -1

        for search_dir in search_dirs:
            for pdf_path in sorted(search_dir.glob("*.pdf")):
                score, _ = score_candidate(name_candidates, keywords, pdf_path.stem)
                if score > best_score:
                    best_score = score
                    best_match = pdf_path
                elif (
                    score == best_score
                    and score >= 0
                    and prefer_upgrade_pdf_candidate(pdf_path, best_match)
                ):
                    best_match = pdf_path

        if not best_match:
            upgrade_data["pdf"] = ""
            failures.append(
                build_upgrade_failure_entry(source_id, upgrade_data, "No matching PDF found")
            )
            continue

        upgrade_data["pdf"] = build_pdf_storage_path(best_match, pdf_data_root)
        matched += 1

    cards_json_path.write_text(json.dumps(cards_data, indent=4))
    return matched, failures


class Command(BaseCommand):
    help = (
        "Match model PDFs into the database plus crew-card and upgrade PDFs into "
        "backend/data/cards.json, then write unresolved/manual entries to "
        "backend/data/match_pdfs_failures.json."
    )

    def handle(self, *args, **options) -> None:
        backend_dir = Path(__file__).resolve().parents[3]
        cards_json_path = backend_dir / "data" / "cards.json"
        pdf_root = Path(settings.PDF_ROOT)
        report_path = backend_dir / "data" / "match_pdfs_failures.json"
        pdf_data_root = pdf_root.parent
        manual_overrides = load_manual_overrides(report_path)

        model_matched, model_failures = match_model_pdfs(
            pdf_root=pdf_root,
            pdf_data_root=pdf_data_root,
            manual_overrides=manual_overrides,
        )
        crew_card_matched, crew_card_failures = match_crew_card_pdfs(
            cards_json_path=cards_json_path,
            pdf_root=pdf_root,
            pdf_data_root=pdf_data_root,
            manual_overrides=manual_overrides,
        )
        upgrade_matched, upgrade_failures = match_upgrade_pdfs(
            cards_json_path=cards_json_path,
            pdf_root=pdf_root,
            pdf_data_root=pdf_data_root,
            manual_overrides=manual_overrides,
        )

        failures = model_failures + crew_card_failures + upgrade_failures
        report_path.write_text(json.dumps(failures, indent=2))

        self.stdout.write(
            self.style.SUCCESS(
                "Matched "
                f"{model_matched} model PDFs and "
                f"{crew_card_matched} crew-card PDFs and "
                f"{upgrade_matched} upgrade PDFs. "
                f"Failures: {len(failures)}. "
                f"Report written to {report_path}"
            )
        )
