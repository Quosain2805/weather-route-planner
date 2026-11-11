import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def clear_cache():
    """Route/weather/throttle state lives in the cache; start every test clean."""
    cache.clear()
    yield
    cache.clear()
