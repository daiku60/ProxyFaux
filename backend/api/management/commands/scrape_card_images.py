import json
from pathlib import Path
from typing import Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen

from django.core.management.base import BaseCommand, CommandError

FIREBASE_BASE_URL = "https://firebasestorage.googleapis.com/v0/b/playwyrd.firebasestorage.app/o/"
DEFAULT_MEDIA_TOKEN = "a8b4396c-13f1-4aba-b1b8-3f24fdb5247d"


def iter_card_paths(value: object) -> Iterator[str]:
    if isinstance(value, str):
        if value.startswith("cards/"):
            yield value
        return

    if isinstance(value, dict):
        for nested_value in value.values():
            yield from iter_card_paths(nested_value)
        return

    if isinstance(value, list):
        for nested_value in value:
            yield from iter_card_paths(nested_value)


def build_media_url(relative_path: str, token: str) -> str:
    encoded_path = quote(relative_path, safe="")
    return f"{FIREBASE_BASE_URL}{encoded_path}?alt=media&token={token}"


def fetch_download_token(relative_path: str) -> str | None:
    encoded_path = quote(relative_path, safe="")
    metadata_url = f"{FIREBASE_BASE_URL}{encoded_path}"

    with urlopen(metadata_url) as response:  # noqa: S310
        metadata = json.loads(response.read().decode("utf-8"))

    tokens = metadata.get("downloadTokens")
    if not tokens:
        return None

    return str(tokens).split(",")[0].strip() or None


class Command(BaseCommand):
    help = "Download card images referenced by backend/data/cards.json into backend/data/."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-download files even when they already exist locally.",
        )
        parser.add_argument(
            "--token",
            default=DEFAULT_MEDIA_TOKEN,
            help="Firebase media token appended to the download URL.",
        )

    def handle(self, *args, **options) -> None:
        backend_dir = Path(__file__).resolve().parents[3]
        data_dir = backend_dir / "data"
        cards_json_path = data_dir / "cards.json"
        report_path = data_dir / "card_image_download_report.json"

        if not cards_json_path.exists():
            raise CommandError(f"Missing source file: {cards_json_path}")

        cards_data = json.loads(cards_json_path.read_text())
        relative_paths = sorted(set(iter_card_paths(cards_data)))

        if not relative_paths:
            self.stdout.write(self.style.WARNING("No card image paths were found in cards.json."))
            return

        force_download = options["force"]
        media_token = options["token"]
        downloaded = 0
        skipped = 0
        failed = 0
        report: list[dict[str, object]] = []

        for relative_path in relative_paths:
            destination_path = data_dir / relative_path
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            report_entry: dict[str, object] = {
                "path": relative_path,
                "destination": str(destination_path),
                "status": "",
                "initial_url": build_media_url(relative_path, media_token),
                "retry_url": None,
                "error": None,
            }

            if destination_path.exists() and not force_download:
                skipped += 1
                self.stdout.write(f"Skipping existing file: {relative_path}")
                report_entry["status"] = "skipped_existing"
                report.append(report_entry)
                continue

            self.stdout.write(f"Downloading {relative_path}")

            try:
                image_url = str(report_entry["initial_url"])
                self.stdout.write(f"  URL: {image_url}")
                with urlopen(image_url) as response:  # noqa: S310
                    destination_path.write_bytes(response.read())
                downloaded += 1
                report_entry["status"] = "downloaded"
            except HTTPError as exc:
                if exc.code == 404:
                    try:
                        resolved_token = fetch_download_token(relative_path)
                    except (HTTPError, URLError, json.JSONDecodeError) as metadata_exc:
                        failed += 1
                        error_message = (
                            "metadata lookup failed: "
                            f"{type(metadata_exc).__name__}: {metadata_exc}"
                        )
                        self.stderr.write(
                            self.style.WARNING(f"Failed for {relative_path}: {error_message}")
                        )
                        report_entry["status"] = "failed"
                        report_entry["error"] = error_message
                        report.append(report_entry)
                        continue

                    if not resolved_token:
                        failed += 1
                        error_message = "metadata lookup returned no download token"
                        self.stderr.write(
                            self.style.WARNING(f"Failed for {relative_path}: {error_message}")
                        )
                        report_entry["status"] = "failed"
                        report_entry["error"] = error_message
                        report.append(report_entry)
                        continue

                    retry_url = build_media_url(relative_path, resolved_token)
                    report_entry["retry_url"] = retry_url
                    self.stdout.write(f"  Retry URL: {retry_url}")

                    try:
                        with urlopen(retry_url) as response:  # noqa: S310
                            destination_path.write_bytes(response.read())
                        downloaded += 1
                        report_entry["status"] = "downloaded_after_retry"
                    except (HTTPError, URLError) as retry_exc:
                        failed += 1
                        error_message = f"{type(retry_exc).__name__}: {retry_exc}"
                        self.stderr.write(
                            self.style.WARNING(f"Failed for {relative_path}: {error_message}")
                        )
                        report_entry["status"] = "failed"
                        report_entry["error"] = error_message
                else:
                    failed += 1
                    error_message = f"{type(exc).__name__}: {exc}"
                    self.stderr.write(
                        self.style.WARNING(f"Failed for {relative_path}: {error_message}")
                    )
                    report_entry["status"] = "failed"
                    report_entry["error"] = error_message
            except URLError as exc:
                failed += 1
                error_message = f"{type(exc).__name__}: {exc}"
                self.stderr.write(self.style.WARNING(f"Failed for {relative_path}: {error_message}"))
                report_entry["status"] = "failed"
                report_entry["error"] = error_message
            except OSError as exc:
                failed += 1
                error_message = f"{type(exc).__name__}: {exc}"
                self.stderr.write(self.style.WARNING(f"Failed for {relative_path}: {error_message}"))
                report_entry["status"] = "failed"
                report_entry["error"] = error_message

            report.append(report_entry)

        report_path.write_text(json.dumps(report, indent=2))

        self.stdout.write(
            self.style.SUCCESS(
                "Completed: "
                f"downloaded {downloaded} file(s), "
                f"skipped {skipped} existing file(s), "
                f"failed {failed} file(s)."
            )
        )
        self.stdout.write(self.style.SUCCESS(f"Report written to {report_path}"))
