"""
CSV parser and export utilities for LCA inventory and calculation results.
"""

import io
import pandas as pd
from typing import List, Dict, Any


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


def generate_hotspot_csv(hotspots: List[Dict[str, Any]]) -> str:
    """
    Generates CSV string output for hotspot results.
    """
    df = pd.DataFrame(hotspots)
    if not df.empty:
        df.columns = ["Lifecycle Stage", "Absolute GWP (kg CO2-eq)", "Percentage Contribution (%)"]
    return df.to_csv(index=False)
