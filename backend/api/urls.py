from django.urls import path

from api.views import CardImageView, CreatePdfView, GeneratedPdfDownloadView, HealthView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("create-pdf/", CreatePdfView.as_view(), name="create-pdf"),
    path("card-images/<path:relative_path>", CardImageView.as_view(), name="card-image"),
    path(
        "generated-pdfs/<str:filename>",
        GeneratedPdfDownloadView.as_view(),
        name="generated-pdf-download",
    ),
]
