import posixpath
from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.utils._os import safe_join
from django.views.generic.base import RedirectView
from django.views.static import serve as static_serve


def serve_react(request, path, document_root=None):
    path = posixpath.normpath(path).lstrip("/")
    fullpath = Path(safe_join(document_root, path))
    if fullpath.is_file():
        return static_serve(request, path, document_root)
    return static_serve(request, "index.html", document_root)


urlpatterns = [
    path(
        "",
        RedirectView.as_view(url="/dashboard/", permanent=False),
        name="root-redirect",
    ),
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    re_path(
        r"^dashboard/(?P<path>.*)$",
        serve_react,
        {"document_root": str(settings.FRONTEND_DIST_DIR)},
    ),
]
