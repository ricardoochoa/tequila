"""
CSV parser and export utilities for LCA inventory and calculation results.
Includes key-value 4-column LCI template generator and strict validation parser.
"""

import io
import csv
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional
from .inventory_mapper import get_all_fields, get_default_captured_payload


DEFAULT_INVENTORY_CSV_HEADERS = [
    "stage_name", "category", "query", "amount", "unit", "location", "exchange_type", "supplier_gwp_factor", "supplier_water_factor"
]

KEY_VALUE_CSV_HEADERS = ["Nombre_Variable", "Valor", "Unidades", "Notas"]


def generate_lci_template_csv() -> str:
    """
    Generates standardized 4-column key-value CSV template (Nombre_Variable, Valor, Unidades, Notas).
    """
    fields_info = get_all_fields()
    defaults = get_default_captured_payload()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(KEY_VALUE_CSV_HEADERS)

    # Auxiliary header metadata rows
    writer.writerow(["reporting_year", 2025, "Año", "Año fiscal o natural de los datos reportados"])
    writer.writerow(["total_tequila_produced", 1500000.0, "Litros", "Producción total terminada a 40% Alc. Vol."])

    for field in fields_info:
        fname = field["django_field"]
        unit = field.get("capture_unit", "")
        desc = field.get("ui_description_es", "")
        def_entry = defaults.get(fname, {})
        val = def_entry.get("amount") if isinstance(def_entry, dict) else def_entry
        if val is None:
            val = 0.0

        writer.writerow([fname, val, unit, desc])

    return output.getvalue()


def parse_key_value_lci_csv(file_obj) -> Tuple[Dict[str, Any], List[str]]:
    """
    Parses key-value CSV format (Nombre_Variable, Valor, Unidades, Notas).
    Pivots data into captured_payload structure and validates keys, types, and constraints.
    Returns (payload_dict, errors_list).
    """
    errors = []
    payload = get_default_captured_payload()

    try:
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)
        df = pd.read_csv(file_obj)
    except Exception as e:
        return payload, [f"Error al leer el archivo CSV: {str(e)}"]

    # Standardize column headers
    cols = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    df.columns = cols

    var_col = None
    val_col = None
    notes_col = None

    for c in cols:
        if "variable" in c or "nombre" in c or "key" in c:
            var_col = c
        elif "valor" in c or "value" in c:
            val_col = c
        elif "nota" in c or "comment" in c:
            notes_col = c

    if not var_col or not val_col:
        # Fallback to column index 0 and 1
        if len(df.columns) >= 2:
            var_col = df.columns[0]
            val_col = df.columns[1]
        else:
            return payload, ["El archivo CSV debe contener las columnas: Nombre_Variable, Valor, Unidades, Notas."]

    all_valid_fields = set([f["django_field"] for f in get_all_fields()] + ["reporting_year", "total_tequila_produced"])

    for idx, row in df.iterrows():
        row_num = idx + 2  # 1-indexed header + 1
        raw_var = row.get(var_col)
        if pd.isna(raw_var) or str(raw_var).strip() == "":
            continue

        var_name = str(raw_var).strip()
        raw_val = row.get(val_col)
        notes = str(row.get(notes_col, "")) if notes_col and pd.notna(row.get(notes_col)) else ""

        # RULE 1: Key Validation
        if var_name not in all_valid_fields:
            errors.append(f"Fila {row_num}: La variable '{var_name}' no es una clave reconocida del Diccionario Oficial de LCI.")
            continue

        # Extract existing Tier 1 overrides (GWP and AWARE) to prevent data loss during upload
        existing_tier1_gwp = None
        existing_tier1_water = None
        if isinstance(payload.get(var_name), dict):
            existing_tier1_gwp = payload[var_name].get("tier1_factor")
            existing_tier1_water = payload[var_name].get("tier1_water_factor")

        # RULE 2: Type Casting & Choice Mapping
        if var_name == "vinasse_treatment":
            val_str = str(raw_val).strip().lower() if pd.notna(raw_val) else ""
            mapped_choice = "pit"
            if "aerob" in val_str or "pta" in val_str:
                mapped_choice = "aerobic"
            elif "biodiges" in val_str or "anaerob" in val_str:
                mapped_choice = "biodigestor"
            elif "riego" in val_str or "irrig" in val_str or "suelo" in val_str:
                mapped_choice = "irrigation"
            elif "fosa" in val_str or "pit" in val_str or "abierta" in val_str:
                mapped_choice = "pit"

            payload[var_name] = {
                "amount": mapped_choice, 
                "tier1_factor": existing_tier1_gwp, 
                "tier1_water_factor": existing_tier1_water,
                "notes": notes
            }
        else:
            if pd.isna(raw_val) or str(raw_val).strip() == "":
                num_val = 0.0
            else:
                try:
                    num_val = float(str(raw_val).strip().replace(",", ""))
                except (ValueError, TypeError):
                    errors.append(f"Fila {row_num} ({var_name}): El valor '{raw_val}' no es un número válido.")
                    continue

            payload[var_name] = {
                "amount": num_val, 
                "tier1_factor": existing_tier1_gwp, 
                "tier1_water_factor": existing_tier1_water,
                "notes": notes
            }

    # RULE 3: Constraint Checking (Bagasse Sum <= 100%)
    def get_p_val(key: str) -> float:
        e = payload.get(key, {})
        if isinstance(e, dict):
            try:
                return float(e.get("amount") or 0.0)
            except (ValueError, TypeError):
                return 0.0
        try:
            return float(e or 0.0)
        except (ValueError, TypeError):
            return 0.0

    boiler_pct = get_p_val("bagasse_boiler_pct")
    compost_pct = get_p_val("bagasse_compost_pct")
    landfill_pct = get_p_val("bagasse_landfill_pct")
    bagasse_sum = boiler_pct + compost_pct + landfill_pct

    if bagasse_sum > 100.0:
        errors.append(f"Restricción violada: La suma de los porcentajes de disposición de bagazo no puede exceder 100% (Suma actual: {bagasse_sum}%).")

    return payload, errors


