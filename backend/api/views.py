import mimetypes
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.http import FileResponse, Http404
from django.urls import reverse
from rest_framework.response import Response
from rest_framework.views import APIView

from api.pdfs import PdfCompositionError, compose_model_pdf


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
        if not isinstance(text, str) or not text.strip():
            return Response({"detail": "The `text` field is required."}, status=400)

        try:
            border = parse_bool_param(request.data.get("border"), field_name="border")
            cut_lines = parse_bool_param(
                request.data.get("cut_lines"),
                field_name="cut_lines",
            )
            sheet_size = parse_sheet_size_param(request.data.get("sheet_size"))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        try:
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
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
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
