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
last-verified-commit: 904f831
source-doc: GUIDA-TECNICA.md
---

# STACK

Motore privato di analisi documentale in Python. Legge documenti aziendali (`.docx`, `.txt`, `.md`, `.png`) dalle cartelle configurate in `sources.yml` e produce due output indipendenti: un vault Obsidian privato e, tramite una pipeline separata, evidenze sanitizzate per un sito pubblico di tassonomia delle competenze.

## Deterministico prima del linguistico

Il lavoro deterministico (parsing, estrazione entita, calcolo del grafo, generazione Markdown, classificazione) sta in script Python: offline, riproducibile, a costo zero di token LLM, con stati intermedi JSON ispezionabili sotto `_intermediate/`. L'estrazione entita combina regex (email, telefoni, URL, codici fiscali, ragioni sociali) e NER spaCy locale (`it_core_news_lg`, label `PER` per i nomi di persona, con fallback regex+stoplist quando il modello non e installato): un modello statistico locale, non un LLM remoto. Il lavoro linguistico (estrazione semantica via graphify, sintesi narrative) usa il modello e consuma token.

## Disclosure progressiva a tre livelli

I documenti non si leggono mai interi: `parse_docx.py` espone Livello 1 (scheletro), Livello 2 (preview di sezione piu entita), Livello 3 (sezione completa on-demand).

## Componenti

Gli script in `scripts/` coprono parsing token-efficient, estrazione entita, grafo pesato, generazione del vault e la pipeline di estrazione skill (`enrich_graph`, `generate_taxonomy_index`, `map_to_taxonomy`, `sanitize_taxonomy_diff`, `export_to_taxonomy`). Ambiente Python isolato in `.venv/`; gli orchestratori `run_pipeline.ps1/.sh` invocano il Python del venv per path completo. Il launcher `scripts/start_graphify.ps1` apre una sessione Claude Code dentro una subfolder sorgente, con parametro `-Account` per selezionare l'account Claude su macchine multi-account. Skill di progetto `grafo-conoscenza` e `parsing-docx`, agent `lettore-documentazione`, e `graphify` (esterno) per il grafo semantico.

## Anonimizzazione multi-strato

`extract_entities.py` estrae dieci categorie (ACRONYM, COMPANY, PROPER_NOUN, PROJECT_CODE, LAW_REF, DATE, AMOUNT, EMAIL, URL, DOC_REF) piu due dedicate all'infrastruttura (IP_ADDR dotted-quad con CIDR opzionale, HOSTNAME con prefissi WIN/SRV/PC-/NAS/USG/VM e forma dashed uppercase). `enrich_graph.py` costruisce una `anonymization_map` con placeholder `[AZIENDA_N]`, `[PERSONA_N]`, `[EMAIL_N]`, `[IP_N]`, `[HOSTNAME_N]`; `map_to_taxonomy.py` la propaga nel `taxonomy_diff.json`, `sanitize_taxonomy_diff.py` la applica e scarta entries con residui non catturati dalla mappa (dominio aziendale nudo, nomi fornitori, sede fisica, IP abbreviato tra parentesi, hostname con spazi), `export_to_taxonomy.py` la applica ai label H3, ai name H1 delle new-capability, al community label e al preview del body, oltre a rigenerare lo slug/file path dal name anonimizzato per non esporre IP/hostname nel nome del file pubblicato.

Il dettaglio (formule, pesi, categorie, comandi) e in `GUIDA-TECNICA.md`.
