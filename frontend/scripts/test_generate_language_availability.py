from pathlib import Path

from generate_language_availability import collect_available_languages


def test_collect_available_languages_accepts_either_pdf_revision(
    tmp_path: Path,
) -> None:
    pdf_path = "pdfs/Neverborn/Woe/Candy.pdf"
    english_pdf = tmp_path / "en" / "v0" / pdf_path
    spanish_pdf = tmp_path / "es" / "v1" / pdf_path
    english_pdf.parent.mkdir(parents=True)
    spanish_pdf.parent.mkdir(parents=True)
    english_pdf.touch()
    spanish_pdf.touch()

    assert collect_available_languages(pdf_path, tmp_path) == ["en", "es"]
