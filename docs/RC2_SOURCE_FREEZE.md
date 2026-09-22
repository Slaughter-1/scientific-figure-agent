# RC2 Source Freeze

- Source commit: `1df5dad9dff6ea8d0d6466cb1e7cb91e0585f2e5` on `main`
- Export package: `outputs/rc2-closeout-task-v2/data/tasks/eaf4f19a-6b6e-42ca-9ed5-0adc1fb793d4/exports/candidate_02-r70af249aeb-fbbc001e.zip`
- Package SHA-256: `b4104f4c47d44c24e3a81e6ba479de5581d258cb28d9a3e6512419c1af1b96e5`
- Package size: `82815` bytes
- Python: `3.13.7`
- Validation: `python -m pytest -q` reported 205 passed / 22 warnings; `npm run build` reported Vite success; fresh API export and ZIP verification returned `verified`; MuPDF, Type3, SVG/PDF parity and Poppler smoke passed.

The freeze identifies the code and evidence snapshot used for this closeout. It does not close independent human holdout, real remote Figma write, or external asset license audit.
