"""
Django unit tests for lca_engine models, views, dynamic forms, and 3-Tier LCA calculation services.
"""

import io
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from lca_engine.models import InventoryScenario, FallbackEmissionFactor
from lca_engine.forms import DynamicInventoryForm, CSVUploadForm
from lca_engine.services.bw_calculator import TequilaBWCalculator
from lca_engine.services.csv_handler import generate_hotspot_csv, generate_lci_template_csv, parse_key_value_lci_csv
from lca_engine.services.inventory_mapper import load_inventory_map, get_default_captured_payload
from lca_engine.views import get_or_create_default_producer_and_product


class LCAEngineTests(TestCase):

    def setUp(self):
        self.client = Client()
        call_command("seed_fallbacks")
        self.scenario = get_or_create_default_producer_and_product()

    def test_seed_fallbacks_management_command(self):
        count = FallbackEmissionFactor.objects.count()
        self.assertGreaterEqual(count, 10)
        n_factor = FallbackEmissionFactor.objects.get(django_field="fertilizer_n_kg", reporting_year=2021)
        self.assertEqual(n_factor.emission_factor, 8.13)

    def test_fallback_emission_factor_unique_together_with_indicator(self):
        # Unique together is ("django_field", "reporting_year", "indicator")
        # municipal_water_m3 (2021, GWP100) already exists from seed_fallbacks. Adding AWARE for the same year:
        aware_obj = FallbackEmissionFactor.objects.create(
            django_field="municipal_water_m3",
            reporting_year=2021,
            emission_factor=42.1,
            unit="m3 eq / m3",
            indicator="AWARE",
            source_reference="WULCA AWARE"
        )
        count = FallbackEmissionFactor.objects.filter(django_field="municipal_water_m3", reporting_year=2021).count()
        self.assertEqual(count, 2)
        self.assertEqual(aware_obj.indicator, "AWARE")

    def test_gwp_and_aware_indicator_isolation(self):
        calculator = TequilaBWCalculator()
        payload = get_default_captured_payload()
        results = calculator.calculate_lca(payload, enable_exiobase=False)

        # Evapotranspiration has AWARE factor 421.0 but NO GWP100 factor
        et_gwp = next((h["gwp_score"] for h in results["hotspots"] if "Evapotranspiración" in h["stage"] or "evapotranspiration_mm" in h["stage"]), None)
        et_water = next((wh["water_score"] for wh in results["water_hotspots"] if "Evapotranspiración" in wh["stage"] or "evapotranspiration_mm" in wh["stage"]), None)

        self.assertEqual(et_gwp, 0.0)
        self.assertIsNotNone(et_water)
        self.assertGreater(et_water, 0.0)

    def test_intermediate_variables_direct_impact_zero(self):
        calculator = TequilaBWCalculator()
        payload = get_default_captured_payload()
        results = calculator.calculate_lca(payload, enable_exiobase=False)

        agave_gwp = next((h["gwp_score"] for h in results["hotspots"] if "Agave" in h["stage"] or "agave_harvested_ton" in h["stage"]), None)
        area_gwp = next((h["gwp_score"] for h in results["hotspots"] if "Área" in h["stage"] or "cultivated_area" in h["stage"]), None)

        self.assertEqual(agave_gwp, 0.0)
        self.assertEqual(area_gwp, 0.0)

    def test_inventory_map_loader(self):
        inv_map = load_inventory_map()
        self.assertIn("AgriculturalPhase", inv_map)
        self.assertIn("IndustrialPhase", inv_map)
        self.assertIn("WaterResource", inv_map)
        self.assertIn("WasteManagement", inv_map)

    def test_dynamic_inventory_form(self):
        payload = get_default_captured_payload()
        form = DynamicInventoryForm(payload=payload)
        self.assertIn("agave_harvested_ton", form.fields)
        self.assertIn("agave_harvested_ton_tier1", form.fields)

        categorized = form.get_categorized_fields()
        self.assertGreater(len(categorized), 0)

    def test_dashboard_view_status_code(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tequila LCA Studio")

    def test_dashboard_exiobase_toggle_off(self):
        response = self.client.get(reverse("dashboard"), {"functional_unit": "700.0", "glass_recycling_rate": "12"})
        self.assertEqual(response.status_code, 200)
        results = response.context["results"]
        self.assertFalse(results["enable_exiobase"])
        self.assertIn("Tier 3", results["db_mode"])

    def test_dashboard_exiobase_toggle_on(self):
        response = self.client.get(reverse("dashboard"), {"functional_unit": "700.0", "enable_exiobase": "on"})
        self.assertEqual(response.status_code, 200)
        results = response.context["results"]
        self.assertTrue(results["enable_exiobase"])

    def test_inventory_edit_view(self):
        response = self.client.get(reverse("inventory_edit"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inventory Management")

    def test_download_lci_template_view(self):
        response = self.client.get(reverse("download_lci_template"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("attachment; filename=", response["Content-Disposition"])
        content = response.content.decode("utf-8")
        self.assertIn("Nombre_Variable,Valor,Unidades,Notas", content)
        self.assertIn("agri_diesel_liters", content)

    def test_parse_key_value_lci_csv_valid(self):
        csv_data = (
            "Nombre_Variable,Valor,Unidades,Notas\n"
            "reporting_year,2025,Año,Año fiscal\n"
            "agri_diesel_liters,12000.0,L,Diésel campo\n"
            "vinasse_treatment,Planta de Tratamiento Aerobia,Texto,PTA\n"
            "bagasse_boiler_pct,80.0,%,Quema\n"
            "bagasse_compost_pct,20.0,%,Compostaje\n"
        )
        file_obj = io.BytesIO(csv_data.encode("utf-8"))
        payload, errors = parse_key_value_lci_csv(file_obj)
        self.assertEqual(len(errors), 0)
        self.assertEqual(payload["agri_diesel_liters"]["amount"], 12000.0)
        self.assertEqual(payload["vinasse_treatment"]["amount"], "aerobic")

    def test_parse_key_value_lci_csv_validation_errors(self):
        csv_data = (
            "Nombre_Variable,Valor,Unidades,Notas\n"
            "invalid_unknown_var,100.0,kg,Unknown field\n"
            "fertilizer_n_kg,invalid_string_val,kg,Invalid float\n"
            "bagasse_boiler_pct,80.0,%,Quema\n"
            "bagasse_compost_pct,30.0,%,Over 100%\n"
        )
        file_obj = io.BytesIO(csv_data.encode("utf-8"))
        payload, errors = parse_key_value_lci_csv(file_obj)
        self.assertGreaterEqual(len(errors), 3)

    def test_key_value_csv_upload_integration(self):
        csv_data = (
            "Nombre_Variable,Valor,Unidades,Notas\n"
            "agri_diesel_liters,15000.0,L,Diésel\n"
            "grid_electricity_kwh,900000.0,kWh,CFE\n"
        )
        file = SimpleUploadedFile("lci_test.csv", csv_data.encode("utf-8"), content_type="text/csv")
        response = self.client.post(reverse("inventory_edit"), {
            "upload_csv": "1",
            "csv_file": file,
            "upload_mode": "replace"
        })
        self.assertEqual(response.status_code, 302)
        self.scenario.refresh_from_db()
        self.assertEqual(self.scenario.captured_payload["agri_diesel_liters"]["amount"], 15000.0)

    def test_export_csv_view(self):
        response = self.client.get(reverse("export_csv"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")

    def test_export_csv_inherits_exiobase_state(self):
        response_off = self.client.get(reverse("export_csv"), {"functional_unit": "750.0", "glass_recycling_rate": "15"})
        self.assertEqual(response_off.status_code, 200)
        csv_text_off = response_off.content.decode("utf-8")
        self.assertIn("Tier 3 (Fallback)", csv_text_off)

    def test_hotspot_csv_generator(self):
        hotspots = [{"stage": "Glass Bottle", "gwp_score": 0.42, "pct": 45.2, "data_tier": "Tier 2 (EXIOBASE)"}]
        water_hotspots = [{"stage": "Glass Bottle", "water_score": 0.06, "pct": 12.5, "data_tier": "Tier 1 (Supplier)"}]
        csv_str = generate_hotspot_csv(hotspots, water_hotspots)
        self.assertIn("Glass Bottle", csv_str)
        self.assertIn("Absolute GWP (kg CO2-eq)", csv_str)
        self.assertIn("GWP Data Tier", csv_str)
        self.assertIn("Water Data Tier", csv_str)
        self.assertIn("AWARE Water (m3 world-eq)", csv_str)
        self.assertIn("Tier 2 (EXIOBASE)", csv_str)
        self.assertIn("Tier 1 (Supplier)", csv_str)

    def test_groundwater_aware_scaling_range(self):
        calculator = TequilaBWCalculator()
        payload = get_default_captured_payload()
        payload["groundwater_m3"] = {"amount": 15342.0, "tier1_factor": None, "tier1_water_factor": None}
        payload["total_tequila_produced"] = {"amount": 1500000.0, "tier1_factor": None}

        results = calculator.calculate_lca(payload, enable_exiobase=False)
        gw_water = next(wh for wh in results["water_hotspots"] if "Extracción de Agua Subterránea" in wh["stage"] or "groundwater_m3" in wh["stage"])

        # 15,342 m3 groundwater with factor 88.0 m3 eq/m3 allocated over 1.5M liters (700ml bottle)
        # Expected score is ~0.6300 m3 world-eq, strictly less than 10.0 m3 world-eq (preventing 1,000,000x overestimation bug)
        self.assertLess(gw_water["water_score"], 10.0)
        self.assertGreater(gw_water["water_score"], 0.1)

    def test_hotspot_csv_decoupled_data_tiers(self):
        hotspots = [{"stage": "Groundwater Extraction", "gwp_score": 0.0, "pct": 0.0, "data_tier": "Tier 3 (Fallback)"}]
        water_hotspots = [{"stage": "Groundwater Extraction", "water_score": 0.63, "pct": 100.0, "data_tier": "Tier 1 (Supplier)"}]
        csv_str = generate_hotspot_csv(hotspots, water_hotspots)
        
        self.assertIn("GWP Data Tier", csv_str)
        self.assertIn("Water Data Tier", csv_str)
        self.assertIn("Tier 3 (Fallback)", csv_str)
        self.assertIn("Tier 1 (Supplier)", csv_str)

    def test_benchmark_view_status_code(self):
        response = self.client.get(reverse("benchmark"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tequila Class Comparative Benchmarking")

    def test_sankey_data_structure(self):
        calculator = TequilaBWCalculator()
        payload = get_default_captured_payload()
        results = calculator.calculate_lca(payload, enable_exiobase=False)
        self.assertIn("sankey_data", results)
        self.assertIn("water_sankey_data", results)

    def test_three_tier_data_architecture(self):
        calculator = TequilaBWCalculator()
        payload = get_default_captured_payload()
        payload["grid_electricity_kwh"] = {"amount": 2571428.0, "tier1_factor": 0.45}

        results = calculator.calculate_lca(payload, enable_exiobase=False)
        self.assertIn("primary_share_pct", results)
        self.assertIn("gwp_tier1", results)
        self.assertIn("gwp_tier3", results)
        self.assertGreater(results["gwp_tier1"], 0.0)

    def test_tier3_missing_factor_raises_value_error(self):
        calculator = TequilaBWCalculator()
        FallbackEmissionFactor.objects.all().delete()
        payload = get_default_captured_payload()
        payload["luc_deforestation_ha"] = {"amount": 5.0, "tier1_factor": None}

        with self.assertRaises(ValueError):
            calculator.calculate_lca(payload, enable_exiobase=False)

    def test_per_bottle_gwp_score_within_realistic_range(self):
        calculator = TequilaBWCalculator()
        payload = get_default_captured_payload()
        results = calculator.calculate_lca(payload, enable_exiobase=False)
        # Spirit bottle footprint should be within realistic range 1.0 to 5.0 kg CO2-eq
        self.assertGreaterEqual(results["gwp_score"], 1.0)
        self.assertLessEqual(results["gwp_score"], 5.0)

    def test_production_volume_allocation_scaling(self):
        calculator = TequilaBWCalculator()
        payload_base = get_default_captured_payload()
        results_base = calculator.calculate_lca(payload_base, enable_exiobase=False)

        # Double annual facility production volume (1.5M -> 3.0M L)
        payload_double = get_default_captured_payload()
        payload_double["total_tequila_produced"] = {"amount": 3000000.0, "tier1_factor": None}
        results_double = calculator.calculate_lca(payload_double, enable_exiobase=False)

        # Per-bottle footprint should be halved when facility production is doubled
        self.assertAlmostEqual(results_double["gwp_score"], results_base["gwp_score"] / 2.0, delta=0.1)

    def test_byproduct_no_double_conversion(self):
        calculator = TequilaBWCalculator()
        payload = get_default_captured_payload()
        payload["bagasse_generated_ton"] = {"amount": 1.0, "tier1_factor": None}
        payload["bagasse_boiler_pct"] = {"amount": 100.0, "tier1_factor": None}
        results = calculator.calculate_lca(payload, enable_exiobase=False)

        # 1 ton of bagasse to boiler allocated over 1.5M L = 0.0007 kg bagasse/bottle
        # With -0.22 kg CO2-eq / kg factor, impact should be a small negative number (~ -0.00015 kg CO2-eq)
        boiler_hotspot = next(h for h in results["hotspots"] if "Combustión" in h["stage"] or "bagasse_boiler_pct" in h["stage"])
        self.assertLess(boiler_hotspot["gwp_score"], 0.0)
        self.assertGreater(boiler_hotspot["gwp_score"], -1.0)

    def test_universal_conversion_factor_tier3(self):
        calculator = TequilaBWCalculator()
        payload = get_default_captured_payload()
        # Set solid_waste_recycled_t (1 ton annual, conv_factor 1000.0)
        payload["solid_waste_recycled_t"] = {"amount": 1.0, "tier1_factor": None}
        results = calculator.calculate_lca(payload, enable_exiobase=False)

        # Waste recycling hotspot should accurately reflect -3.098 kg CO2-eq per kg (i.e. -3098.0 kg CO2-eq / t)
        waste_hotspot = next(h for h in results["hotspots"] if "Reciclaje" in h["stage"] or "solid_waste_recycled_t" in h["stage"])
        self.assertLess(waste_hotspot["gwp_score"], 0.0)
        self.assertGreater(waste_hotspot["gwp_score"], -10.0)

    def test_tier1_water_factor_calculation(self):
        calculator = TequilaBWCalculator()
        payload = get_default_captured_payload()
        payload["groundwater_m3"] = {"amount": 100.0, "tier1_factor": 0.2, "tier1_water_factor": 50.0}

        results = calculator.calculate_lca(payload, enable_exiobase=False)
        gw_water = next(wh for wh in results["water_hotspots"] if "Extracción de Agua Subterránea" in wh["stage"] or "groundwater_m3" in wh["stage"])

        self.assertEqual(gw_water["data_tier"], "Tier 1 (Supplier)")
        self.assertGreater(gw_water["water_score"], 0.0)

    def test_tier2_exiobase_water_factor_calculation(self):
        from unittest.mock import patch, MagicMock
        calculator = TequilaBWCalculator()
        payload = get_default_captured_payload()
        payload["groundwater_m3"] = {"amount": 100.0, "tier1_factor": None, "tier1_water_factor": None}

        mock_db = MagicMock()
        mock_db.search.return_value = [MagicMock(key=("EXIOBASE_3", "1262"))]

        with patch("brightway2.databases", {"EXIOBASE_3": True}):
            with patch("brightway2.Database", return_value=mock_db):
                results = calculator.calculate_lca(payload, enable_exiobase=True)
                gw_water = next(wh for wh in results["water_hotspots"] if "Extracción de Agua Subterránea" in wh["stage"] or "groundwater_m3" in wh["stage"])
                self.assertEqual(gw_water["data_tier"], "Tier 2 (EXIOBASE)")
                self.assertGreater(gw_water["water_score"], 0.0)


