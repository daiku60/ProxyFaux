import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from api.models import CrewCard, Model, Upgrade


class Command(BaseCommand):
    help = (
        "Import the models, crewCards, and upgrades sections from backend/data/cards.json "
        "into the Model, CrewCard, and Upgrade tables."
    )

    def handle(self, *args, **options) -> None:
        backend_dir = Path(__file__).resolve().parents[3]
        cards_json_path = backend_dir / "data" / "cards.json"

        if not cards_json_path.exists():
            raise CommandError(f"Missing source file: {cards_json_path}")

        cards_data = json.loads(cards_json_path.read_text())
        raw_models = cards_data.get("models")
        raw_crew_cards = cards_data.get("crewCards")
        raw_upgrades = cards_data.get("upgrades")

        if not isinstance(raw_models, dict):
            raise CommandError("cards.json does not contain a valid 'models' object.")
        if not isinstance(raw_crew_cards, dict):
            raise CommandError("cards.json does not contain a valid 'crewCards' object.")
        if not isinstance(raw_upgrades, dict):
            raise CommandError("cards.json does not contain a valid 'upgrades' object.")

        model_created = 0
        model_updated = 0

        for source_id, payload in raw_models.items():
            if not isinstance(payload, dict):
                self.stderr.write(self.style.WARNING(f"Skipping invalid model payload: {source_id}"))
                continue

            defaults = {
                "name": payload.get("name", ""),
                "faction": payload.get("faction", ""),
                "pdf": payload.get("pdf", ""),
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
                model_created += 1
            else:
                model_updated += 1

        crew_card_created = 0
        crew_card_updated = 0

        for source_id, payload in raw_crew_cards.items():
            if not isinstance(payload, dict):
                self.stderr.write(
                    self.style.WARNING(f"Skipping invalid crew card payload: {source_id}")
                )
                continue

            defaults = {
                "name": payload.get("name", ""),
                "faction": payload.get("faction", ""),
                "pdf": payload.get("pdf", ""),
                "text": payload.get("text", ""),
                "keywords": payload.get("keywords", []),
                "tokens": payload.get("tokens", []),
                "files": payload.get("files", {}),
            }

            _, was_created = CrewCard.objects.update_or_create(
                source_id=source_id,
                defaults=defaults,
            )

            if was_created:
                crew_card_created += 1
            else:
                crew_card_updated += 1

        upgrade_created = 0
        upgrade_updated = 0

        for source_id, payload in raw_upgrades.items():
            if not isinstance(payload, dict):
                self.stderr.write(
                    self.style.WARNING(f"Skipping invalid upgrade payload: {source_id}")
                )
                continue

            defaults = {
                "name": payload.get("name", ""),
                "faction": payload.get("faction", ""),
                "pdf": payload.get("pdf", ""),
                "text": payload.get("text", ""),
                "keywords": payload.get("keywords", []),
                "tokens": payload.get("tokens", []),
                "files": payload.get("files", {}),
            }

            _, was_created = Upgrade.objects.update_or_create(
                source_id=source_id,
                defaults=defaults,
            )

            if was_created:
                upgrade_created += 1
            else:
                upgrade_updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Imported "
                f"{model_created + model_updated} models: "
                f"{model_created} created, {model_updated} updated. "
                f"Imported {crew_card_created + crew_card_updated} crew cards: "
                f"{crew_card_created} created, {crew_card_updated} updated. "
                f"Imported {upgrade_created + upgrade_updated} upgrades: "
                f"{upgrade_created} created, {upgrade_updated} updated."
            )
        )
