import json
import re
from pathlib import Path


VARIANT_PATTERN = re.compile(r"\{([A-Z](?:\|[A-Z])*)\}")


def main() -> None:
    root_dir = Path(__file__).resolve().parents[2]
    cards_data_path = root_dir / "backend" / "data" / "cards.json"
    backend_data_dir = root_dir / "backend" / "data"
    output_path = root_dir / "frontend" / ".generated" / "language-availability.json"

    raw_catalog = json.loads(cards_data_path.read_text())
    all_entries = {
        **raw_catalog.get("models", {}),
        **raw_catalog.get("crewCards", {}),
        **raw_catalog.get("upgrades", {}),
    }
    availability_entries = {
        entry_id: build_language_availability_entry(entry.get("pdf"), backend_data_dir)
        for entry_id, entry in all_entries.items()
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(availability_entries, indent=2))
    print(f"Wrote {output_path}")


def build_language_availability_entry(
    pdf_path: str | None,
    backend_data_dir: Path,
) -> dict[str, object]:
    if not pdf_path:
        return {"default": ["en"]}

    variant_match = VARIANT_PATTERN.search(pdf_path)
    if not variant_match:
        return {"default": collect_available_languages(pdf_path, backend_data_dir)}

    variants = variant_match.group(1).split("|")
    return {
        "default": ["en"],
        "variants": {
            variant: collect_available_languages(
                VARIANT_PATTERN.sub(variant, pdf_path),
                backend_data_dir,
            )
            for variant in variants
        },
    }


def collect_available_languages(pdf_path: str, backend_data_dir: Path) -> list[str]:
    languages = [
        language
        for language in ("en", "es")
        if (backend_data_dir / language / pdf_path).exists()
    ]
    return languages or ["en"]


if __name__ == "__main__":
    main()
