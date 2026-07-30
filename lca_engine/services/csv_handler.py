"""
CSV parser and export utilities for LCA inventory and calculation results.
"""

import io
import pandas as pd
from typing import List, Dict, Any, Optional


DEFAULT_INVENTORY_CSV_HEADERS = ["stage_name", "category", "query", "amount", "unit", "location", "exchange_type"]


def parse_inventory_csv(file_obj) -> List[Dict[str, Any]]:
    """
    Parses uploaded CSV file into structured inventory exchange dictionaries.
    """
    df = pd.read_csv(file_obj)
    # Standardize header names
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    exchanges = []
    for _, row in df.iterrows():
        exchanges.append({
            "name": str(row.get("stage_name", row.get("name", "Process"))),
            "category": str(row.get("category", "General")),
            "query": str(row.get("query", "")),
            "amount": float(row.get("amount", 0.0)),
            "unit": str(row.get("unit", "kg")),
            "location": str(row.get("location", "")) if pd.notna(row.get("location")) else None,
            "type": str(row.get("exchange_type", row.get("type", "technosphere")))
        })
    return exchanges


def generate_hotspot_csv(
    hotspots: List[Dict[str, Any]],
    water_hotspots: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Generates CSV string output combining GWP and Water hotspot results.
    """
    water_lookup = {}
    if water_hotspots:
        for wh in water_hotspots:
            water_lookup[wh.get("stage")] = wh

    merged_data = []
    seen_stages = set()

    for h in hotspots:
        stage = h.get("stage", "")
        seen_stages.add(stage)
        wh = water_lookup.get(stage, {})
        merged_data.append({
            "Lifecycle Stage": stage,
            "Absolute GWP (kg CO2-eq)": h.get("gwp_score", 0.0),
            "GWP Contribution (%)": h.get("pct", 0.0),
            "AWARE Water (m3 world-eq)": wh.get("water_score", 0.0),
            "Water Contribution (%)": wh.get("pct", 0.0),
        })

    if water_hotspots:
        for wh in water_hotspots:
            stage = wh.get("stage", "")
            if stage not in seen_stages:
                merged_data.append({
                    "Lifecycle Stage": stage,
                    "Absolute GWP (kg CO2-eq)": 0.0,
                    "GWP Contribution (%)": 0.0,
                    "AWARE Water (m3 world-eq)": wh.get("water_score", 0.0),
                    "Water Contribution (%)": wh.get("pct", 0.0),
                })

    df = pd.DataFrame(merged_data)
    if df.empty:
        df = pd.DataFrame(columns=[
            "Lifecycle Stage",
            "Absolute GWP (kg CO2-eq)",
            "GWP Contribution (%)",
            "AWARE Water (m3 world-eq)",
            "Water Contribution (%)"
        ])
    return df.to_csv(index=False)

