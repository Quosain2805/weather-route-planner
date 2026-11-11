from __future__ import annotations

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from .domain.geo import haversine_mi
from .limits import MAX_DEPARTURE_AHEAD, MAX_DEPARTURE_PAST

MAX_LOAD_LB = 80_000          # US federal gross vehicle weight limit
MIN_TRIP_MI = 1.0


class PointSerializer(serializers.Serializer):
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)
    label = serializers.CharField(required=False, allow_blank=True, max_length=300)


class AnalyzeRequestSerializer(serializers.Serializer):
    origin = PointSerializer()
    destination = PointSerializer()
    departure = serializers.DateTimeField()
    load_lb = serializers.IntegerField(min_value=0, max_value=MAX_LOAD_LB)
    interval_miles = serializers.IntegerField(default=25)

    def validate_departure(self, value):
        if timezone.is_naive(value):
            value = timezone.make_aware(value, timezone.utc)
        now = timezone.now()
        if value < now - MAX_DEPARTURE_PAST:
            raise serializers.ValidationError("Departure can't be in the past.")
        if value > now + MAX_DEPARTURE_AHEAD:
            raise serializers.ValidationError("Forecasts only reach about 7 days ahead; pick an earlier departure.")
        return value

    def validate_interval_miles(self, value):
        if value not in settings.ALLOWED_INTERVALS_MI:
            options = ", ".join(map(str, settings.ALLOWED_INTERVALS_MI))
            raise serializers.ValidationError(f"Choose one of: {options} miles.")
        return value

    def validate(self, attrs):
        o, d = attrs["origin"], attrs["destination"]
        if haversine_mi((o["lat"], o["lon"]), (d["lat"], d["lon"])) < MIN_TRIP_MI:
            raise serializers.ValidationError("Origin and destination are too close together to plan a route.")
        return attrs
