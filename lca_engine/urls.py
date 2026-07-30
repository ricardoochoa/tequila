"""
URL Routing configuration for lca_engine app.
"""

from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path("inventory/", views.inventory_edit_view, name="inventory_edit"),
    path("benchmark/", views.benchmark_view, name="benchmark"),
    path("export/csv/", views.export_csv_view, name="export_csv"),
]
