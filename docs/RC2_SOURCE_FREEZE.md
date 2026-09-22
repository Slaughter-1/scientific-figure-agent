# RC2 Source Freeze

- Implementation source commit: `14e332e5ae9d620dd5163c8ad3e45a6dfc99d746` on `main`.
- Fresh API smoke task: `8dc69e9b-8aa3-4d2b-b60b-7ec7fb08bdfc`.
- Selected export: `outputs/rc2-closeout-task-v3/data/tasks/8dc69e9b-8aa3-4d2b-b60b-7ec7fb08bdfc/exports/candidate_02-r10cf6cd8b5-aca83fd9.zip`.
- Selected export SHA-256: `b1ef5ff72e5722e7109c025fa71d850fd025537428d0349dbb13ea75d048b1ae`.
- The source-inclusive evidence bundle and its SHA-256 are recorded in `outputs/rc2-closeout-task-v3/freeze-manifest.json`.
- Python: `3.13.7`.
- Validation: `python -m pytest -q` reported 205 passed / 22 warnings; `npm run build` reported Vite success; `python -m compileall -q src tests` passed; fresh API export and ZIP verification returned `verified`; MuPDF text extraction, Type 3 glyph, SVG/PDF page-size parity and Poppler smoke passed for all three candidates.
- The evidence snapshot includes the relevant source files, regression tests, full pytest/build/compile/PDF logs, route records and this freeze documentation.

This freeze identifies the implementation and evidence snapshot used for the current closeout. It does not close independent human holdout, real remote Figma write, or external asset license audit.
