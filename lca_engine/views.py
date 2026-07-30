"""
Django views for Tequila LCA Studio: Dashboard, Chart.js / Plotly JSON APIs, CSV Schema Mapper, & Tequila Class Benchmarking.
"""

import json
import pandas as pd
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from .models import Producer, Product, InventoryScenario, InventoryExchange, LCAResult
from .forms import CSVUploadForm, InventoryExchangeFormSet, GlobalParameterForm, CSVSchemaMapperForm
from .services.bw_calculator import TequilaBWCalculator
from .services.csv_handler import parse_inventory_csv, generate_hotspot_csv


def get_or_create_default_producer_and_product():
    producer, _ = Producer.objects.get_or_create(
        name="Destilería Los Altos",
        defaults={"location": "Jalisco, Mexico"}
    )
    product, _ = Product.objects.get_or_create(
        producer=producer,
        name="100% Reposado Tequila",
        defaults={"tequila_class": "reposado", "bottle_weight_g": 550.0, "aging_months": 6}
    )
    scenario, created = InventoryScenario.objects.get_or_create(
        product=product,
        name="100% Reposado Tequila (Baseline)",
        defaults={"description": "Standard cradle-to-gate inventory process.", "version": 1, "is_baseline": True}
    )
    if created or scenario.exchanges.count() == 0:
        defaults = [
            {"stage_name": "Reposado Tequila Output", "category": "Production", "query": "", "amount": 1.0, "unit": "unit", "location": "MX", "exchange_type": "production"},
            {"stage_name": "Agave pineapple", "category": "Agave Reception", "query": "Cultivation of crops", "amount": 8.62, "unit": "kg", "location": "MX", "exchange_type": "technosphere"},
            {"stage_name": "Electricity (Reception)", "category": "Agave Reception", "query": "Production of electricity", "amount": 3.29e-03, "unit": "kWh", "location": "MX", "exchange_type": "technosphere"},
            {"stage_name": "Fuel Oil (Cooking)", "category": "Cooking", "query": "Production of fuel oil", "amount": 8.06e-01, "unit": "kg", "location": "", "exchange_type": "technosphere"},
            {"stage_name": "Water (Cooking)", "category": "Cooking", "query": "Collection, purification and distribution of water", "amount": 7.16e-01, "unit": "L", "location": "", "exchange_type": "technosphere"},
            {"stage_name": "Electricity (Grinding)", "category": "Grinding", "query": "Production of electricity", "amount": 1.01e-01, "unit": "kWh", "location": "MX", "exchange_type": "technosphere"},
            {"stage_name": "Electricity (Fermentation)", "category": "Fermentation", "query": "Production of electricity", "amount": 9.36e-02, "unit": "kWh", "location": "MX", "exchange_type": "technosphere"},
            {"stage_name": "Yeast", "category": "Fermentation", "query": "Manufacture of food products", "amount": 4.44e-03, "unit": "kg", "location": "", "exchange_type": "technosphere"},
            {"stage_name": "CO2 Direct Emissions", "category": "Fermentation", "query": "Carbon dioxide, fossil", "amount": 3.17e-02, "unit": "kg", "location": "", "exchange_type": "biosphere"},
            {"stage_name": "Fuel Oil (Distillation)", "category": "Distillation", "query": "Production of fuel oil", "amount": 1.35e-01, "unit": "kg", "location": "", "exchange_type": "technosphere"},
            {"stage_name": "Electricity (Distillation)", "category": "Distillation", "query": "Production of electricity", "amount": 1.004, "unit": "kWh", "location": "MX", "exchange_type": "technosphere"},
            {"stage_name": "Glass Bottle (550g)", "category": "Packaging", "query": "Manufacture of glass", "amount": 5.50e-01, "unit": "kg", "location": "", "exchange_type": "technosphere"},
            {"stage_name": "Aluminum Cap", "category": "Packaging", "query": "Manufacture of aluminum", "amount": 9.80e-02, "unit": "kg", "location": "", "exchange_type": "technosphere"},
            {"stage_name": "Wooden Box", "category": "Packaging", "query": "Manufacture of wood products", "amount": 2.45e-01, "unit": "kg", "location": "", "exchange_type": "technosphere"},
            {"stage_name": "Bagasse Bio-energy Credit", "category": "Byproduct Credit", "query": "bagasse", "amount": 1.42, "unit": "kg", "location": "MX", "exchange_type": "byproduct"},
        ]
        for d in defaults:
            InventoryExchange.objects.create(scenario=scenario, **d)
    return scenario


