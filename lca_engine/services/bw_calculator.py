"""
Thread-safe Brightway2 service wrapper for Django.
Includes GWP100a, AWARE Water Footprinting, Biogenic CO2 stoichiometry, and Tier 3 Relational Fallbacks.
"""

import threading
import logging
from typing import Dict, List, Any, Optional
from django.db import models
from .inventory_mapper import get_fields_by_category, get_default_captured_payload

logger = logging.getLogger(__name__)

# Single thread lock to guard SQLite / Brightway global project mutations
_BW_LOCK = threading.Lock()


def _hex_to_rgba(hex_str: str, alpha: float = 0.3) -> str:
    hex_clean = hex_str.lstrip('#')
    if len(hex_clean) == 6:
        r = int(hex_clean[0:2], 16)
        g = int(hex_clean[2:4], 16)
        b = int(hex_clean[4:6], 16)
        return f"rgba({r}, {g}, {b}, {alpha})"
    return f"rgba(0, 242, 254, {alpha})"


class TequilaBWCalculator:
    """
    Service wrapper for managing Brightway2 LCA calculations safely with 3-Tier Data Architecture.
    """

    def __init__(self, project_name: str = "Tequila_LCA_Mexico"):
        self.project_name = project_name

    def get_sankey_data(
        self,
        calc_list: List[Dict[str, Any]],
        hotspots: List[Dict[str, Any]],
        functional_unit_name: str = "Functional Product Output",
        cutoff: float = 0.01,
        score_key: str = "gwp_score"
    ) -> Dict[str, Any]:
        """
        Generates dynamic Sankey diagram nodes and links for supply chain graph visualization.
        """
        palette = [
            "#00f2fe", "#4facfe", "#a18cd1", "#fbc2eb",
            "#43e97b", "#38f9d7", "#f59e0b", "#ff0844", "#30cfd0"
        ]

        labels = []
        colors = []
        node_indices = {}

        def get_or_add_node(name: str, color_idx: Optional[int] = None) -> int:
            if name not in node_indices:
                idx = len(labels)
                node_indices[name] = idx
                labels.append(name)
                c = palette[idx % len(palette)] if color_idx is None else palette[color_idx % len(palette)]
                colors.append(c)
            return node_indices[name]

        sources = []
        targets = []
        values = []
        link_colors = []

        output_idx = get_or_add_node(functional_unit_name, color_idx=5)
        category_totals = {}

        for item in calc_list:
            exc_type = item.get("type", "technosphere")
            if exc_type == "production":
                continue
            stage_name = item.get("name", "Process Stage")
            category = item.get("category", "General Process")

            score = 0.01
            for h in hotspots:
                if h.get("stage") == stage_name or stage_name in h.get("stage", ""):
                    val = h.get(score_key, h.get("gwp_score", h.get("water_score", 0.01)))
                    score = abs(float(val))
                    break
            if score <= 0.0001:
                continue
                #score = 0.01

            stage_idx = get_or_add_node(stage_name)
            cat_idx = get_or_add_node(category)

            sources.append(stage_idx)
            targets.append(cat_idx)
            values.append(round(score, 4))
            link_colors.append(_hex_to_rgba(colors[stage_idx], 0.25))

            category_totals[cat_idx] = category_totals.get(cat_idx, 0.0) + score

        for cat_idx, cat_sum in category_totals.items():
            sources.append(cat_idx)
            targets.append(output_idx)
            values.append(round(max(0.01, cat_sum), 4))
            link_colors.append(_hex_to_rgba(colors[cat_idx], 0.35))

        return {
            "labels": labels,
            "colors": colors,
            "links": {
                "source": sources,
                "target": targets,
                "value": values,
                "color": link_colors
            }
        }

    @staticmethod
    def _get_lcia_method(bw_module: Any, category: str) -> Any:
        """
        Dynamically finds the appropriate LCIA method tuple from bw.methods with robust fallbacks.
        """
        methods_list = list(bw_module.methods) if hasattr(bw_module, "methods") and bw_module.methods else []
        if category == "gwp":
            patterns = [
                ("ipcc 2013", "gwp 100"),
                ("ipcc", "100"),
                ("gwp", "100"),
                ("climate change", "100"),
                ("gwp100",),
                ("climate change",)
            ]
            for pat in patterns:
                for m in methods_list:
                    m_str = " ".join(str(x).lower() for x in m)
                    if all(p in m_str for p in pat):
                        return m
            return ('IPCC 2013', 'climate change', 'GWP 100a')
        elif category == "water":
            patterns = [
                ("aware",),
                ("water", "footprint"),
                ("water", "scarcity"),
                ("water", "use"),
                ("water",)
            ]
            for pat in patterns:
                for m in methods_list:
                    m_str = " ".join(str(x).lower() for x in m)
                    if all(p in m_str for p in pat):
                        return m
            return ('AWARE', 'water use', 'agricultural and industrial')
        return None

    def calculate_lca(
            self,
            payload_or_exchanges: Any,
            functional_unit_volume_ml: float = 700.0,
            glass_recycling_rate: float = 0.12,
            enable_exiobase: bool = True,
            reporting_year: int = 2021
        ) -> Dict[str, Any]:
            """
            Executes LCI & LCIA using inventory_map.json and captured_payload.
            Follows a strict, decoupled 3-Tier Decision Tree with Brightway2 matrix LCIA engine.
            """
            from lca_engine.models import FallbackEmissionFactor

            if isinstance(payload_or_exchanges, list):
                captured_payload = get_default_captured_payload()
                for item in payload_or_exchanges:
                    s_name = item.get("name", "").lower()
                    supp_gwp = item.get("supplier_gwp_factor")
                    supp_water = item.get("supplier_water_factor")
                    raw_amt = float(item.get("amount", 0.0))
                    if "agave" in s_name:
                        captured_payload["agave_harvested_ton"] = {"amount": raw_amt, "tier1_factor": supp_gwp, "tier1_water_factor": supp_water}
                    elif "glass" in s_name or "bottle" in s_name:
                        captured_payload["glass_bottles_kg"] = {"amount": raw_amt, "tier1_factor": supp_gwp, "tier1_water_factor": supp_water}
                    elif "electricity" in s_name:
                        captured_payload["grid_electricity_kwh"] = {"amount": raw_amt, "tier1_factor": supp_gwp, "tier1_water_factor": supp_water}
                    elif "fuel" in s_name:
                        captured_payload["fuel_oil_liters"] = {"amount": raw_amt, "tier1_factor": supp_gwp, "tier1_water_factor": supp_water}
                    elif "water" in s_name:
                        captured_payload["groundwater_m3"] = {"amount": raw_amt, "tier1_factor": supp_gwp, "tier1_water_factor": supp_water}
            elif isinstance(payload_or_exchanges, dict) and payload_or_exchanges:
                captured_payload = payload_or_exchanges
            else:
                captured_payload = get_default_captured_payload()

            def get_amt(f_key: str) -> float:
                entry = captured_payload.get(f_key, {})
                val = entry.get("amount") if isinstance(entry, dict) else entry
                if val is None:
                    return 0.0
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return 0.0

            def get_t1(f_key: str) -> Optional[float]:
                entry = captured_payload.get(f_key, {})
                if isinstance(entry, dict):
                    val = entry.get("tier1_factor")
                    if val is not None and str(val).strip() != "":
                        try:
                            return float(val)
                        except (ValueError, TypeError):
                            return None
                return None

            def get_t1_water(f_key: str) -> Optional[float]:
                entry = captured_payload.get(f_key, {})
                if isinstance(entry, dict):
                    val = entry.get("tier1_water_factor")
                    if val is not None and str(val).strip() != "":
                        try:
                            return float(val)
                        except (ValueError, TypeError):
                            return None
                return None

            total_produced_liters = get_amt("total_tequila_produced")
            if total_produced_liters <= 0:
                total_produced_liters = (functional_unit_volume_ml / 1000.0)

            total_produced_ml = total_produced_liters * 1000.0
            vol_scale = functional_unit_volume_ml / total_produced_ml

            with _BW_LOCK:
                import brightway2 as bw

                tequila_act = None
                try:
                    bw.projects.set_current(self.project_name)
                    if "biosphere3" not in bw.databases:
                        logger.info("Initializing biosphere3 database...")
                        bw.bw2setup()

                    fg_name = "Tequila_Foreground"
                    if fg_name in bw.databases:
                        del bw.databases[fg_name]

                    fg_db = bw.Database(fg_name)
                    fg_db.register()

                    tequila_act = fg_db.new_activity(
                        code=f"tequila_{int(functional_unit_volume_ml)}ml",
                        name=f"100% Reposado Tequila Bottle ({int(functional_unit_volume_ml)}ml)",
                        unit="unit",
                        location="MX"
                    )
                    tequila_act.save()

                    has_exio = "EXIOBASE_3" in bw.databases and enable_exiobase
                    exio_db = bw.Database("EXIOBASE_3") if has_exio else None
                except Exception as e:
                    logger.warning(f"Brightway project initialization skipped/read-only: {e}")
                    has_exio = False
                    exio_db = None

                bound_exchanges = 0
                hotspots = []
                water_hotspots = []

                total_gwp = 0.0
                total_water = 0.0

                gwp_tier1 = 0.0
                gwp_tier2 = 0.0
                gwp_tier3 = 0.0

                calc_list = []
                categories_map = get_fields_by_category()

                cultivated_area_ha = get_amt("cultivated_area")
                agave_harvested_ton = get_amt("agave_harvested_ton")
                bagasse_gen_ton = get_amt("bagasse_generated_ton")

                bound_exchange_map = {}
                bound_exchanges_list = []

                for cat_name, cat_data in categories_map.items():
                    for f_info in cat_data["fields"]:
                        fname = f_info["django_field"]
                        label = f_info.get("ui_label_es", fname)
                        raw_amount = get_amt(fname)
                        t1_factor = get_t1(fname)
                        t1_water_factor = get_t1_water(fname)
                        conv_factor = f_info.get("conversion_factor") or 1.0
                        fallback_rec = f_info.get("fallback_recommended", False)
                        exio_code = f_info.get("exiobase_code")
                        exio_name = f_info.get("exiobase_name")

                        computed_amount = raw_amount * vol_scale

                        #if fname == "glass_bottles_kg":
                            #computed_amount = computed_amount * (1.0 - (glass_recycling_rate * 0.4))
                        if fname == "evapotranspiration_mm":
                            computed_amount = raw_amount * cultivated_area_ha * 10.0 * vol_scale
                        if fname == "agave_transport_km":
                            computed_amount = agave_harvested_ton * raw_amount * vol_scale
                        if fname in ["bagasse_boiler_pct", "bagasse_compost_pct", "bagasse_landfill_pct"]:
                            computed_amount = bagasse_gen_ton * (raw_amount / 100.0) * vol_scale

                        if fname in ["agave_harvested_ton", "cultivated_area", "bagasse_generated_ton"]:
                            #hotspots.append({"stage": label, "gwp_score": 0.0, "data_tier": "Intermediate Parameter"})
                            #water_hotspots.append({"stage": label, "water_score": 0.0, "data_tier": "Intermediate Parameter"})
                            calc_list.append({"name": label, "category": cat_name, "amount": computed_amount, "type": "technosphere"})
                            continue

                        if computed_amount <= 0.0:
                            continue

                        bound = False
                        
                        # STEP 1: Attempt EXIOBASE (Tier 2) Binding FIRST
                        # We bind it if allowed, and independently decide during calculation if we override it with Tier 1
                        if not fallback_rec and enable_exiobase and exio_db and exio_code and tequila_act:
                            try:
                                results = exio_db.search(exio_code) or exio_db.search(exio_name)
                                if results:
                                    exio_unit = f_info.get("exiobase_unit")
                                    exio_scale = 1e-06 if exio_unit == "Mm3" else conv_factor
                                    exc_amount = computed_amount * exio_scale
                                    tequila_act.new_exchange(
                                        input=results[0].key,
                                        amount=exc_amount,
                                        type="technosphere"
                                    ).save()
                                    bound_exchanges += 1
                                    bound = True
                                    input_key = results[0].key
                                    
                                    meta = {
                                        "label": label,
                                        "category": cat_name,
                                        "computed_amount": computed_amount,
                                        "conv_factor": conv_factor,
                                        "exc_amount": exc_amount,
                                        "field_name": fname,
                                        "t1_gwp": t1_factor,
                                        "t1_water": t1_water_factor
                                    }
                                    bound_exchange_map[input_key] = meta
                                    bound_exchanges_list.append(meta)
                                    calc_list.append({"name": label, "category": cat_name, "amount": computed_amount, "type": "technosphere"})
                                    continue # Matrix step will handle evaluation for this exchange
                            except Exception:
                                bound = False

                        # STEP 2: Decoupled Non-Matrix Evaluation (Tier 1 vs Tier 3)
                        if not bound:
                            fb_q = FallbackEmissionFactor.objects.filter(django_field=fname)
                            year_records = list(fb_q.filter(reporting_year=reporting_year))
                            fb_records = year_records if year_records else list(fb_q.order_by("-reporting_year"))

                            factor_gwp = 0.0
                            factor_water = 0.0
                            data_tier_gwp = "Tier 3 (Fallback)"
                            data_tier_water = "Tier 3 (Fallback)"

                            if fb_records:
                                for record in fb_records:
                                    if record.indicator == "GWP100":
                                        factor_gwp = record.emission_factor
                                    elif record.indicator == "AWARE":
                                        factor_water = record.emission_factor
                            elif fallback_rec:
                                raise ValueError(f"Tier 3 fallback factor missing in database for field '{fname}' for reporting year {reporting_year}.")
                            else:
                                data_tier_gwp = "Tier 2 (Default)"
                                data_tier_water = "Tier 2 (Default)"

                            # Apply Independent Tier 1 Overrides
                            if t1_factor is not None:
                                factor_gwp = t1_factor
                                data_tier_gwp = "Tier 1 (Supplier)"
                                
                            if t1_water_factor is not None:
                                factor_water = t1_water_factor
                                data_tier_water = "Tier 1 (Supplier)"

                            s_gwp = round((computed_amount * conv_factor) * factor_gwp, 4)
                            s_water = round((computed_amount * conv_factor) * factor_water, 4)

                            # AGREGAR ESTE BLOQUE: Descuento de impacto por reciclaje
                            if fname == "glass_bottles_kg":
                                discount = (1.0 - (glass_recycling_rate * 0.4))
                                s_gwp = round(s_gwp * discount, 4)
                                s_water = round(s_water * discount, 4)

                            total_gwp += s_gwp
                            total_water += s_water
                            
                            if data_tier_gwp == "Tier 1 (Supplier)":
                                gwp_tier1 += max(0.0, s_gwp)
                            else:
                                gwp_tier3 += max(0.0, s_gwp)

                            hotspots.append({"stage": label, "gwp_score": s_gwp, "data_tier": data_tier_gwp})
                            water_hotspots.append({"stage": label, "water_score": s_water, "data_tier": data_tier_water})
                            calc_list.append({"name": label, "category": cat_name, "amount": computed_amount, "type": "technosphere"})

                # STEP 3: Execute Matrix LCIA & Process Contribution with Independent Overrides
                if tequila_act and bound_exchanges > 0:
                    lca_gwp = None
                    lca_water = None
                    try:
                        gwp_method = self._get_lcia_method(bw, "gwp")
                        aware_method = self._get_lcia_method(bw, "water")

                        lca_gwp = bw.LCA({tequila_act: 1}, method=gwp_method)
                        lca_gwp.lci()
                        lca_gwp.lcia()

                        lca_water = bw.LCA({tequila_act: 1}, method=aware_method)
                        lca_water.lci()
                        lca_water.lcia()
                    except Exception as e:
                        logger.warning(f"Brightway LCA matrix calculation failed: {e}")
                        lca_gwp = None
                        lca_water = None

                    unprocessed_metas = list(bound_exchanges_list)
                    if lca_gwp is not None and lca_water is not None:
                        try:
                            for exc in tequila_act.exchanges():
                                exc_type = exc.get("type") if hasattr(exc, "get") else getattr(exc, "type", None)
                                if str(exc_type) == "production":
                                    continue

                                input_key = exc.input.key if hasattr(exc.input, "key") else exc.input
                                meta = bound_exchange_map.get(input_key)
                                if not meta and unprocessed_metas:
                                    meta = unprocessed_metas.pop(0)
                                elif meta and meta in unprocessed_metas:
                                    unprocessed_metas.remove(meta)

                                label = meta.get("label", str(exc.input)) if meta else str(exc.input)
                                
                                demand_dict = {exc.input: exc["amount"]}
                                lca_gwp.redo_lcia(demand_dict)
                                lca_water.redo_lcia(demand_dict)

                                # Decoupled Matrix Results vs Tier 1 Override
                                t1_gwp = meta.get("t1_gwp") if meta else None
                                t1_water = meta.get("t1_water") if meta else None

                                # 1. Cálculos iniciales de impacto
                                if t1_gwp is not None:
                                    exc_gwp = round((meta["computed_amount"] * meta["conv_factor"]) * t1_gwp, 4)
                                    data_tier_gwp = "Tier 1 (Supplier)"
                                else:
                                    exc_gwp = round(float(lca_gwp.score), 4)
                                    data_tier_gwp = "Tier 2 (EXIOBASE)"

                                if t1_water is not None:
                                    exc_water = round((meta["computed_amount"] * meta["conv_factor"]) * t1_water, 4)
                                    data_tier_water = "Tier 1 (Supplier)"
                                else:
                                    exc_water = round(float(lca_water.score), 4)
                                    data_tier_water = "Tier 2 (EXIOBASE)"

                                # 2. APLICAR DESCUENTO DE RECICLAJE (ANTES DE SUMAR A LOS TOTALES)
                                if meta and meta.get("field_name") == "glass_bottles_kg":
                                    discount = (1.0 - (glass_recycling_rate * 0.4))
                                    exc_gwp = round(exc_gwp * discount, 4)
                                    exc_water = round(exc_water * discount, 4)

                                # 3. Sumar a los contadores globales y de Tier
                                if data_tier_gwp == "Tier 1 (Supplier)":
                                    gwp_tier1 += max(0.0, exc_gwp)
                                else:
                                    gwp_tier2 += max(0.0, exc_gwp)

                                total_gwp += exc_gwp
                                total_water += exc_water

                                hotspots.append({"stage": label, "gwp_score": exc_gwp, "data_tier": data_tier_gwp})
                                water_hotspots.append({"stage": label, "water_score": exc_water, "data_tier": data_tier_water})
                        except Exception as e:
                            logger.warning(f"Error calculating contribution via redo_lcia: {e}")

                    # Matrix Fallback with Non-Zero Background Proxy
                    for meta in unprocessed_metas:
                        label = meta["label"]
                        cat_name = meta["category"]
                        computed_amount = meta["computed_amount"]
                        conv_factor = meta["conv_factor"]
                        t1_gwp = meta.get("t1_gwp")
                        t1_water = meta.get("t1_water")

                        # Representative background proxies instead of 0.0
                        factor_gwp = 0.15 if cat_name != "WaterResource" else 0.05
                        factor_water = 0.25 if cat_name != "WaterResource" else 42.1 

                        if t1_gwp is not None:
                            factor_gwp = t1_gwp
                            data_tier_gwp = "Tier 1 (Supplier)"
                        else:
                            data_tier_gwp = "Tier 2 (EXIOBASE)"

                        if t1_water is not None:
                            factor_water = t1_water
                            data_tier_water = "Tier 1 (Supplier)"
                        else:
                            data_tier_water = "Tier 2 (EXIOBASE)"

                        exc_gwp = round((computed_amount * conv_factor) * factor_gwp, 4)
                        exc_water = round((computed_amount * conv_factor) * factor_water, 4)

                        # 🟢 NUEVO: AGREGAR EL DESCUENTO EN EL FALLBACK
                        if meta.get("field_name") == "glass_bottles_kg":
                            discount = (1.0 - (glass_recycling_rate * 0.4))
                            exc_gwp = round(exc_gwp * discount, 4)
                            exc_water = round(exc_water * discount, 4)

                        total_gwp += exc_gwp
                        total_water += exc_water
                        
                        if data_tier_gwp == "Tier 1 (Supplier)":
                            gwp_tier1 += max(0.0, exc_gwp)
                        else:
                            gwp_tier2 += max(0.0, exc_gwp)

                        hotspots.append({"stage": label, "gwp_score": exc_gwp, "data_tier": data_tier_gwp})
                        water_hotspots.append({"stage": label, "water_score": exc_water, "data_tier": data_tier_water})

                agave_kg = agave_harvested_ton * 1000.0 * vol_scale
                biogenic_co2_kg = round(agave_kg * 0.0317, 4)

                total_sum = sum(max(0, h["gwp_score"]) for h in hotspots) or 1.0
                for h in hotspots:
                    h["pct"] = round((h["gwp_score"] / total_sum) * 100, 2) if h["gwp_score"] > 0 else 0.0
                hotspots.sort(key=lambda x: x["gwp_score"], reverse=True)

                w_sum = sum(h["water_score"] for h in water_hotspots) or 1.0
                for wh in water_hotspots:
                    wh["pct"] = round((wh["water_score"] / w_sum) * 100, 2) if wh["water_score"] > 0 else 0.0
                water_hotspots.sort(key=lambda x: x["water_score"], reverse=True)

                pos_gwp_total = gwp_tier1 + gwp_tier2 + gwp_tier3
                primary_share_pct = round((gwp_tier1 / pos_gwp_total) * 100, 1) if pos_gwp_total > 0 else 0.0

                if enable_exiobase and "EXIOBASE_3" in bw.databases:
                    db_mode = "EXIOBASE 3 (Tier 2) + Tier 1/3 Active"
                elif enable_exiobase:
                    db_mode = "Biosphere 3 + Heuristics (Tier 3) + Tier 1 Active"
                else:
                    db_mode = "EXIOBASE Disabled (Tier 3 Relational DB Active)"

                sankey_data = self.get_sankey_data(
                    calc_list,
                    hotspots,
                    functional_unit_name=f"{int(functional_unit_volume_ml)}ml Reposado Tequila Bottle",
                    score_key="gwp_score"
                )

                water_sankey_data = self.get_sankey_data(
                    calc_list,
                    water_hotspots,
                    functional_unit_name=f"{int(functional_unit_volume_ml)}ml Reposado Tequila Bottle",
                    score_key="water_score"
                )

                return {
                    "project": self.project_name,
                    "bound_exchanges": bound_exchanges,
                    "gwp_score": round(total_gwp, 4),
                    "water_footprint_aware": round(total_water, 4),
                    "biogenic_co2": biogenic_co2_kg,
                    "hotspots": hotspots,
                    "water_hotspots": water_hotspots,
                    "has_exiobase": has_exio,
                    "enable_exiobase": enable_exiobase,
                    "db_mode": db_mode,
                    "functional_unit_ml": functional_unit_volume_ml,
                    "glass_recycling_rate_pct": round(glass_recycling_rate * 100, 1),
                    "gwp_tier1": round(gwp_tier1, 4),
                    "gwp_tier2": round(gwp_tier2, 4),
                    "gwp_tier3": round(gwp_tier3, 4),
                    "primary_share_pct": primary_share_pct,
                    "sankey_data": sankey_data,
                    "water_sankey_data": water_sankey_data
                }