"""
Django forms for inventory CSV uploads and live Formset editing.
"""

from django import forms
from django.forms import inlineformset_factory
from .models import InventoryScenario, InventoryExchange


class CSVUploadForm(forms.Form):
    csv_file = forms.FileField(
        label="Upload Inventory CSV",
        help_text="Select a CSV file with columns: stage_name, category, query, amount, unit, location, exchange_type"
    )


class InventoryExchangeForm(forms.ModelForm):
    class Meta:
        model = InventoryExchange
        fields = ["stage_name", "category", "query", "amount", "unit", "location", "exchange_type"]
        widgets = {
            "stage_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Stage Name"}),
            "category": forms.TextInput(attrs={"class": "form-control", "placeholder": "Category"}),
            "query": forms.TextInput(attrs={"class": "form-control", "placeholder": "Background Database Query"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "any"}),
            "unit": forms.TextInput(attrs={"class": "form-control", "placeholder": "Unit"}),
            "location": forms.TextInput(attrs={"class": "form-control", "placeholder": "Location (e.g. MX)"}),
            "exchange_type": forms.Select(attrs={"class": "form-select"}),
        }


InventoryExchangeFormSet = inlineformset_factory(
    InventoryScenario,
    InventoryExchange,
    form=InventoryExchangeForm,
    extra=1,
    can_delete=True
)
