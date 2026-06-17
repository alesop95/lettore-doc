---
generated-from-commit: 979d674
generated-from-branch: main
generated-date: 2026-06-17
covers-paths:
  - scripts/**
  - run_pipeline.ps1
  - run_pipeline.sh
  - sources.yml
  - requirements.txt
last-verified-commit: 979d674
source-doc: GUIDA-TECNICA.md
---

# STACK

Motore privato di analisi documentale in Python. Legge documenti aziendali (`.docx`, `.txt`, `.md`, `.png`) dalle cartelle configurate in `sources.yml` e produce due output indipendenti: un vault Obsidian privato e, tramite una pipeline separata, evidenze sanitizzate per un sito pubblico di tassonomia delle competenze.

## Deterministico prima del linguistico

Il lavoro deterministico (parsing, estrazione entita con regex, calcolo del grafo, generazione Markdown, classificazione) sta in script Python: offline, riproducibile, a costo zero di token, con stati intermedi JSON ispezionabili sotto `_intermediate/`. Il lavoro linguistico (estrazione semantica via graphify, sintesi narrative) usa il modello e consuma token.

## Disclosure progressiva a tre livelli

I documenti non si leggono mai interi: `parse_docx.py` espone Livello 1 (scheletro), Livello 2 (preview di sezione piu entita), Livello 3 (sezione completa on-demand).

## Componenti

Gli script in `scripts/` coprono parsing token-efficient, estrazione entita, grafo pesato, generazione del vault e la pipeline di estrazione skill (`enrich_graph`, `generate_taxonomy_index`, `map_to_taxonomy`, `export_to_taxonomy`). Ambiente Python isolato in `.venv/`; gli orchestratori `run_pipeline.ps1/.sh` invocano il Python del venv per path completo. Skill di progetto `grafo-conoscenza` e `parsing-docx`, agent `lettore-documentazione`, e `graphify` (esterno) per il grafo semantico.

Il dettaglio (formule, pesi, categorie, comandi) e in `GUIDA-TECNICA.md`.
