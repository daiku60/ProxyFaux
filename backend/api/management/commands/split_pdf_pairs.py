from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from pypdf import PdfReader, PdfWriter


class Command(BaseCommand):
    help = (
        "Split a PDF into two-page PDFs after skipping the first page. "
        "Requires the source PDF to have an odd number of pages."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("input_pdf", help="Path to the source PDF.")
        parser.add_argument(
            "output_dir",
            help="Directory where the split PDFs will be written.",
        )
        parser.add_argument(
            "--prefix",
            default="split",
            help="Filename prefix for generated PDFs. Defaults to 'split'.",
        )

    def handle(self, *args, **options) -> None:
        input_pdf = Path(options["input_pdf"]).expanduser().resolve()
        output_dir = Path(options["output_dir"]).expanduser().resolve()
        prefix = options["prefix"].strip()

        if not input_pdf.exists():
            raise CommandError(f"Input PDF does not exist: {input_pdf}")
        if input_pdf.suffix.lower() != ".pdf":
            raise CommandError(f"Input file must be a PDF: {input_pdf}")
        if not prefix:
            raise CommandError("The --prefix value cannot be blank.")

        reader = PdfReader(str(input_pdf))
        total_pages = len(reader.pages)

        if total_pages % 2 == 0:
            raise CommandError(
                f"Expected an odd number of pages, found {total_pages} in {input_pdf}."
            )

        output_dir.mkdir(parents=True, exist_ok=True)

        created_files = 0
        for output_index, start_page in enumerate(range(1, total_pages, 2), start=1):
            writer = PdfWriter()
            writer.add_page(reader.pages[start_page])
            writer.add_page(reader.pages[start_page + 1])

            output_path = output_dir / f"{prefix}_{output_index:03d}.pdf"
            with output_path.open("wb") as output_file:
                writer.write(output_file)

            created_files += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created_files} PDF file(s) in {output_dir} from {input_pdf}."
            )
        )
