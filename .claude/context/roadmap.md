---
generated-from-commit: 979d674
generated-from-branch: main
generated-date: 2026-06-17
covers-paths:
  - scripts/**
last-verified-commit: 233c39c
source-doc: GUIDA-TECNICA.md
---

# Roadmap

Estensioni candidate (da `GUIDA-TECNICA.md` sezione 9), da valutare caso per caso solo se il valore giustifica la dipendenza:

- Automazione multi-sorgente completa: oggi il passaggio graphify resta semi-interattivo; serve un flag headless o una API key dedicata.
- Embeddings semantici al posto del recall su keyword in `map_to_taxonomy.py`: cambia solo la funzione di scoring, il resto della pipeline resta invariato.
- Connettori MCP per sorgenti remote (Google Drive, Notion, Confluence) che producono lo stesso formato `graph.json`.
- Clustering gerarchico nel vault al posto dell'approccio naive a singolo seed.
