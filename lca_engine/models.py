"""
Django database models for Tequila LCA scenarios and inventory exchanges.
"""

from django.db import models


class InventoryScenario(models.Model):
    name = models.CharField(max_length=200, default="100% Reposado Tequila (700ml)")
    description = models.TextField(blank=True, default="Standard cradle-to-gate inventory for aged tequila.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class InventoryExchange(models.Model):
    EXCHANGE_TYPES = (
        ("technosphere", "Technosphere Input"),
        ("biosphere", "Biosphere Emission"),
        ("production", "Production Output"),
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
