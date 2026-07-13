---
generated-from-commit: 979d674
generated-from-branch: main
generated-date: 2026-06-17
covers-paths:
  - scripts/**
  - run_pipeline.ps1
  - run_pipeline.sh
  - setup.ps1
  - setup.sh
last-verified-commit: cb35334
source-doc: GUIDA-TECNICA.md
---

# Dev e testing

La pipeline e deterministica: rilanciare gli script da lo stesso output. Controlli chiave: `--dry-run` obbligatorio prima di `export_to_taxonomy.py --apply`; revisione manuale di `taxonomy_diff.md`; `mkdocs build --strict` come safety net sui link del sito pubblico. La modalita `--incremental` confronta hash SHA256 e processa solo i file cambiati. Il tuning avviene su soglie e pesi (`THRESHOLD_FIT`, `W_JACCARD`, ecc.) documentati in `GUIDA-TECNICA.md` sezione 8. Ambiente ricreabile con `setup.ps1/.sh`.
