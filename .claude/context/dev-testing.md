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
last-verified-commit: bbf19bb
source-doc: GUIDA-TECNICA.md
---

# Dev e testing

La pipeline e deterministica: rilanciare gli script da lo stesso output. Controlli chiave: `--dry-run` obbligatorio prima di `export_to_taxonomy.py --apply`; revisione manuale di `taxonomy_diff.md`; `sanitize_taxonomy_diff.py` come gate obbligatorio fra `map_to_taxonomy` e `export_to_taxonomy` (produce il `.sanitized.json` che poi va in dry-run/apply); `mkdocs build --strict` come safety net sui link del sito pubblico. La modalita `--incremental` confronta hash SHA256 e processa solo i file cambiati. Il tuning avviene su soglie e pesi (`THRESHOLD_FIT`, `W_JACCARD`, ecc.) documentati in `GUIDA-TECNICA.md` sezione 8. Ambiente ricreabile con `setup.ps1/.sh`; per l'estrazione NER serve `it_core_news_lg` scaricato via `python -m spacy download it_core_news_lg` (senza il modello si attiva un fallback regex+stoplist sub-ottimale). Sanity check post-`--apply` sullo skills-repo: `git diff -w --numstat` deve mostrare solo aggiunte (con eventuali `-2` legittimi dovuti alla rimozione del placeholder "None yet" dalle sezioni "Projects & evidence" preesistenti).
