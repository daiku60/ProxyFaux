from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from pypdf import PdfReader, PdfWriter


def create_test_pdf_with_page_count(
    path: Path,
    page_count: int,
    *,
    width: float = 200,
    height: float = 300,
) -> None:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=width, height=height)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as pdf_file:
        writer.write(pdf_file)


def test_split_pdf_pairs_command_splits_after_skipping_first_page(tmp_path) -> None:
    input_pdf = tmp_path / "source.pdf"
    output_dir = tmp_path / "output"
    create_test_pdf_with_page_count(input_pdf, 5)

    call_command(
        "split_pdf_pairs",
        str(input_pdf),
        str(output_dir),
        prefix="card",
    )

    generated_files = sorted(output_dir.glob("*.pdf"))
    assert [path.name for path in generated_files] == ["card_001.pdf", "card_002.pdf"]

    for generated_file in generated_files:
        reader = PdfReader(str(generated_file))
        assert len(reader.pages) == 2


def test_split_pdf_pairs_command_errors_on_even_page_count(tmp_path) -> None:
    input_pdf = tmp_path / "source.pdf"
    output_dir = tmp_path / "output"
    create_test_pdf_with_page_count(input_pdf, 4)

    with pytest.raises(CommandError, match="Expected an odd number of pages"):
        call_command("split_pdf_pairs", str(input_pdf), str(output_dir))
