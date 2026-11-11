from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import AnalyzeRequestSerializer
from .services import analysis, geocoding


class HealthView(APIView):
    def get(self, request):
        return Response({"status": "ok"})


class GeocodeView(APIView):
    """GET /api/geocode?q=chicago -> [{label, lat, lon}]"""

    throttle_scope = "geocode"

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if len(query) < 3:
            return Response([])
        if len(query) > 200:
            return Response(
                {"error": {"code": "invalid_query", "message": "Search text is too long."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(geocoding.search(query))


class AnalyzeView(APIView):
    """POST /api/analyze -> three scored routes, checkpoints and heatmap data."""

    throttle_scope = "analyze"

    def post(self, request):
        serializer = AnalyzeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        trip = analysis.TripRequest(
            origin=(data["origin"]["lat"], data["origin"]["lon"]),
            destination=(data["destination"]["lat"], data["destination"]["lon"]),
            departure_epoch=int(data["departure"].timestamp()),
            load_lb=data["load_lb"],
            interval_mi=data["interval_miles"],
        )
        return Response(analysis.analyze(trip))
