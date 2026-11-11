"""Django settings. Everything environment-specific comes from environment variables."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG", False)
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or (
    "dev-only-insecure-key" if DEBUG else None
)
if not SECRET_KEY:
    raise RuntimeError("Set DJANGO_SECRET_KEY (or DJANGO_DEBUG=1 for local development).")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "")
# Hostnames the hosting platform assigns (Render, Vercel production/preview URLs).
for _host_var in ("RENDER_EXTERNAL_HOSTNAME", "VERCEL_URL", "VERCEL_BRANCH_URL", "VERCEL_PROJECT_PRODUCTION_URL"):
    if _host := os.environ.get(_host_var):
        ALLOWED_HOSTS.append(_host)
if os.environ.get("VERCEL"):
    # A Vercel project is reachable on several generated *.vercel.app aliases (deployment, branch,
    # team); only traffic for this project is routed here, so trust the whole suffix.
    ALLOWED_HOSTS.append(".vercel.app")

INSTALLED_APPS = [
    # DRF's request/throttle machinery imports the auth models (AnonymousUser) even though we
    # have no users; these two apps satisfy that without any database tables being used.
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "corsheaders",
    "rest_framework",
    "routing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",  # DRF views are exempt; this guards anything else
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# The service is stateless (no users, no stored data), so no database is configured.
DATABASES: dict = {}

USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---- static files / the built React app ------------------------------------------------------
FRONTEND_DIST = BASE_DIR / "frontend_dist"
if FRONTEND_DIST.is_dir():
    # Serve the Vite build from the site root (index.html at "/").
    WHITENOISE_ROOT = FRONTEND_DIST
    WHITENOISE_INDEX_FILE = True

# ---- CORS (only needed when the Vite dev server runs on a different port) --------------------
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
CORS_URLS_REGEX = r"^/api/.*$"

# ---- DRF -------------------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "routing.exceptions.api_exception_handler",
    # Protects the free third-party APIs we depend on from a runaway client.
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"analyze": "30/min", "geocode": "120/min"},
    "NUM_PROXIES": int(os.environ.get("NUM_PROXIES", "1")),
}

# ---- caching ---------------------------------------------------------------------------------
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "wx"}}

# ---- third-party services (all free, no API keys) --------------------------------------------
OUTBOUND_USER_AGENT = os.environ.get(
    "OUTBOUND_USER_AGENT", "weather-route-planner/1.0 (assessment project)"
)
OSRM_URL = os.environ.get("OSRM_URL", "https://router.project-osrm.org").rstrip("/")
# The free endpoint needs no key but is rate limited (~5,000 locations/hour). Setting
# OPEN_METEO_API_KEY switches to the commercial endpoint with the same API.
OPEN_METEO_API_KEY = os.environ.get("OPEN_METEO_API_KEY", "")
OPEN_METEO_URL = os.environ.get(
    "OPEN_METEO_URL",
    "https://customer-api.open-meteo.com/v1/forecast" if OPEN_METEO_API_KEY else "https://api.open-meteo.com/v1/forecast",
)
PHOTON_URL = os.environ.get("PHOTON_URL", "https://photon.komoot.io/api/")
NOMINATIM_URL = os.environ.get("NOMINATIM_URL", "https://nominatim.openstreetmap.org/search")

# ---- domain tuning ---------------------------------------------------------------------------
ALLOWED_INTERVALS_MI = (10, 25, 50)
MAX_CHECKPOINTS_PER_ROUTE = 130
WEATHER_GRID_DEG = 0.1           # lookups snap to this grid (~7 mi), about the resolution of the forecast models
WEATHER_FORECAST_DAYS = 12       # departures up to 7 days out + trip length + 48 h heatmap
WEATHER_CACHE_TTL_S = 45 * 60    # the model data refreshes hourly
ROUTE_CACHE_TTL_S = 60 * 60
GEOCODE_CACHE_TTL_S = 24 * 60 * 60

# ---- production hardening --------------------------------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SECURE_REDIRECT_EXEMPT = [r"^api/health$"]
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_CONTENT_TYPE_NOSNIFF = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}
