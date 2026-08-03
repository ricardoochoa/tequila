"""
Inventory mapper service to load, validate, and cache inventory_map.json.
Provides helpers for dynamic forms, validation, and LCA calculation routing.
"""

import json
import os
from typing import Dict, List, Any, Optional
from django.conf import settings
from django.core.cache import cache

_MAP_CACHE_KEY = "tequila_lca_inventory_map_v1"
_MODULE_CACHE: Optional[Dict[str, Any]] = None


def load_inventory_map() -> Dict[str, Any]:
    """
    Loads inventory_map.json from lca_engine/data/inventory_map.json with caching.
    """
    global _MODULE_CACHE
    if _MODULE_CACHE is not None:
        return _MODULE_CACHE

    cached_data = cache.get(_MAP_CACHE_KEY)
    if cached_data:
        _MODULE_CACHE = cached_data
        return cached_data

    file_path = os.path.join(settings.BASE_DIR, "lca_engine", "data", "inventory_map.json")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Inventory mapping file not found at: {file_path}")

    with open(file_path, mode="r", encoding="utf-8") as f:
        data = json.load(f)

    cache.set(_MAP_CACHE_KEY, data, timeout=86400)
    _MODULE_CACHE = data
    return data


def get_all_fields() -> List[Dict[str, Any]]:
    """
    Returns a flat list of all field definitions across all phases/categories.
    """
    inv_map = load_inventory_map()
    fields = []
    for cat_name, cat_data in inv_map.items():
        for field in cat_data.get("fields", []):
            field_copy = dict(field)
            field_copy["category_name"] = cat_name
            fields.append(field_copy)
    return fields


def get_fields_by_category() -> Dict[str, List[Dict[str, Any]]]:
    """
    Returns a dictionary mapping category_name -> list of field definitions.
    """
    inv_map = load_inventory_map()
    result = {}
    for cat_name, cat_data in inv_map.items():
        result[cat_name] = {
            "metadata": cat_data.get("entity_metadata", {}),
            "fields": cat_data.get("fields", [])
        }
    return result


def get_field_by_django_field(django_field: str) -> Optional[Dict[str, Any]]:
    """
    Looks up a specific field definition by its django_field key.
    """
    for field in get_all_fields():
        if field.get("django_field") == django_field:
            return field
    return None


def get_default_captured_payload() -> Dict[str, Any]:
    """
    Returns default initial values for captured_payload based on baseline tequila production (1.5M Liters facility level).
    """
    defaults = {
        "total_tequila_produced": {"amount": 1500000.0, "tier1_factor": None},
        "cultivated_area": {"amount": 1071.4, "tier1_factor": None},
        "agave_harvested_ton": {"amount": 8620.0, "tier1_factor": 0.28},
        "luc_deforestation_ha": {"amount": 0.0, "tier1_factor": None},
        "fertilizer_n_kg": {"amount": 5357.0, "tier1_factor": None},
        "fertilizer_p_kg": {"amount": 1714.0, "tier1_factor": None},
        "fertilizer_k_kg": {"amount": 1071.0, "tier1_factor": None},
        "organic_fertilizer_kg": {"amount": 10714.0, "tier1_factor": None},
        "pesticides_active_kg": {"amount": 257.0, "tier1_factor": None},
        "agri_diesel_liters": {"amount": 2571428.0, "tier1_factor": 2.68},
        "agave_milled_ton": {"amount": 8620.0, "tier1_factor": None},
        "agave_transport_km": {"amount": 25.0, "tier1_factor": None},
        "fuel_oil_liters": {"amount": 1727142.0, "tier1_factor": 3.1},
        "natural_gas_m3": {"amount": 0.0, "tier1_factor": None},
        "lp_gas_liters": {"amount": 0.0, "tier1_factor": None},
        "grid_electricity_kwh": {"amount": 2571428.0, "tier1_factor": 0.45},
        "solar_electricity_kwh": {"amount": 0.0, "tier1_factor": None},
        "yeast_nutrients_kg": {"amount": 9428.0, "tier1_factor": None},
        "ref_r22_leaked_kg": {"amount": 0.0, "tier1_factor": None},
        "ref_r134a_leaked_kg": {"amount": 0.0, "tier1_factor": None},
        "glass_bottles_kg": {"amount": 1178571.0, "tier1_factor": 1.1},
        "cardboard_boxes_kg": {"amount": 257142.0, "tier1_factor": None},
        "groundwater_m3": {"amount": 15342.0, "tier1_factor": 0.65},
        "municipal_water_m3": {"amount": 0.0, "tier1_factor": None},
        "precipitation_mm": {"amount": 850.0, "tier1_factor": None},
        "evapotranspiration_mm": {"amount": 42.1, "tier1_factor": None},
        "vinasse_volume_m3": {"amount": 25714.0, "tier1_factor": None},
        "vinasse_cod_mg_l": {"amount": 50000.0, "tier1_factor": None},
        "vinasse_treatment": {"amount": "pit", "tier1_factor": None},
        "bagasse_generated_ton": {"amount": 3042.0, "tier1_factor": None},
        "bagasse_boiler_pct": {"amount": 60.0, "tier1_factor": None},
        "bagasse_compost_pct": {"amount": 40.0, "tier1_factor": None},
        "bagasse_landfill_pct": {"amount": 0.0, "tier1_factor": None},
        "solid_waste_landfill_t": {"amount": 0.0, "tier1_factor": None},
        "solid_waste_recycled_t": {"amount": 1071.0, "tier1_factor": None},
    }
    return defaults
