from django.conf import settings
from django.http import FileResponse, Http404
from django.views import View


class FrontendAppView(View):
    def get(self, request, *args, **kwargs):  # type: ignore[override]
        index_path = settings.FRONTEND_DIST_DIR / "index.html"
        if not index_path.exists():
            raise Http404("Frontend build not found.")
        return FileResponse(index_path.open("rb"), content_type="text/html")


class FrontendAssetView(View):
    def get(self, request, asset_path: str, *args, **kwargs):  # type: ignore[override]
        file_path = settings.FRONTEND_DIST_DIR / asset_path
        if not file_path.exists() or not file_path.is_file():
            raise Http404("Frontend asset not found.")
        return FileResponse(file_path.open("rb"))
