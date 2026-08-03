import csv
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from lca_engine.models import FallbackEmissionFactor


class Command(BaseCommand):
    help = "Seeds Tier 3 Fallback Emission Factors into SQLite database from fallback_data.csv"

    def handle(self, *args, **options):
        csv_path = os.path.join(settings.BASE_DIR, "lca_engine", "data", "fallback_data.csv")
        if not os.path.exists(csv_path):
            self.stderr.write(self.style.ERROR(f"File not found: {csv_path}"))
            return

        seeded_count = 0
        updated_count = 0

        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                obj, created = FallbackEmissionFactor.objects.update_or_create(
                    django_field=row["django_field"].strip(),
                    reporting_year=int(row["reporting_year"].strip()),
                    indicator=row.get("indicator", "GWP100").strip(),
                    defaults={
                        "emission_factor": float(row["emission_factor"].strip()),
                        "unit": row["unit"].strip(),
                        "source_reference": row.get("source_reference", "").strip(),
                        "notes": row.get("notes", "").strip(),
                    }
                )
                if created:
                    seeded_count += 1
                else:
                    updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Successfully seeded FallbackEmissionFactor database: {seeded_count} created, {updated_count} updated."
        ))
