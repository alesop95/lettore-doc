---
generated-from-commit: 979d674
generated-from-branch: main
generated-date: 2026-06-17
covers-paths:
  - scripts/enrich_graph.py
  - scripts/export_to_taxonomy.py
  - .gitignore
last-verified-commit: 904f831
source-doc: GUIDA-TECNICA.md
---

# Design e sicurezza

## Confine di sicurezza fisico

Due repository con scopi opposti: `lettore-doc` (privato, locale, mai online: codice, dati di lavoro, vault) e il repo pubblico della tassonomia (solo output elaborato e anonimizzato). `export_to_taxonomy.py` e l'unico script che scrive nel repo pubblico e prima applica l'`anonymization_map` prodotta da `enrich_graph.py` con cinque tipi di placeholder: `[AZIENDA_N]` per ragioni sociali, `[PERSONA_N]` per nomi propri, `[EMAIL_N]` per indirizzi email, `[IP_N]` per IPv4 (dotted-quad con CIDR opzionale), `[HOSTNAME_N]` per hostname riconoscibili (prefissi WIN/SRV/PC-/NAS/USG/VM e forma dashed uppercase). La sostituzione riguarda ogni testo che finisce nel repo pubblico: label H3 dell'evidenza, name H1 di nuove Capability, community label e preview del body; lo slug/file path della nuova Capability viene rigenerato dal name gia' anonimizzato per non esporre IP o hostname nel nome del file.

## Gate finale con residue-pattern

Fra `map_to_taxonomy.py` e `export_to_taxonomy.py --apply` c'e' un passaggio obbligatorio in `sanitize_taxonomy_diff.py` che scarta le entries insufficienti o rischiose dopo anonimizzazione: entries con troppo pochi caratteri alfanumerici significativi (soglia default 10, escludendo i placeholder), entries in cui pattern IP/EMAIL/hostname sopravvivono alla mappa per case-mismatch, entries con residui specifici del contesto del progetto (dominio aziendale nudo, nome azienda senza suffix ragione sociale, nome fornitore ricorrente, sede fisica). Per le new-capability filtra anche i nodi interni con residue e droppa l'intera capability se non ne rimane nessuno. E' difesa in profondita: la mappa e' first-line, il gate e' second-line.

## Preservazione del line-ending

`export_to_taxonomy.py` legge in binario ogni file esistente per rilevare CRLF vs LF e riscrive con lo stesso terminatore, evitando che un run Windows converta in CRLF file nati LF (o viceversa) e sporcando il diff GitHub con "line-ending changes" su decine di file. Per le new-capability create da zero, il line-ending viene campionato da un file esistente nel docs-dir per restare coerente col repo.

## Separazione dei piani dati

`_intermediate/` (derivati rigenerabili, gitignored) contro `vault-output/` (vault navigabile e annotabile a mano, gitignored): si re-indicizza senza perdere annotazioni manuali.

## Segreti

`.env` e `.env.local` gitignored, mai committati (verificato sulla storia). Le path sensibili si risolvono via variabili d'ambiente, mai hardcoded negli script.

Dettaglio in `GUIDA-TECNICA.md` sezioni 1.1-1.3.
