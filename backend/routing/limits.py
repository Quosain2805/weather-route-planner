"""Limits shared by request validation and departure planning."""
from datetime import timedelta

MAX_DEPARTURE_AHEAD = timedelta(days=7)   # forecasts only reach about this far
MAX_DEPARTURE_PAST = timedelta(hours=1)
