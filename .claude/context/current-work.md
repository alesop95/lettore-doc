---
generated-from-commit: 979d674
generated-from-branch: main
generated-date: 2026-06-17
covers-paths:
  - scripts/**
last-verified-commit: 397c0a8
source-doc: GUIDA-TECNICA.md
---

# Lavoro corrente

Stato: sistema maturo (v2.2 post-correzione routing e pre-flight graphify). Chiuse in sessione 2026-07-27 le due scoperte lasciate aperte dal ciclo Cybersec: il filtro sui nomi file di graphify ha ora un passo di preparazione dedicato (`prepare_graphify_source.py`), e il misrouting delle evidenze GDPR e' risolto alla radice con il taglio equo delle keyword in `generate_taxonomy_index.py` piu' lo spostamento del perimetro data breach su `Cybersecurity & IT Governance` nelle pagine pubbliche (skills-repo `88f4b8f`). Verificato sul corpus del ciclo chiuso: la classificazione automatica passa da 1 a 20 evidenze corrette e non richiede piu' la correzione manuale di diciotto fit.

Stato precedente: sistema maturo (v2.1 post-anonimizzazione robusta). Chiuse in sessione 2026-07-14 le feature "parametro `-Account` in `start_graphify.ps1`" e "anonimizzazione multi-strato + gate residue"; primo ciclo end-to-end su subfolder infrastrutturale (`ARCHITETTURA SERVER-CLOUD-LINEE`) andato a segno (skills-repo commit `bbd361e`, 56 evidenze anonimizzate su 11 Capability). Modalita corrente: manutenzione. Quando si apre una nuova feature, qui vanno cosa fa, file da creare, file da modificare, checklist di completamento e stato; la fonte di verita su cosa e fatto resta `memory/index.md` e il work-log, non le spunte qui. Le estensioni candidate sono in `roadmap.md`.
