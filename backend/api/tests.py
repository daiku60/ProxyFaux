from io import BytesIO
from pathlib import Path

from django.test import override_settings
from pypdf import PdfReader, PdfWriter
from rest_framework.test import APIClient

from api.models import Model
from api.pdfs import (
    PAGE_HEIGHT,
    PAGE_WIDTH,
    build_overlay_page,
    clean_input_line,
    normalize_pdf_storage_path,
    parse_requested_models,
    resolve_pdf_placements,
)


def test_health_endpoint_returns_ok() -> None:
    response = APIClient().get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_frontend_root_returns_html_shell() -> None:
    response = APIClient().get("/")
    content = b"".join(response.streaming_content).decode()

    assert response.status_code == 200
    assert "text/html" in response["Content-Type"]
    assert '<script type="module" crossorigin src="/index.js"></script>' in content


def create_test_pdf(path: Path, *, width: float = 200, height: float = 300) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=width, height=height)
    writer.add_blank_page(width=width, height=height)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as pdf_file:
        writer.write(pdf_file)


def test_clean_input_line_skips_headers_and_group_labels() -> None:
    assert clean_input_line("(Arcanists)") == ""
    assert clean_input_line("Leader:") == ""
    assert clean_input_line("  Mara  ") == "Mara"
    assert clean_input_line("- Kaltgeist") == "Kaltgeist"


def test_parse_requested_models_supports_titles_and_repeated_variants(db) -> None:
    rasputina = Model.objects.create(
        source_id="rasputina",
        name="Rasputina",
        title="Abominable",
        faction="Arcanists",
        pdf="December/Rasputina.pdf",
    )
    kaltgeist = Model.objects.create(
        source_id="kaltgeist",
        name="Kaltgeist",
        faction="Arcanists",
        pdf="December/Kaltgeist_{A|B|C}.pdf",
    )

    requested = parse_requested_models(
        """
        (Arcanists)
        Leader:
          Rasputina, Abominable
        Hires:
          Kaltgeist
          Kaltgeist B
        """,
        [rasputina, kaltgeist],
    )

    assert [(entry.model.name, entry.variant) for entry in requested] == [
        ("Rasputina", None),
        ("Kaltgeist", None),
        ("Kaltgeist", "B"),
    ]


def test_create_pdf_endpoint_returns_a4_pdf_with_expected_page_count(db, tmp_path) -> None:
    pdf_root = tmp_path / "pdfs"
    generated_pdf_root = tmp_path / "generated-pdfs"

    create_test_pdf(pdf_root / "December" / "Rasputina.pdf", width=180, height=320)
    create_test_pdf(pdf_root / "December" / "Mara.pdf", width=220, height=300)
    create_test_pdf(pdf_root / "December" / "Kaltgeist_A.pdf", width=150, height=260)
    create_test_pdf(pdf_root / "December" / "Kaltgeist_B.pdf", width=140, height=270)
    create_test_pdf(pdf_root / "December" / "Kaltgeist_C.pdf", width=130, height=280)

    Model.objects.create(
        source_id="rasputina",
        name="Rasputina",
        title="Abominable",
        faction="Arcanists",
        pdf="December/Rasputina.pdf",
    )
    Model.objects.create(
        source_id="mara",
        name="Mara",
        faction="Arcanists",
        pdf="December/Mara.pdf",
    )
    Model.objects.create(
        source_id="kaltgeist",
        name="Kaltgeist",
        faction="Arcanists",
        pdf="December/Kaltgeist_{A|B|C}.pdf",
    )

    with override_settings(PDF_ROOT=pdf_root, GENERATED_PDF_ROOT=generated_pdf_root):
        response = APIClient().post(
            "/api/create-pdf/",
            {
                "text": """
                (Arcanists)
                Leader:
                  Rasputina, Abominable
                Totem(s):
                  Mara
                Hires:
                  Kaltgeist
                  Kaltgeist
                  Kaltgeist
                """,
                "border": False,
                "cut_lines": False,
            },
            format="json",
        )

        download_response = APIClient().get(response.json()["url"])

    assert response.status_code == 201
    assert response.json()["url"].endswith(".pdf")

    generated_files = list(generated_pdf_root.glob("*.pdf"))
    assert len(generated_files) == 1

    assert download_response.status_code == 200
    assert download_response["Content-Type"] == "application/pdf"

    reader = PdfReader(BytesIO(b"".join(download_response.streaming_content)))
    assert len(reader.pages) == 3
    assert round(float(reader.pages[0].mediabox.width), 4) == round(PAGE_WIDTH, 4)
    assert round(float(reader.pages[0].mediabox.height), 4) == round(PAGE_HEIGHT, 4)


def test_resolve_pdf_placements_uses_explicit_and_sequential_variants(db, tmp_path) -> None:
    pdf_root = tmp_path / "pdfs"
    create_test_pdf(pdf_root / "December" / "Kaltgeist_A.pdf")
    create_test_pdf(pdf_root / "December" / "Kaltgeist_B.pdf")
    create_test_pdf(pdf_root / "December" / "Kaltgeist_C.pdf")

    model = Model.objects.create(
        source_id="kaltgeist",
        name="Kaltgeist",
        faction="Arcanists",
        pdf="December/Kaltgeist_{A|B|C}.pdf",
    )

    requested = parse_requested_models(
        """
        Kaltgeist
        Kaltgeist C
        Kaltgeist
        """,
        [model],
    )

    with override_settings(PDF_ROOT=pdf_root):
        placements = resolve_pdf_placements(requested)

    assert [placement.source_path.name for placement in placements] == [
        "Kaltgeist_A.pdf",
        "Kaltgeist_C.pdf",
        "Kaltgeist_B.pdf",
    ]


def test_normalize_pdf_storage_path_accepts_relative_prefixed_and_absolute_paths(tmp_path) -> None:
    pdf_root = tmp_path / "pdfs"
    absolute = pdf_root / "Arcanists" / "December" / "Mara.pdf"

    assert normalize_pdf_storage_path(
        Path("Arcanists/December/Mara.pdf"),
        pdf_root,
    ) == absolute
    assert normalize_pdf_storage_path(
        Path("pdfs/Arcanists/December/Mara.pdf"),
        pdf_root,
    ) == absolute
    assert normalize_pdf_storage_path(absolute, pdf_root) == absolute


def test_build_overlay_page_respects_border_and_cut_line_flags() -> None:
    assert build_overlay_page(1, border=False, cut_lines=False) is None

    border_only = build_overlay_page(1, border=True, cut_lines=False)
    border_and_cut_lines = build_overlay_page(1, border=True, cut_lines=True)
    cut_lines_only = build_overlay_page(1, border=False, cut_lines=True)

    assert border_only is not None
    assert border_and_cut_lines is not None
    assert cut_lines_only is not None

    border_content = border_only.get_contents().get_data().decode("latin-1")
    border_and_cut_lines_content = border_and_cut_lines.get_contents().get_data().decode("latin-1")
    cut_lines_only_content = cut_lines_only.get_contents().get_data().decode("latin-1")

    assert " re" in border_content
    assert border_content.count(" m") == 0

    assert " re" in border_and_cut_lines_content
    assert border_and_cut_lines_content.count(" m") >= 8

    assert " re" not in cut_lines_only_content
    assert cut_lines_only_content.count(" m") >= 8


def test_create_pdf_endpoint_rejects_non_boolean_flags(db) -> None:
    response = APIClient().post(
        "/api/create-pdf/",
        {
            "text": "Mara",
            "border": "yes",
            "cut_lines": False,
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "The `border` field must be true or false."}
