---
generated-from-commit: 979d674
generated-from-branch: main
generated-date: 2026-06-17
covers-paths:
  - scripts/export_to_taxonomy.py
  - scripts/generate_taxonomy_index.py
last-verified-commit: ab89133
source-doc: GUIDA-TECNICA.md
---

# Deployment

Il vault Obsidian privato e locale, senza deploy. Il sito pubblico della tassonomia e un MkDocs servito su GitHub Pages: `git push` su `main` del repo pubblico avvia `mkdocs build --strict` (fallisce sui link rotti, safety net voluto) e il deploy delle Pages. L'iniezione delle evidenze nelle pagine Capability avviene via `export_to_taxonomy.py`, sempre `--dry-run` prima di `--apply`, con idempotenza tramite ID SHA256 in commenti HTML; le quattro H2 fisse delle pagine sono invariate per contratto.

Dettaglio in `GUIDA-TECNICA.md` sezioni 5-6.
