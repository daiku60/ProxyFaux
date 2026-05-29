import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from api.models import Model


class Command(BaseCommand):
    help = "Import the models section from backend/data/cards.json into the Model table."

    def handle(self, *args, **options) -> None:
        backend_dir = Path(__file__).resolve().parents[3]
        cards_json_path = backend_dir / "data" / "cards.json"

        if not cards_json_path.exists():
            raise CommandError(f"Missing source file: {cards_json_path}")

        cards_data = json.loads(cards_json_path.read_text())
        raw_models = cards_data.get("models")

        if not isinstance(raw_models, dict):
            raise CommandError("cards.json does not contain a valid 'models' object.")

        created = 0
        updated = 0

        for source_id, payload in raw_models.items():
            if not isinstance(payload, dict):
                self.stderr.write(self.style.WARNING(f"Skipping invalid model payload: {source_id}"))
                continue

            defaults = {
                "name": payload.get("name", ""),
                "faction": payload.get("faction", ""),
                "station": payload.get("station", ""),
                "text": payload.get("text", ""),
                "title": payload.get("title", ""),
                "crew_card": payload.get("crewCard", ""),
                "totem_id": payload.get("totemId", ""),
                "characteristics": payload.get("characteristics", []),
                "keywords": payload.get("keywords", []),
                "tokens": payload.get("tokens", []),
                "alternates": payload.get("alternates", []),
                "meta": payload.get("meta", {}),
                "files": payload.get("files", {}),
                "stats": payload.get("stats", {}),
            }

            _, was_created = Model.objects.update_or_create(
                source_id=source_id,
                defaults=defaults,
            )

            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {created + updated} models: {created} created, {updated} updated."
            )
        )
