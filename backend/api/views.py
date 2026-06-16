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
            pdf_bytes = compose_model_pdf(text)
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
