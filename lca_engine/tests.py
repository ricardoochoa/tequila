"""
Django unit tests for lca_engine models, views, and services.
"""

from django.test import TestCase, Client
from django.urls import reverse
from lca_engine.models import InventoryScenario, InventoryExchange
from lca_engine.services.bw_calculator import TequilaBWCalculator
from lca_engine.services.csv_handler import generate_hotspot_csv


class LCAEngineTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.scenario = InventoryScenario.objects.create(
            name="Test Scenario",
            description="Testing Tequila LCA"
        )
        InventoryExchange.objects.create(
            scenario=self.scenario,
            stage_name="Test Bottling",
            category="Packaging",
            query="Manufacture of glass",
            amount=0.55,
            unit="kg",
            location="MX",
            exchange_type="technosphere"
        )

    def test_dashboard_view_status_code(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tequila LCA Studio")

    def test_inventory_edit_view(self):
        response = self.client.get(reverse("inventory_edit"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inventory Management")

    def test_export_csv_view(self):
        response = self.client.get(reverse("export_csv"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")

    def test_hotspot_csv_generator(self):
        hotspots = [{"stage": "Glass Bottle", "gwp_score": 0.42, "pct": 45.2}]
        csv_str = generate_hotspot_csv(hotspots)
        self.assertIn("Glass Bottle", csv_str)
        self.assertIn("Absolute GWP", csv_str)
