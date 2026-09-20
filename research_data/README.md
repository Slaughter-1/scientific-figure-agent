# Research data

This directory contains curated, provenance-tracked inputs for the figure-agent evaluation.

- `cases/kate_method.md` and `cases/atoms_method.md` are short, source-bound method excerpts from local paper analyses.
- `cases/kate_results.csv` contains values transcribed from the local KATE paper analysis with page/table provenance.
- `cases/kate_bfcl_summary.csv` and `cases/atoms_counterfact_summary.csv` are aggregate summaries computed from public GitHub datasets. Raw repositories remain local under `github/` and are git-ignored.
- `sources.json` records local source paths, public URLs, and license review status.

Raw benchmark records were not copied into tracked fixtures because public benchmark examples can contain credential-like fields.
