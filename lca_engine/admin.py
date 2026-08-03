from django.contrib import admin
from .models import Producer, Product, InventoryScenario, InventoryExchange, LCAResult, FallbackEmissionFactor


@admin.register(FallbackEmissionFactor)
class FallbackEmissionFactorAdmin(admin.ModelAdmin):
    list_display = ("django_field", "reporting_year", "emission_factor", "unit", "indicator", "source_reference")
    list_filter = ("reporting_year", "indicator")
    search_fields = ("django_field", "source_reference", "notes")


@admin.register(Producer)
class ProducerAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "created_at")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "tequila_class", "producer", "bottle_weight_g", "aging_months")


@admin.register(InventoryScenario)
class InventoryScenarioAdmin(admin.ModelAdmin):
    list_display = ("name", "product", "version", "is_baseline", "updated_at")


@admin.register(InventoryExchange)
class InventoryExchangeAdmin(admin.ModelAdmin):
    list_display = ("stage_name", "scenario", "category", "amount", "unit", "exchange_type")


@admin.register(LCAResult)
class LCAResultAdmin(admin.ModelAdmin):
    list_display = ("scenario", "gwp_total", "water_footprint_aware", "biogenic_co2", "calculated_at")

