"""
Forms for CSV Schema Mapping, CSV Uploads, Formsets, and Global Parameters.
"""

from django import forms
from django.forms import inlineformset_factory
from .models import InventoryScenario, InventoryExchange


class CSVUploadForm(forms.Form):
    UPLOAD_MODES = (
        ("replace", "Replace existing inventory"),
        ("append", "Append to existing inventory"),
    )

    csv_file = forms.FileField(
        label="Upload Inventory CSV",
        help_text="Select a CSV file with columns: stage_name, category, query, amount, unit, location, exchange_type"
    )
    upload_mode = forms.ChoiceField(
        choices=UPLOAD_MODES,
        initial="replace",
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
        label="Upload Mode"
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


class CSVSchemaMapperForm(forms.Form):
    stage_name_col = forms.ChoiceField(label="Stage Name Column")
    category_col = forms.ChoiceField(label="Category Column")
    query_col = forms.ChoiceField(label="Background Search Query Column")
    amount_col = forms.ChoiceField(label="Amount Column")
    unit_col = forms.ChoiceField(label="Unit Column")
    location_col = forms.ChoiceField(label="Location Column")

    def __init__(self, *args, csv_columns=None, **kwargs):
        super().__init__(*args, **kwargs)
        if csv_columns:
            choices = [(col, col) for col in csv_columns]
            for field_name in self.fields:
                self.fields[field_name].choices = choices


class GlobalParameterForm(forms.Form):
    FUNCTIONAL_UNITS = (
        (700.0, "700ml Bottle (Standard EU/MX)"),
        (750.0, "750ml Bottle (Standard US)"),
        (1000.0, "1,000ml (1 Litre) Bottle"),
    )

    functional_unit = forms.TypedChoiceField(
        choices=FUNCTIONAL_UNITS,
        coerce=float,
        initial=700.0,
        label="Functional Unit",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    glass_recycling_rate = forms.IntegerField(
        min_value=0,
        max_value=100,
        initial=12,
        label="Glass Recycling Rate (%)",
        widget=forms.NumberInput(attrs={"class": "form-control", "type": "range", "min": "0", "max": "100", "step": "1", "oninput": "this.nextElementSibling.value = this.value + '%'"})
    )

