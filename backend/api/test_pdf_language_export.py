from io import BytesIO
from pathlib import Path

from django.test import override_settings
from pypdf import PdfReader, PdfWriter
from rest_framework.test import APIClient

from api.models import Model
from api.pdfs import resolve_pdf_path_and_variants


def create_test_pdf(path: Path, *, width: float = 200, height: float = 300) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=width, height=height)
    writer.add_blank_page(width=width, height=height)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as pdf_file:
        writer.write(pdf_file)


def test_resolve_pdf_path_and_variants_uses_language_specific_root(tmp_path) -> None:
    pdf_data_root = tmp_path / "data"
    english_pdf = pdf_data_root / "en" / "pdfs" / "Neverborn" / "Woe" / "Candy.pdf"
    spanish_pdf = pdf_data_root / "es" / "pdfs" / "Neverborn" / "Woe" / "Candy.pdf"
    create_test_pdf(english_pdf)
    create_test_pdf(spanish_pdf)

    with override_settings(PDF_DATA_ROOT=pdf_data_root, PDF_ROOT=english_pdf.parent.parent.parent):
        resolved_path, variants = resolve_pdf_path_and_variants(
            "pdfs/Neverborn/Woe/Candy.pdf",
            language="es",
        )

    assert resolved_path == spanish_pdf
    assert variants == []


def test_create_pdf_endpoint_exports_selected_cards_in_spanish_when_available(db, tmp_path) -> None:
    pdf_data_root = tmp_path / "data"
    generated_pdf_root = tmp_path / "generated-pdfs"
    english_pdf = pdf_data_root / "en" / "pdfs" / "Neverborn" / "Woe" / "Candy.pdf"
    spanish_pdf = pdf_data_root / "es" / "pdfs" / "Neverborn" / "Woe" / "Candy.pdf"
    create_test_pdf(english_pdf, width=180, height=320)
    create_test_pdf(spanish_pdf, width=190, height=330)

    Model.objects.create(
        source_id="candy",
        name="Candy",
        faction="Neverborn",
        pdf="pdfs/Neverborn/Woe/Candy.pdf",
    )

    with override_settings(
        PDF_DATA_ROOT=pdf_data_root,
        PDF_ROOT=pdf_data_root / "en" / "pdfs",
        GENERATED_PDF_ROOT=generated_pdf_root,
    ):
        response = APIClient().post(
            "/api/create-pdf/",
            {
                "selected_cards": [
                    {
                        "kind": "model",
                        "label": "Candy",
                        "language": "es",
                        "source_id": "candy",
                    }
                ],
                "sheet_size": "a4",
            },
            format="json",
        )
        download_response = APIClient().get(response.json()["url"])

    assert response.status_code == 201
    assert download_response.status_code == 200
    reader = PdfReader(BytesIO(b"".join(download_response.streaming_content)))
    assert len(reader.pages) == 1


def test_create_pdf_endpoint_rejects_missing_spanish_card(db, tmp_path) -> None:
    pdf_data_root = tmp_path / "data"
    generated_pdf_root = tmp_path / "generated-pdfs"
    english_pdf = pdf_data_root / "en" / "pdfs" / "Neverborn" / "Woe" / "Candy.pdf"
    create_test_pdf(english_pdf)

    Model.objects.create(
        source_id="candy",
        name="Candy",
        faction="Neverborn",
        pdf="pdfs/Neverborn/Woe/Candy.pdf",
    )

    with override_settings(
        PDF_DATA_ROOT=pdf_data_root,
        PDF_ROOT=pdf_data_root / "en" / "pdfs",
        GENERATED_PDF_ROOT=generated_pdf_root,
    ):
        response = APIClient().post(
            "/api/create-pdf/",
            {
                "selected_cards": [
                    {
                        "kind": "model",
                        "label": "Candy",
                        "language": "es",
                        "source_id": "candy",
                    }
                ],
            },
            format="json",
        )

    assert response.status_code == 400
    assert "Missing PDF for Candy" in response.json()["detail"]


def test_create_pdf_endpoint_falls_back_to_cards_json_for_upgrade_selected_from_preview(
    db,
    tmp_path,
    settings,
) -> None:
    pdf_data_root = tmp_path / "data"
    generated_pdf_root = tmp_path / "generated-pdfs"
    cards_json_path = pdf_data_root / "cards.json"
    english_pdf = pdf_data_root / "en" / "pdfs" / "Neverborn" / "Chimera" / "ArmoredPlating.pdf"
    create_test_pdf(english_pdf)
    cards_json_path.parent.mkdir(parents=True, exist_ok=True)
    cards_json_path.write_text(
        """
        {
          "models": {},
          "crewCards": {},
          "upgrades": {
            "ArmoredPlating": {
              "name": "Armored Plating",
              "faction": "Neverborn",
              "pdf": "pdfs/Neverborn/Chimera/ArmoredPlating.pdf",
              "text": "Armored Plating",
              "keywords": ["Chimera"],
              "tokens": [],
              "files": {
                "versions": [
                  {
                    "displayName": "Armored Plating"
                  }
                ]
              }
            }
          }
        }
        """
    )
    settings.BASE_DIR = tmp_path

    with override_settings(
        PDF_DATA_ROOT=pdf_data_root,
        PDF_ROOT=pdf_data_root / "en" / "pdfs",
        GENERATED_PDF_ROOT=generated_pdf_root,
    ):
        response = APIClient().post(
            "/api/create-pdf/",
            {
                "selected_cards": [
                    {
                        "kind": "upgrade",
                        "label": "Armored Plating",
                        "language": "en",
                        "source_id": "ArmoredPlating",
                    }
                ],
            },
            format="json",
        )

    assert response.status_code == 201
