"""Vercel serverless entry point: serves the Django API under /api/*.

The React build is served by Vercel as static files; vercel.json rewrites /api/* here.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from config.wsgi import application  # noqa: E402

app = application