def parse_inventory_csv(file_obj) -> List[Dict[str, Any]]:
    """
    Parses uploaded legacy CSV file into structured inventory exchange dictionaries.
    """
    if hasattr(file_obj, "seek"):
        file_obj.seek(0)
    df = pd.read_csv(file_obj)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    exchanges = []
    for _, row in df.iterrows():
        sg = row.get("supplier_gwp_factor", row.get("supplier_gwp", None))
        sw = row.get("supplier_water_factor", row.get("supplier_water", None))

        exchanges.append({
            "name": str(row.get("stage_name", row.get("name", "Process"))),
            "category": str(row.get("category", "General")),
            "query": str(row.get("query", "")),
            "amount": float(row.get("amount", 0.0)),
            "unit": str(row.get("unit", "kg")),
            "location": str(row.get("location", "")) if pd.notna(row.get("location")) else None,
            "type": str(row.get("exchange_type", row.get("type", "technosphere"))),
            "supplier_gwp_factor": float(sg) if pd.notna(sg) and str(sg).strip() != "" else None,
            "supplier_water_factor": float(sw) if pd.notna(sw) and str(sw).strip() != "" else None,
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
            "Data Tier": h.get("data_tier", "Fallback"),
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
                    "Data Tier": wh.get("data_tier", "Fallback"),
                    "Absolute GWP (kg CO2-eq)": 0.0,
                    "GWP Contribution (%)": 0.0,
                    "AWARE Water (m3 world-eq)": wh.get("water_score", 0.0),
                    "Water Contribution (%)": wh.get("pct", 0.0),
                })

    df = pd.DataFrame(merged_data)
    if df.empty:
        df = pd.DataFrame(columns=[
            "Lifecycle Stage",
            "Data Tier",
            "Absolute GWP (kg CO2-eq)",
            "GWP Contribution (%)",
            "AWARE Water (m3 world-eq)",
            "Water Contribution (%)"
        ])
    return df.to_csv(index=False)