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
        water_hotspots = [{"stage": "Glass Bottle", "water_score": 0.06, "pct": 12.5}]
        csv_str = generate_hotspot_csv(hotspots, water_hotspots)
        self.assertIn("Glass Bottle", csv_str)
        self.assertIn("Absolute GWP (kg CO2-eq)", csv_str)
        self.assertIn("AWARE Water (m3 world-eq)", csv_str)
        self.assertIn("GWP Contribution (%)", csv_str)
        self.assertIn("Water Contribution (%)", csv_str)

    def test_benchmark_view_status_code(self):
        response = self.client.get(reverse("benchmark"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tequila Class Comparative Benchmarking")

    def test_csv_upload_modes(self):
        # Verify CSVUploadForm contains upload_mode with choices
        from lca_engine.forms import CSVUploadForm
        form = CSVUploadForm()
        self.assertIn("upload_mode", form.fields)
        self.assertEqual(form.fields["upload_mode"].initial, "replace")

    def test_sankey_data_structure(self):
        calculator = TequilaBWCalculator()
        exchanges = [
            {"name": "Agave pineapple", "category": "Agave Reception", "query": "Cultivation of crops", "amount": 8.62, "unit": "kg", "location": "MX", "type": "technosphere"},
            {"name": "Fuel Oil (Cooking)", "category": "Cooking", "query": "Production of fuel oil", "amount": 0.806, "unit": "kg", "location": "", "type": "technosphere"}
        ]
        results = calculator.calculate_lca(exchanges)
        self.assertIn("sankey_data", results)
        self.assertIn("water_sankey_data", results)
        sankey = results["sankey_data"]
        self.assertIn("labels", sankey)
        self.assertIn("colors", sankey)
        self.assertIn("links", sankey)
        links = sankey["links"]
        self.assertIn("source", links)
        self.assertIn("target", links)
        self.assertIn("value", links)
        self.assertIn("color", links)
        self.assertEqual(len(links["source"]), len(links["target"]))
        self.assertEqual(len(links["source"]), len(links["value"]))
        self.assertEqual(len(links["source"]), len(links["color"]))
        
        # Verify indices are valid zero-indexed integers within labels range
        num_labels = len(sankey["labels"])
        for src, tgt in zip(links["source"], links["target"]):
            self.assertTrue(0 <= src < num_labels)
            self.assertTrue(0 <= tgt < num_labels)


