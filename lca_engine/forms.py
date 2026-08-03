"""
Forms for Dynamic Inventory Mapping, CSV Uploads, and Global LCA Parameters.
"""

from django import forms
from django.forms import inlineformset_factory
from .models import InventoryScenario, InventoryExchange
from .services.inventory_mapper import get_fields_by_category, get_default_captured_payload


class DynamicInventoryForm(forms.Form):
    """
    Dynamically generates Django form fields grouped by inventory_map.json phases.
    Supports inputting activity amounts and optional Tier 1 supplier factors.
    """

    VINASSE_TREATMENT_CHOICES = (
        ("pit", "Fosa Abierta (Open Lagoon/Pit)"),
        ("biodigestor", "Biodigestor (Anaerobic Digestion)"),
        ("irrigation", "Riego Agrícola (Land Application)"),
        ("aerobic", "Planta Aerobia (Aerobic Treatment Plant)"),
    )

    def __init__(self, *args, payload: dict = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.payload = payload or get_default_captured_payload()
        self.categories = get_fields_by_category()

        for cat_name, cat_data in self.categories.items():
            for field in cat_data["fields"]:
                fname = field["django_field"]
                ftype = field.get("type", "FloatField")
                unit = field.get("capture_unit", "")
                label = field.get("ui_label_es", fname)
                if unit and unit != "Choice":
                    label_text = f"{label} ({unit})"
                else:
                    label_text = label
                help_text = field.get("ui_description_es", "")

                initial_val = None
                initial_tier1 = None
                if isinstance(self.payload, dict) and fname in self.payload:
                    item_payload = self.payload[fname]
                    if isinstance(item_payload, dict):
                        initial_val = item_payload.get("amount")
                        initial_tier1 = item_payload.get("tier1_factor")
                    else:
                        initial_val = item_payload

                if unit == "Choice" or fname == "vinasse_treatment":
                    self.fields[fname] = forms.ChoiceField(
                        choices=self.VINASSE_TREATMENT_CHOICES,
                        initial=initial_val or "pit",
                        label=label_text,
                        help_text=help_text,
                        widget=forms.Select(attrs={"class": "form-select"})
                    )
                else:
                    self.fields[fname] = forms.FloatField(
                        initial=initial_val if initial_val is not None else 0.0,
                        required=False,
                        label=label_text,
                        help_text=help_text,
                        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"})
                    )
                    tier1_name = f"{fname}_tier1"
                    self.fields[tier1_name] = forms.FloatField(
                        initial=initial_tier1,
                        required=False,
                        label=f"Factor Proveedor Tier 1 ({label})",
                        help_text="Opcional: Factor de emisión directo verificado por el proveedor",
                        widget=forms.NumberInput(attrs={
                            "class": "form-control supplier-factor",
                            "step": "any",
                            "placeholder": "Tier 1 Overwrite"
                        })
                    )

    def get_categorized_fields(self):
        """
        Returns a list of category dicts with bound form fields for Django templates.
        """
        categorized = []
        for cat_name, cat_data in self.categories.items():
            field_list = []
            for f_info in cat_data["fields"]:
                fname = f_info["django_field"]
                tier1_fname = f"{fname}_tier1"
                bound_f = self[fname] if fname in self.fields else None
                bound_t1 = self[tier1_fname] if tier1_fname in self.fields else None
                field_list.append({
                    "info": f_info,
                    "bound_field": bound_f,
                    "bound_tier1_field": bound_t1
                })
            categorized.append({
                "category_name": cat_name,
                "metadata": cat_data.get("metadata", {}),
                "fields": field_list
            })
        return categorized

    def get_structured_payload(self) -> dict:
        """
        Constructs captured_payload dict from cleaned_data.
        """
        cleaned = self.cleaned_data
        result = {}
        for cat_name, cat_data in self.categories.items():
            for field in cat_data["fields"]:
                fname = field["django_field"]
                val = cleaned.get(fname)
                tier1_val = cleaned.get(f"{fname}_tier1")
                result[fname] = {
                    "amount": val if val is not None else 0.0,
                    "tier1_factor": tier1_val if tier1_val is not None else None
                }
        return result


class CSVUploadForm(forms.Form):
    UPLOAD_MODES = (
        ("replace", "Replace existing inventory"),
        ("append", "Append to existing inventory"),
    )

    csv_file = forms.FileField(
        label="Upload Inventory CSV",
        help_text="Select a CSV file formatted as: Nombre_Variable, Valor, Unidades, Notas"
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
        fields = ["stage_name", "category", "query", "amount", "unit", "location", "exchange_type", "supplier_gwp_factor", "supplier_water_factor"]
        widgets = {
            "stage_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Stage Name"}),
            "category": forms.TextInput(attrs={"class": "form-control", "placeholder": "Category"}),
            "query": forms.TextInput(attrs={"class": "form-control", "placeholder": "Background Database Query"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "any"}),
            "unit": forms.TextInput(attrs={"class": "form-control", "placeholder": "Unit"}),
            "location": forms.TextInput(attrs={"class": "form-control", "placeholder": "Location (e.g. MX)"}),
            "exchange_type": forms.Select(attrs={"class": "form-select"}),
            "supplier_gwp_factor": forms.NumberInput(attrs={"class": "form-control supplier-factor", "step": "any", "placeholder": "Tier 1 GWP Factor"}),
            "supplier_water_factor": forms.NumberInput(attrs={"class": "form-control supplier-factor", "step": "any", "placeholder": "Tier 1 Water Factor"}),
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
    enable_exiobase = forms.BooleanField(
        required=False,
        initial=True,
        label="Enable EXIOBASE 3 Background Database (Tier 2)",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )
