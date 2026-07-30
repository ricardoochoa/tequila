"""
Django database models for Tequila LCA scenarios, producers, products, and inventory exchanges.
"""

from django.db import models


class Producer(models.Model):
    name = models.CharField(max_length=200, help_text="Producer or Distillery Name")
    location = models.CharField(max_length=100, default="Jalisco, Mexico")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    TEQUILA_CLASSES = (
        ("blanco", "Blanco / Silver (Unaged)"),
        ("reposado", "Reposado (Aged 2-12 months)"),
        ("anejo", "Añejo (Aged 1-3 years)"),
        ("extra_anejo", "Extra Añejo (Aged 3+ years)"),
    )

    producer = models.ForeignKey(Producer, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=200)
    tequila_class = models.CharField(max_length=20, choices=TEQUILA_CLASSES, default="reposado")
    bottle_weight_g = models.FloatField(default=550.0, help_text="Weight of glass bottle in grams")
    aging_months = models.IntegerField(default=6, help_text="Months spent in oak barrels")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.get_tequila_class_display()})"


class InventoryScenario(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="scenarios", null=True, blank=True)
    name = models.CharField(max_length=200, default="Standard Inventory Scenario")
    description = models.TextField(blank=True, default="Cradle-to-gate inventory process.")
    version = models.IntegerField(default=1)
    is_baseline = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (v{self.version})"


class InventoryExchange(models.Model):
    EXCHANGE_TYPES = (
        ("technosphere", "Technosphere Input"),
        ("biosphere", "Biosphere Emission"),
        ("production", "Production Output"),
        ("byproduct", "Byproduct Credit"),
    )

    scenario = models.ForeignKey(InventoryScenario, on_delete=models.CASCADE, related_name="exchanges")
    stage_name = models.CharField(max_length=150)
    category = models.CharField(max_length=100, default="General")
    query = models.CharField(max_length=255, blank=True, help_text="Search query for background database matching")
    amount = models.FloatField(default=0.0)
    unit = models.CharField(max_length=30, default="kg")
    location = models.CharField(max_length=10, blank=True, null=True, default="MX")
    exchange_type = models.CharField(max_length=20, choices=EXCHANGE_TYPES, default="technosphere")

    def __str__(self):
        return f"{self.stage_name} ({self.amount} {self.unit})"


class LCAResult(models.Model):
    scenario = models.OneToOneField(InventoryScenario, on_delete=models.CASCADE, related_name="lca_result")
    gwp_total = models.FloatField(default=0.0, help_text="Total Climate Footprint in kg CO2-eq")
    water_footprint_aware = models.FloatField(default=0.0, help_text="AWARE Water Scarcity Footprint in m3 world-eq")
    biogenic_co2 = models.FloatField(default=0.0, help_text="Direct biogenic CO2 emissions in kg")
    raw_json_results = models.JSONField(default=dict, help_text="Complete calculation payload for client charts")
    calculated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"LCA Result for {self.scenario.name} (GWP: {self.gwp_total})"
