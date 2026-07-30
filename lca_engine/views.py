"""
Django views for Tequila LCA Web Application dashboard, inventory forms, and exports.
"""

import os
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, Http404
from django.conf import settings
from .models import InventoryScenario, InventoryExchange
from .forms import CSVUploadForm, InventoryExchangeFormSet
from .services.bw_calculator import TequilaBWCalculator
from .services.csv_handler import parse_inventory_csv, generate_hotspot_csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns


def get_or_create_default_scenario():
    scenario, created = InventoryScenario.objects.get_or_create(
        name="100% Reposado Tequila Bottle (700ml)",
        defaults={"description": "Default cradle-to-gate inventory process."}
    )
    if created:
        # Populate initial paper baseline
        defaults = [
            {"stage_name": "Reposado Tequila Bottle Output", "category": "Production", "query": "", "amount": 1.0, "unit": "unit", "location": "MX", "exchange_type": "production"},
            {"stage_name": "Agave pineapple", "category": "Agave Reception", "query": "Cultivation of crops", "amount": 8.62, "unit": "kg", "location": "MX", "exchange_type": "technosphere"},
            {"stage_name": "Electricity (Reception)", "category": "Agave Reception", "query": "Production of electricity", "amount": 3.29e-03, "unit": "kWh", "location": "MX", "exchange_type": "technosphere"},
            {"stage_name": "Fuel Oil (Cooking)", "category": "Cooking", "query": "Production of fuel oil", "amount": 8.06e-01, "unit": "kg", "location": "", "exchange_type": "technosphere"},
            {"stage_name": "Water (Cooking)", "category": "Cooking", "query": "Collection, purification and distribution of water", "amount": 7.16e-01, "unit": "L", "location": "", "exchange_type": "technosphere"},
            {"stage_name": "Electricity (Cooking)", "category": "Cooking", "query": "Production of electricity", "amount": 1.19e-04, "unit": "kWh", "location": "MX", "exchange_type": "technosphere"},
            {"stage_name": "Electricity (Grinding)", "category": "Grinding", "query": "Production of electricity", "amount": 1.01e-01, "unit": "kWh", "location": "MX", "exchange_type": "technosphere"},
            {"stage_name": "Electricity (Fermentation)", "category": "Fermentation", "query": "Production of electricity", "amount": 9.36e-02, "unit": "kWh", "location": "MX", "exchange_type": "technosphere"},
            {"stage_name": "Yeast", "category": "Fermentation", "query": "Manufacture of food products", "amount": 4.44e-03, "unit": "kg", "location": "", "exchange_type": "technosphere"},
            {"stage_name": "CO2 Direct Emissions", "category": "Fermentation", "query": "Carbon dioxide, fossil", "amount": 3.17e-02, "unit": "kg", "location": "", "exchange_type": "biosphere"},
            {"stage_name": "Fuel Oil (Distillation)", "category": "Distillation", "query": "Production of fuel oil", "amount": 1.35e-01, "unit": "kg", "location": "", "exchange_type": "technosphere"},
            {"stage_name": "Electricity (Distillation)", "category": "Distillation", "query": "Production of electricity", "amount": 1.004, "unit": "kWh", "location": "MX", "exchange_type": "technosphere"},
            {"stage_name": "Glass Bottle (550g)", "category": "Packaging", "query": "Manufacture of glass", "amount": 5.50e-01, "unit": "kg", "location": "", "exchange_type": "technosphere"},
            {"stage_name": "Aluminum Cap", "category": "Packaging", "query": "Manufacture of aluminum", "amount": 9.80e-02, "unit": "kg", "location": "", "exchange_type": "technosphere"},
            {"stage_name": "Wooden Box", "category": "Packaging", "query": "Manufacture of wood products", "amount": 2.45e-01, "unit": "kg", "location": "", "exchange_type": "technosphere"},
        ]
        for d in defaults:
            InventoryExchange.objects.create(scenario=scenario, **d)
    return scenario


def dashboard_view(request):
    scenario = get_or_create_default_scenario()
    exchanges = scenario.exchanges.all()

    # Format exchanges for calculation engine
    calc_list = []
    for exc in exchanges:
        calc_list.append({
            "name": exc.stage_name,
            "query": exc.query,
            "amount": exc.amount,
            "location": exc.location,
            "type": exc.exchange_type
        })

    calculator = TequilaBWCalculator()
    results = calculator.calculate_lca(calc_list)

    # Render Matplotlib Chart into media
    chart_url = None
    if results["hotspots"]:
        stages = [h["stage"] for h in results["hotspots"][:6]]
        pcts = [h["pct"] for h in results["hotspots"][:6]]

        plt.figure(figsize=(9, 4))
        sns.barplot(x=pcts, y=stages, palette="viridis")
        plt.title("Climate Footprint (GWP100) Hotspot Analysis")
        plt.xlabel("Share of Total Carbon Footprint (%)")
        plt.ylabel("Lifecycle Process")
        plt.tight_layout()

        media_dir = os.path.join(settings.BASE_DIR, "media")
        os.makedirs(media_dir, exist_ok=True)
        chart_path = os.path.join(media_dir, "tequila_hotspot_chart.png")
        plt.savefig(chart_path, dpi=300)
        plt.close()
        chart_url = "/media/tequila_hotspot_chart.png"

    context = {
        "scenario": scenario,
        "results": results,
        "chart_url": chart_url,
    }
    return render(request, "lca_engine/dashboard.html", context)


def inventory_edit_view(request):
    scenario = get_or_create_default_scenario()
    upload_form = CSVUploadForm()

    if request.method == "POST":
        if "upload_csv" in request.POST:
            upload_form = CSVUploadForm(request.POST, request.FILES)
            if upload_form.is_valid():
                parsed_exchanges = parse_inventory_csv(request.FILES["csv_file"])
                scenario.exchanges.all().delete()
                for item in parsed_exchanges:
                    InventoryExchange.objects.create(
                        scenario=scenario,
                        stage_name=item["name"],
                        category=item["category"],
                        query=item["query"],
                        amount=item["amount"],
                        unit=item["unit"],
                        location=item["location"],
                        exchange_type=item["type"]
                    )
                return redirect("dashboard")
        else:
            formset = InventoryExchangeFormSet(request.POST, instance=scenario)
            if formset.is_valid():
                formset.save()
                return redirect("dashboard")

    formset = InventoryExchangeFormSet(instance=scenario)
    context = {
        "scenario": scenario,
        "formset": formset,
        "upload_form": upload_form,
    }
    return render(request, "lca_engine/inventory_form.html", context)


def export_csv_view(request):
    scenario = get_or_create_default_scenario()
    exchanges = scenario.exchanges.all()
    calc_list = [{"name": e.stage_name, "query": e.query, "amount": e.amount, "location": e.location, "type": e.exchange_type} for e in exchanges]
    results = TequilaBWCalculator().calculate_lca(calc_list)

    csv_content = generate_hotspot_csv(results["hotspots"])
    response = HttpResponse(csv_content, content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="tequila_gwp_process_contribution.csv"'
    return response