def dashboard_view(request):
    scenario = get_or_create_default_producer_and_product()

    fu_ml = float(request.GET.get("functional_unit", 700.0))
    recycling_pct = float(request.GET.get("glass_recycling_rate", 12)) / 100.0

    exchanges = scenario.exchanges.all()
    calc_list = [{"name": e.stage_name, "query": e.query, "amount": e.amount, "location": e.location, "type": e.exchange_type, "category": e.category} for e in exchanges]

    calculator = TequilaBWCalculator()
    results = calculator.calculate_lca(
        calc_list,
        functional_unit_volume_ml=fu_ml,
        glass_recycling_rate=recycling_pct
    )

    # Save to LCAResult model
    LCAResult.objects.update_or_create(
        scenario=scenario,
        defaults={
            "gwp_total": results["gwp_score"],
            "water_footprint_aware": results["water_footprint_aware"],
            "biogenic_co2": results["biogenic_co2"],
            "raw_json_results": results
        }
    )

    param_form = GlobalParameterForm(initial={
        "functional_unit": fu_ml,
        "glass_recycling_rate": int(recycling_pct * 100)
    })

    # Generate combined hotspots list for side-by-side table display
    water_dict = {wh["stage"]: wh for wh in results.get("water_hotspots", [])}
    combined_hotspots = []
    seen_stages = set()
    for h in results.get("hotspots", []):
        stage = h["stage"]
        seen_stages.add(stage)
        wh = water_dict.get(stage, {})
        combined_hotspots.append({
            "stage": stage,
            "gwp_score": h.get("gwp_score", 0.0),
            "gwp_pct": h.get("pct", 0.0),
            "water_score": wh.get("water_score", 0.0),
            "water_pct": wh.get("pct", 0.0),
        })
    for wh in results.get("water_hotspots", []):
        stage = wh["stage"]
        if stage not in seen_stages:
            combined_hotspots.append({
                "stage": stage,
                "gwp_score": 0.0,
                "gwp_pct": 0.0,
                "water_score": wh.get("water_score", 0.0),
                "water_pct": wh.get("pct", 0.0),
            })

    context = {
        "scenario": scenario,
        "results": results,
        "results_json": json.dumps(results),
        "param_form": param_form,
        "combined_hotspots": combined_hotspots,
    }
    return render(request, "lca_engine/dashboard.html", context)


def inventory_edit_view(request):
    scenario = get_or_create_default_producer_and_product()
    upload_form = CSVUploadForm()

    if request.method == "POST":
        if "upload_csv" in request.POST:
            upload_form = CSVUploadForm(request.POST, request.FILES)
            if upload_form.is_valid():
                upload_mode = upload_form.cleaned_data.get("upload_mode", "replace")
                parsed_exchanges = parse_inventory_csv(request.FILES["csv_file"])
                
                if upload_mode == "replace":
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


def benchmark_view(request):
    scenario = get_or_create_default_producer_and_product()
    producer = Producer.objects.first() or scenario.product.producer

    class_configs = [
        ("blanco", "Blanco (Unaged)", 4.85, 2.15),
        ("reposado", "Reposado (6m)", 8.16, 3.42),
        ("anejo", "Añejo (18m)", 9.45, 4.10),
        ("extra_anejo", "Extra Añejo (36m)", 11.20, 4.85),
    ]

    labels = []
    gwp_values = []
    water_values = []

    for key, display_name, fallback_gwp, fallback_water in class_configs:
        labels.append(display_name)
        product = Product.objects.filter(tequila_class=key).first()
        gwp = fallback_gwp
        water = fallback_water
        if product:
            p_scenario = product.scenarios.first()
            if p_scenario:
                lca_res = LCAResult.objects.filter(scenario=p_scenario).first()
                if lca_res:
                    gwp = float(lca_res.gwp_total)
                    water = float(lca_res.water_footprint_aware)
        gwp_values.append(gwp)
        water_values.append(water)

    benchmark_data = {
        "labels": labels,
        "gwp": gwp_values,
        "water": water_values,
    }

    context = {
        "producer": producer,
        "benchmark_json": json.dumps(benchmark_data)
    }
    return render(request, "lca_engine/benchmark.html", context)



def export_csv_view(request):
    scenario = get_or_create_default_producer_and_product()
    exchanges = scenario.exchanges.all()
    calc_list = [{"name": e.stage_name, "query": e.query, "amount": e.amount, "location": e.location, "type": e.exchange_type, "category": e.category} for e in exchanges]
    results = TequilaBWCalculator().calculate_lca(calc_list)

    csv_content = generate_hotspot_csv(results["hotspots"], results.get("water_hotspots"))
    response = HttpResponse(csv_content, content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="tequila_lca_hotspots_summary.csv"'
    return response
