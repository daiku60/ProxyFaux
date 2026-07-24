# Versioned PDF Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve every card PDF from `v1` when available and otherwise use `v0`, without changing card catalog paths.

**Architecture:** Card data continues to use versionless `pdfs/...` paths. The backend maps such a path to the requested language's `v1/pdfs` and then `v0/pdfs` roots. The language-availability generator checks the identical roots.

**Tech Stack:** Django/Python, pytest, frontend Python build script, TypeScript/Vite.

## Global Constraints

- Preserve all existing versionless `pdf` fields in `backend/data/cards.json`.
- Prefer an exact language-specific `v1` PDF; otherwise use that language's `v0` PDF.
- Never substitute an English PDF for a requested Spanish PDF.
- Do not expose PDF revision controls in the UI.

---

### Task 1: Implement and test backend revision resolution

**Files:**
- Modify: `backend/api/pdfs.py:301-350`
- Modify: `backend/api/test_pdf_language_export.py:21-54`

**Interfaces:**
- Consumes: `resolve_pdf_path_and_variants(pdf_value: str, *, language: str = "en") -> tuple[Path, list[str]]`.
- Produces: the same interface, with a `v1`, then `v0`, lookup order.

- [ ] **Step 1: Write failing resolution tests**

Add a test that creates both `tmp_path / "data" / "en" / "v0" / "pdfs" / "Neverborn" / "Woe" / "Candy.pdf"` and its `v1` equivalent, calls `resolve_pdf_path_and_variants("pdfs/Neverborn/Woe/Candy.pdf", language="en")`, and asserts the `v1` path is returned. Add a second test with English `v0` and Spanish `v0` files that requests Spanish and asserts its Spanish `v0` path is returned.

- [ ] **Step 2: Verify the tests fail**

Run: `cd backend && pytest api/test_pdf_language_export.py -k 'version_one or version_zero' -v`

Expected: FAIL because the resolver only recognizes the unversioned layout.

- [ ] **Step 3: Implement the minimal lookup**

Define `PDF_VERSIONS = ("v1", "v0")`. Replace `get_pdf_root_for_language` with a function returning `tuple(pdf_data_root / language / version / "pdfs" for version in PDF_VERSIONS)`. In `resolve_pdf_path_and_variants`, normalize the versionless path against each root and return the first candidate that exists; return the `v0` candidate when neither exists so the existing missing-file error remains useful. Keep filename variant parsing unchanged.

- [ ] **Step 4: Verify backend behavior**

Run: `cd backend && pytest api/test_pdf_language_export.py api/tests.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/api/pdfs.py backend/api/test_pdf_language_export.py
git commit -m "feat: resolve versioned card PDFs"
```

### Task 2: Implement and test version-aware language availability

**Files:**
- Modify: `frontend/scripts/generate_language_availability.py:55-63`
- Create: `frontend/scripts/test_generate_language_availability.py`

**Interfaces:**
- Consumes: `collect_available_languages(pdf_path: str, backend_data_dir: Path) -> list[str]`.
- Produces: the same list, considering each language's `v1` and `v0` PDF roots.

- [ ] **Step 1: Write the failing availability test**

Create a pytest file that imports `collect_available_languages`, creates `en/v0/pdfs/Neverborn/Woe/Candy.pdf` and `es/v1/pdfs/Neverborn/Woe/Candy.pdf` below `tmp_path`, then asserts `collect_available_languages("pdfs/Neverborn/Woe/Candy.pdf", tmp_path) == ["en", "es"]`.

- [ ] **Step 2: Verify the test fails**

Run: `cd frontend/scripts && python -m pytest test_generate_language_availability.py -v`

Expected: FAIL because availability checks only `<language>/<catalog path>`.

- [ ] **Step 3: Implement the minimum check**

Add `PDF_VERSIONS = ("v1", "v0")` and update `collect_available_languages` to include a language when `any((backend_data_dir / language / version / pdf_path).exists() for version in PDF_VERSIONS)` is true. Preserve `or ["en"]`.

- [ ] **Step 4: Verify generator and frontend**

Run: `cd frontend/scripts && python -m pytest test_generate_language_availability.py -v && cd .. && npm run build`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/scripts/generate_language_availability.py frontend/scripts/test_generate_language_availability.py frontend/.generated/language-availability.json
git commit -m "feat: detect versioned PDF languages"
```

### Task 3: Migrate the PDF storage hierarchy

**Files:**
- Move: `backend/data/en/pdfs/` to `backend/data/en/v0/pdfs/`
- Move: `backend/data/es/pdfs/` to `backend/data/es/v0/pdfs/`
- Create: `backend/data/en/v1/pdfs/.gitkeep`
- Create: `backend/data/es/v1/pdfs/.gitkeep`
- Modify: `README.md:221-236`
- Modify: `backend/.env.prod.example`

**Interfaces:**
- Consumes: version-aware resolver and availability generator from Tasks 1-2.
- Produces: a language/version/PDF directory tree with sparse `v1` revisions.

- [ ] **Step 1: Move the baseline PDFs with history preservation**

Create `v0` directories and use `git mv` for the complete existing English and Spanish `pdfs` folders. Create the empty `v1/pdfs` roots with `.gitkeep` files.

- [ ] **Step 2: Add the supplied revised English PDFs**

Place each revised file only at its corresponding `backend/data/en/v1/pdfs/<existing-relative-path>` location. Do not duplicate unchanged cards in `v1`.

- [ ] **Step 3: Update deployment configuration documentation**

Set the documented data root to `/app/data`; explain that PDF selection is `v1` then `v0` within the requested language. Remove unversioned `PDF_ROOT=/app/data/pdfs` examples.

- [ ] **Step 4: Regenerate and verify**

Run: `python frontend/scripts/generate_language_availability.py && cd backend && pytest api/test_pdf_language_export.py api/tests.py -v && cd ../frontend && npm run build`

Expected: generated availability matches the relocated files, all backend tests pass, and the frontend build exits successfully.

- [ ] **Step 5: Commit the migration**

```bash
git add README.md backend/.env.prod.example backend/data frontend/.generated/language-availability.json
git commit -m "chore: store PDFs by language and revision"
```
