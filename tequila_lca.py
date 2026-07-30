"""
Tequila Life Cycle Assessment (LCA) Model
-------------------------------------------
Modular, robust Brightway2 script for modeling the cradle-to-gate
environmental impact of 100% Reposado Tequila (700ml).
"""

import logging
from typing import Dict, List, Any, Optional

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def safe_search(database: Any, query: str, location: Optional[str] = None) -> Any:
    """
    Safely query a Brightway database with informative error messages.
    """
    results = database.search(query)
    if location:
        filtered = [r for r in results if r.get("location") == location]
        if filtered:
            return filtered[0]

    if results:
        return results[0]

    raise ValueError(f"Could not find matching activity for query '{query}' (location={location}) in database {database.name}")


def get_tequila_inventory_recipe() -> List[Dict[str, Any]]:
    """
    Returns structured foreground inventory data for 1 bottle (700ml) of 100% Reposado Tequila.
    """
    return [
        # Production output
        {"name": "production_output", "category": "production", "query": None, "amount": 1.0, "type": "production"},

        # 1. Agave Reception & Clipping Phase
        {"name": "Agave pineapple", "category": "Agave Reception", "query": "Cultivation of crops Mexico", "location": "MX", "amount": 8.62, "type": "technosphere"},
        {"name": "Electricity (Reception)", "category": "Agave Reception", "query": "Production of electricity", "location": "MX", "amount": 3.29e-03, "type": "technosphere"},

        # 2. Cooking Phase
        {"name": "Fuel Oil (Cooking)", "category": "Cooking", "query": "Production of fuel oil", "amount": 8.06e-01, "type": "technosphere"},
        {"name": "Water (Cooking)", "category": "Cooking", "query": "Collection, purification and distribution of water", "amount": 7.16e-01, "type": "technosphere"},
        {"name": "Electricity (Cooking)", "category": "Cooking", "query": "Production of electricity", "location": "MX", "amount": 1.19e-04, "type": "technosphere"},

        # 3. Grinding Phase
        {"name": "Electricity (Grinding)", "category": "Grinding", "query": "Production of electricity", "location": "MX", "amount": 1.01e-01, "type": "technosphere"},

        # 4. Fermentation Phase
        {"name": "Electricity (Fermentation)", "category": "Fermentation", "query": "Production of electricity", "location": "MX", "amount": 9.36e-02, "type": "technosphere"},
        {"name": "Yeast", "category": "Fermentation", "query": "Manufacture of food products", "amount": 4.44e-03, "type": "technosphere"},
        {"name": "CO2 Direct Emissions", "category": "Fermentation", "query": "Carbon dioxide, fossil", "db": "biosphere3", "amount": 3.17e-02, "type": "biosphere"},

        # 5. Distillation 1 & 2 Phase
        {"name": "Fuel Oil (Distillation)", "category": "Distillation", "query": "Production of fuel oil", "amount": 2.12e-03 + 1.33e-01, "type": "technosphere"},
        {"name": "Electricity (Distillation)", "category": "Distillation", "query": "Production of electricity", "location": "MX", "amount": 1.96e-01 + 8.08e-01, "type": "technosphere"},

        # 6. Post-Distillation Filtering, Rectification & Aging
        {"name": "Water (Rectification)", "category": "Aging & Filtering", "query": "Collection, purification and distribution of water", "amount": 1.97e-01, "type": "technosphere"},
        {"name": "Electricity (Filtering)", "category": "Aging & Filtering", "query": "Production of electricity", "location": "MX", "amount": 5.24e-04 + 7.21e-04 + 3.50e-04, "type": "technosphere"},
        {"name": "Activated Carbon Filters", "category": "Aging & Filtering", "query": "Manufacture of chemicals", "amount": 6.35e-06 + 1.13e-05, "type": "technosphere"},

        # 7. Bottling and Packaging Phase
        {"name": "Electricity (Bottling)", "category": "Packaging", "query": "Production of electricity", "location": "MX", "amount": 5.07e-04, "type": "technosphere"},
        {"name": "Glass Bottle (550g)", "category": "Packaging", "query": "Manufacture of glass", "amount": 5.50e-01, "type": "technosphere"},
        {"name": "Aluminum Cap", "category": "Packaging", "query": "Manufacture of aluminum", "amount": 9.80e-02, "type": "technosphere"},
        {"name": "Wooden Box", "category": "Packaging", "query": "Manufacture of wood products", "amount": 2.45e-01, "type": "technosphere"},
    ]


def build_tequila_lca_model(bw_module: Any, project_name: str = "Tequila_LCA_Mexico") -> Any:
    """
    Sets up Brightway project and constructs foreground activity.
    """
    bw_module.projects.set_current(project_name)
    logging.info(f"Active Brightway project set to '{project_name}'")

    if "biosphere3" not in bw_module.databases:
        logging.info("Initializing biosphere3 database...")
        bw_module.bw2setup()

    fg_name = "Tequila_Foreground"
    fg_db = bw_module.Database(fg_name)
    fg_db.register()

    # Define primary activity
    tequila_activity = fg_db.new_activity(
        code="reposado_700ml",
        name="100% Reposado Tequila Bottle (700ml, 6-month aged)",
        unit="unit",
        location="MX"
    )
    tequila_activity.save()

    exio_db = bw_module.Database("EXIOBASE_3") if "EXIOBASE_3" in bw_module.databases else None
    bio_db = bw_module.Database("biosphere3")

    recipe = get_tequila_inventory_recipe()

    for item in recipe:
        if item["type"] == "production":
            tequila_activity.new_exchange(input=tequila_activity.key, amount=item["amount"], type="production").save()
            continue

        target_db = bio_db if item.get("db") == "biosphere3" else exio_db
        if target_db is None:
            logging.warning(f"Database for '{item['name']}' not initialized. Skipping exchange binding in mock mode.")
            continue

        input_act = safe_search(target_db, item["query"], item.get("location"))
        tequila_activity.new_exchange(input=input_act.key, amount=item["amount"], type=item["type"]).save()

    logging.info("Tequila inventory model successfully assembled.")
    return tequila_activity


if __name__ == "__main__":
    print("Tequila LCA Model module ready.")
