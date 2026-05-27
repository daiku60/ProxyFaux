from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):  # type: ignore[override]
        return Response({"status": "ok"})

