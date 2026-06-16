from django.urls import path

from api.views import CreatePdfView, GeneratedPdfDownloadView, HealthView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("create-pdf/", CreatePdfView.as_view(), name="create-pdf"),
    path(
        "generated-pdfs/<str:filename>",
        GeneratedPdfDownloadView.as_view(),
        name="generated-pdf-download",
    ),
]
