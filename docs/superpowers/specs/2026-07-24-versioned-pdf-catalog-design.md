# Versioned PDF Catalog Design

## Goal

Store revised card PDFs without changing card records, while making version 1 the preferred export source and retaining version 0 as the complete fallback.

## Storage layout

PDFs are grouped first by language, then by PDF revision, and retain the existing relative card path:

```text
backend/data/
  en/
    v0/pdfs/<faction>/<keyword>/<filename>.pdf
    v1/pdfs/<faction>/<keyword>/<filename>.pdf
  es/
    v0/pdfs/<faction>/<keyword>/<filename>.pdf
    v1/pdfs/<faction>/<keyword>/<filename>.pdf
```

`v0` contains the baseline English PDF collection. `v1` is sparse: it contains only PDFs that have been revised. Spanish revisions follow the same independent structure when they are available.

## Catalog compatibility

Existing `pdf` fields in `backend/data/cards.json` remain versionless, for example:

```json
"pdf": "pdfs/Guild/Elite/M4E_Stat_Elite_Alan_Reid.pdf"
```

Card image data and its existing `files.versions` field are not changed; those versions are unrelated to PDF revisions.

## Resolution

For a requested language, the resolver checks the same versionless catalog path in this order:

1. `<language>/v1/<catalog path>`
2. `<language>/v0/<catalog path>`

The first existing file is exported. A missing PDF in both version directories remains an export error. The implementation does not fall back from Spanish to English: language availability and exports must reflect only files available in the requested language.

## Language availability

The generated frontend availability data marks a language available for a card or variant when its PDF exists in either `v1` or `v0`, using the same preferred-version order as the backend. This preserves current language controls without adding PDF-version controls to the UI.

## Testing

Backend tests will prove that English and Spanish resolve to their language-specific `v1` file when present and to their language-specific `v0` file otherwise. Frontend generation tests, if present, will verify that availability recognizes a PDF in either revision directory.
