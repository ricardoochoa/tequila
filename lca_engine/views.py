"""
Django views for Tequila LCA Studio: Dashboard, Chart.js / Plotly JSON APIs, CSV Schema Mapper, & Tequila Class Benchmarking.
"""

import json
import pandas as pd
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from .models import Producer, Product, InventoryScenario, InventoryExchange, LCAResult
from .forms import CSVUploadForm, InventoryExchangeFormSet, GlobalParameterForm, CSVSchemaMapperForm, DynamicInventoryForm
from .services.bw_calculator import TequilaBWCalculator
from .services.csv_handler import parse_inventory_csv, generate_hotspot_csv, generate_lci_template_csv, parse_key_value_lci_csv
from .services.inventory_mapper import get_default_captured_payload, get_fields_by_category


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
        defaults={
            "description": "Standard cradle-to-gate inventory process.",
            "version": 1,
            "is_baseline": True,
            "captured_payload": get_default_captured_payload()
        }
    )
    if not scenario.captured_payload:
        scenario.captured_payload = get_default_captured_payload()
        scenario.save()
    return scenario


def dashboard_view(request):
    #scenario = get_or_create_default_producer_and_product()

    #fu_ml = float(request.GET.get("functional_unit", 700.0))
    #recycling_pct = float(request.GET.get("glass_recycling_rate", 12)) / 100.0
    #if request.GET:
        #enable_exio = request.GET.get("enable_exiobase") in ["on", "true", "True", "1"]
    #else:
        #enable_exio = True

    #calculator = TequilaBWCalculator()
    #results = calculator.calculate_lca(
        #scenario.captured_payload,
        #functional_unit_volume_ml=fu_ml,
        #glass_recycling_rate=recycling_pct,
        #enable_exiobase=enable_exio
    #)

    scenario = get_or_create_default_producer_and_product()

    # 1. Leer parámetros del GET (si se acaba de presionar "Recalcular")
    if request.GET:
        fu_ml = float(request.GET.get("functional_unit", 700.0))
        recycling_rate = float(request.GET.get("glass_recycling_rate", 12))
        enable_exio = request.GET.get("enable_exiobase") in ["on", "true", "True", "1"]
        
        # Guardar estos valores en la Sesión del usuario
        request.session["functional_unit"] = fu_ml
        request.session["glass_recycling_rate"] = recycling_rate
        request.session["enable_exiobase"] = enable_exio
    else:
        # 2. Si no hay GET (navegación normal), leer de la Sesión (con valores por defecto)
        fu_ml = float(request.session.get("functional_unit", 700.0))
        recycling_rate = float(request.session.get("glass_recycling_rate", 12.0))
        enable_exio = request.session.get("enable_exiobase", True)

    recycling_pct = recycling_rate / 100.0

    calculator = TequilaBWCalculator()
    results = calculator.calculate_lca(
        scenario.captured_payload,
        functional_unit_volume_ml=fu_ml,
        glass_recycling_rate=recycling_pct,
        enable_exiobase=enable_exio
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

    #param_form = GlobalParameterForm(initial={
        #"functional_unit": fu_ml,
        #"glass_recycling_rate": int(recycling_pct * 100),
        #"enable_exiobase": enable_exio
    #})

    param_form = GlobalParameterForm(initial={
        "functional_unit": fu_ml,
        "glass_recycling_rate": int(recycling_rate), # Usamos la variable entera
        "enable_exiobase": enable_exio
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
            "data_tier": h.get("data_tier", "Fallback"),
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
                "data_tier": wh.get("data_tier", "Fallback"),
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


def download_lci_template_view(request):
    """
    Exports standardized 4-column key-value CSV template (Nombre_Variable, Valor, Unidades, Notas).
    """
    csv_content = generate_lci_template_csv()
    response = HttpResponse(csv_content, content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="lci_inventory_template.csv"'
    return response


def inventory_edit_view(request):
    scenario = get_or_create_default_producer_and_product()
    upload_form = CSVUploadForm()
    payload = scenario.captured_payload or get_default_captured_payload()
    upload_errors = []

    if request.method == "POST":
        if "upload_csv" in request.POST:
            upload_form = CSVUploadForm(request.POST, request.FILES)
            if upload_form.is_valid():
                upload_mode = upload_form.cleaned_data.get("upload_mode", "replace")
                parsed_payload, errors = parse_key_value_lci_csv(request.FILES["csv_file"])

                if errors:
                    upload_errors = errors
                    dynamic_form = DynamicInventoryForm(payload=payload)
                else:
                    if upload_mode == "append":
                        merged_payload = dict(payload)
                        merged_payload.update(parsed_payload)
                        scenario.captured_payload = merged_payload
                    else:
                        scenario.captured_payload = parsed_payload
                    scenario.save()
                    return redirect("dashboard")
            else:
                dynamic_form = DynamicInventoryForm(payload=payload)
        else:
            dynamic_form = DynamicInventoryForm(request.POST, payload=payload)
            if dynamic_form.is_valid():
                scenario.captured_payload = dynamic_form.get_structured_payload()
                scenario.save()
                return redirect("dashboard")
    else:
        dynamic_form = DynamicInventoryForm(payload=payload)

    context = {
        "scenario": scenario,
        "dynamic_form": dynamic_form,
        "categories": get_fields_by_category(),
        "upload_form": upload_form,
        "upload_errors": upload_errors,
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
    
    # Leer el estado activo desde la sesión en lugar de GET
    fu_ml = float(request.session.get("functional_unit", 700.0))
    recycling_rate = float(request.session.get("glass_recycling_rate", 12.0))
    recycling_pct = recycling_rate / 100.0
    enable_exio = request.session.get("enable_exiobase", True)

    results = TequilaBWCalculator().calculate_lca(
        scenario.captured_payload,
        functional_unit_volume_ml=fu_ml,
        glass_recycling_rate=recycling_pct,
        enable_exiobase=enable_exio
    )

    csv_content = generate_hotspot_csv(results["hotspots"], results.get("water_hotspots"))
    response = HttpResponse(csv_content, content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="tequila_lca_hotspots_summary.csv"'
    return response

    #scenario = get_or_create_default_producer_and_product()
    #fu_ml = float(request.GET.get("functional_unit", 700.0))
    #recycling_pct = float(request.GET.get("glass_recycling_rate", 12)) / 100.0
    #if request.GET:
        #enable_exio = request.GET.get("enable_exiobase") in ["on", "true", "True", "1"]
    #else:
        #enable_exio = True

    #results = TequilaBWCalculator().calculate_lca(
        #scenario.captured_payload,
        #functional_unit_volume_ml=fu_ml,
        #glass_recycling_rate=recycling_pct,
        #enable_exiobase=enable_exio
    #)

    #csv_content = generate_hotspot_csv(results["hotspots"], results.get("water_hotspots"))
    #response = HttpResponse(csv_content, content_type="text/csv")
    #response["Content-Disposition"] = 'attachment; filename="tequila_lca_hotspots_summary.csv"'
    #return response
