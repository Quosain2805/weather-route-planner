from django.urls import path

from . import views

urlpatterns = [
    path("health", views.HealthView.as_view()),
    path("geocode", views.GeocodeView.as_view()),
    path("analyze", views.AnalyzeView.as_view()),
]
