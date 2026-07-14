import json
import mimetypes
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.http import FileResponse, Http404
from django.urls import reverse
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import CrewCard, Model, Upgrade
from api.pdfs import (
    PdfCompositionError,
    RequestedCard,
    compose_model_pdf,
    compose_selected_cards_pdf,
)


class HealthView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):  # type: ignore[override]
        return Response({"status": "ok"})


class CreatePdfView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):  # type: ignore[override]
        text = request.data.get("text")
        selected_cards_data = request.data.get("selected_cards")

        if selected_cards_data is None:
            if not isinstance(text, str) or not text.strip():
                return Response({"detail": "The `text` field is required."}, status=400)
        elif not isinstance(selected_cards_data, list) or len(selected_cards_data) == 0:
            return Response(
                {"detail": "The `selected_cards` field must be a non-empty list."},
                status=400,
            )

        try:
            border = parse_bool_param(request.data.get("border"), field_name="border")
            cut_lines = parse_bool_param(
                request.data.get("cut_lines"),
                field_name="cut_lines",
            )
            sheet_size = parse_sheet_size_param(request.data.get("sheet_size"))
            selected_cards = parse_selected_cards_param(selected_cards_data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        try:
            if selected_cards is not None:
                pdf_bytes = compose_selected_cards_pdf(
                    selected_cards,
                    border=border,
                    cut_lines=cut_lines,
                    sheet_size=sheet_size,
                )
            else:
                pdf_bytes = compose_model_pdf(
                    text,
                    border=border,
                    cut_lines=cut_lines,
                    sheet_size=sheet_size,
                )
        except PdfCompositionError as exc:
            return Response({"detail": str(exc)}, status=400)

        settings.GENERATED_PDF_ROOT.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid4()}.pdf"
        output_path = settings.GENERATED_PDF_ROOT / filename
        output_path.write_bytes(pdf_bytes)

        pdf_url = request.build_absolute_uri(
            reverse("generated-pdf-download", kwargs={"filename": filename})
        )
        return Response({"url": pdf_url}, status=201)


class GeneratedPdfDownloadView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, filename: str):  # type: ignore[override]
        if Path(filename).name != filename or not filename.endswith(".pdf"):
            raise Http404

        file_path = settings.GENERATED_PDF_ROOT / filename
        if not file_path.exists() or not file_path.is_file():
            raise Http404

        response = FileResponse(file_path.open("rb"), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        return response


class CardImageView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, relative_path: str):  # type: ignore[override]
        normalized_relative_path = Path(relative_path)
        if (
            normalized_relative_path.is_absolute()
            or not normalized_relative_path.parts
            or normalized_relative_path.parts[0] != "cards"
            or ".." in normalized_relative_path.parts
        ):
            raise Http404

        file_path = settings.BASE_DIR / "data" / normalized_relative_path
        if not file_path.exists() or not file_path.is_file():
            raise Http404

        content_type, _ = mimetypes.guess_type(str(file_path))
        response = FileResponse(
            file_path.open("rb"),
            content_type=content_type or "application/octet-stream",
        )
        return response


def parse_bool_param(value, *, field_name: str) -> bool:
    if value is None:
        return False

    if isinstance(value, bool):
        return value

    raise ValueError(f"The `{field_name}` field must be true or false.")


def parse_sheet_size_param(value) -> str:
    if value is None:
        return "a4"

    if isinstance(value, str) and value.lower() in {"a4", "letter"}:
        return value.lower()

    raise ValueError("The `sheet_size` field must be `a4` or `letter`.")


def parse_selected_cards_param(value) -> list[RequestedCard] | None:
    if value is None:
        return None

    if not isinstance(value, list) or len(value) == 0:
        raise ValueError("The `selected_cards` field must be a non-empty list.")

    requested_cards: list[RequestedCard] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("Each `selected_cards` entry must be an object.")

        kind = item.get("kind")
        source_id = item.get("source_id")
        label = item.get("label")
        language = item.get("language", "en")
        variant = item.get("variant")

        if kind not in {"model", "crewCard", "upgrade"}:
            raise ValueError("Each `selected_cards.kind` must be `model`, `crewCard`, or `upgrade`.")
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError("Each `selected_cards.source_id` must be a non-empty string.")
        if not isinstance(label, str) or not label.strip():
            raise ValueError("Each `selected_cards.label` must be a non-empty string.")
        if not isinstance(language, str) or language not in {"en", "es"}:
            raise ValueError("Each `selected_cards.language` must be `en` or `es`.")
        if variant is not None and not isinstance(variant, str):
            raise ValueError("Each `selected_cards.variant` must be a string or null.")

        card = resolve_card_by_kind_and_source_id(kind, source_id)
        if card is None:
            raise ValueError(f"Card not found for {kind}:{source_id}.")

        requested_cards.append(
            RequestedCard(
                raw_name=label,
                card=card,
                variant=variant,
                language=language,
            )
        )

    return requested_cards


def resolve_card_by_kind_and_source_id(
    kind: str,
    source_id: str,
) -> Model | CrewCard | Upgrade | None:
    if kind == "model":
        return Model.objects.filter(source_id=source_id).first() or build_card_from_catalog(
            kind,
            source_id,
        )
    if kind == "crewCard":
        return CrewCard.objects.filter(source_id=source_id).first() or build_card_from_catalog(
            kind,
            source_id,
        )
    return Upgrade.objects.filter(source_id=source_id).first() or build_card_from_catalog(
        kind,
        source_id,
    )


def build_card_from_catalog(
    kind: str,
    source_id: str,
) -> Model | CrewCard | Upgrade | None:
    cards_json_path = settings.BASE_DIR / "data" / "cards.json"
    if not cards_json_path.exists():
        return None

    cards_data = json.loads(cards_json_path.read_text())
    section_name = {
        "model": "models",
        "crewCard": "crewCards",
        "upgrade": "upgrades",
    }[kind]
    raw_section = cards_data.get(section_name)
    if not isinstance(raw_section, dict):
        return None

    payload = raw_section.get(source_id)
    if not isinstance(payload, dict):
        return None

    if kind == "model":
        return Model(
            source_id=source_id,
            name=payload.get("name", ""),
            faction=payload.get("faction", ""),
            pdf=payload.get("pdf", ""),
            station=payload.get("station", ""),
            text=payload.get("text", ""),
            title=payload.get("title", ""),
            crew_card=payload.get("crewCard", ""),
            totem_id=payload.get("totemId", ""),
            characteristics=payload.get("characteristics", []),
            keywords=payload.get("keywords", []),
            tokens=payload.get("tokens", []),
            alternates=payload.get("alternates", []),
            meta=payload.get("meta", {}),
            files=payload.get("files", {}),
            stats=payload.get("stats", {}),
        )

    if kind == "crewCard":
        return CrewCard(
            source_id=source_id,
            name=payload.get("name", ""),
            faction=payload.get("faction", ""),
            pdf=payload.get("pdf", ""),
            text=payload.get("text", ""),
            keywords=payload.get("keywords", []),
            tokens=payload.get("tokens", []),
            files=payload.get("files", {}),
        )

    return Upgrade(
        source_id=source_id,
        name=payload.get("name", ""),
        faction=payload.get("faction", ""),
        pdf=payload.get("pdf", ""),
        text=payload.get("text", ""),
        keywords=payload.get("keywords", []),
        tokens=payload.get("tokens", []),
        files=payload.get("files", {}),
    )
