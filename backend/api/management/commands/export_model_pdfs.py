import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from api.models import Model


class Command(BaseCommand):
    help = (
        "Write each Model.pdf value back into the matching model entry "
        "in backend/data/cards.json."
    )

    def handle(self, *args, **options) -> None:
        backend_dir = Path(__file__).resolve().parents[3]
        cards_json_path = backend_dir / "data" / "cards.json"

        if not cards_json_path.exists():
            raise CommandError(f"Missing source file: {cards_json_path}")

        cards_data = json.loads(cards_json_path.read_text())
        raw_models = cards_data.get("models")

        if not isinstance(raw_models, dict):
            raise CommandError("cards.json does not contain a valid 'models' object.")

        updated = 0
        missing = 0

        for model in Model.objects.all():
            payload = raw_models.get(model.source_id)
            if not isinstance(payload, dict):
                missing += 1
                self.stderr.write(
                    self.style.WARNING(
                        f"Skipping missing or invalid cards.json model entry: {model.source_id}"
                    )
                )
                continue

            payload["pdf"] = model.pdf
            updated += 1

        cards_json_path.write_text(json.dumps(cards_data, indent=4))

        self.stdout.write(
            self.style.SUCCESS(
                f"Updated pdf values for {updated} models in {cards_json_path}. "
                f"Missing entries: {missing}."
            )
        )
