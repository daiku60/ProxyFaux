from django.urls import path

from api.views import HealthView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
]

