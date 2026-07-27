---
generated-from-commit: 979d674
generated-from-branch: main
generated-date: 2026-06-17
covers-paths:
  - scripts/enrich_graph.py
  - scripts/export_to_taxonomy.py
  - .gitignore
  - .graphifyignore
last-verified-commit: 397c0a8
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

`_intermediate/` (derivati rigenerabili, gitignored) contro `vault-output/` (vault navigabile e annotabile a mano, gitignored): si re-indicizza senza perdere annotazioni manuali. Il piano graphify ha un confine dedicato: `.graphifyignore` replica `.gitignore` come lista di esclusione ma tiene volutamente indicizzabile `_intermediate/src/`, che contiene i sorgenti gia' sanitizzati; le due liste vanno mantenute allineate (regola operativa in `CLAUDE.md`) perche' graphify non finisca a indicizzare `.venv/`, `vault-output/`, `.env` o cache di sviluppo. E' un confine di privacy secondario al gitignore ma coerente con lo stesso principio: cio che sta fuori dal repo pubblico non deve entrare nel grafo semantico.

Su questo confine agisce anche un filtro che non e' nostro. graphify scarta autonomamente i file il cui nome contiene termini che sembrano segreti, e lo fa guardando il nome e mai il contenuto. E' una protezione sensata sul caso d'uso generale, ma sul nostro corpus produce un falso positivo sistematico: le policy IT aziendali si chiamano per forza di cose "Configurazione-password-Windows" o "Risposte-audit-password-policy", e sono esattamente il materiale da indicizzare. E lo scarto non e' nemmeno osservabile in modo affidabile: nel ciclo Cybersec il campo diagnostico `skipped_sensitive` e' risultato vuoto, perche' si popola a valle di un pre-detect che aveva gia' concluso `total_files: 0`, quindi il documento e' sparito senza lasciare traccia. `prepare_graphify_source.py` risolve replicando il filtro a monte e producendo una cartella parallela con i soli nomi neutralizzati. La distinzione di merito e' che si neutralizza il nome, non il contenuto: la protezione contro la fuga di dati resta interamente affidata alla catena di anonimizzazione e al gate residue, e non viene ne' sostituita ne' indebolita da questo passo, che risolve un problema di indicizzabilita' e non di riservatezza. I file di vero materiale crittografico, riconosciuti per estensione, non si rinominano affatto: li' il filtro di graphify ha ragione e restano fuori dal corpus.

L'indicizzabilita' di `_intermediate/src/` non e' pero' incondizionata: vale per il materiale gia' sanitizzato, non per i documenti aziendali reali depositati li' in attesa di lavorazione. Da qui la prima esclusione *per-subfolder* introdotta in entrambe le liste, `_intermediate/src/Cybersec-governance-baseline/`, che contiene le policy IT originali del ciclo di ingest omonimo. Sul lato git la riga e' ridondante, perche' `_intermediate/` e' gia' escluso a monte, e ha valore di sola documentazione della decisione; sul lato graphify e' invece la riga che conta davvero, perche' senza di essa il grafo semantico assorbirebbe testo non anonimizzato. La regola generale che ne discende: quando una subfolder di `_intermediate/src/` non ha ancora passato l'anonimizzazione, la si esclude esplicitamente in entrambi i file, e la si rimuove dall'esclusione solo dopo il passaggio nel gate.

## Segreti

`.env` e `.env.local` gitignored, mai committati (verificato sulla storia). Le path sensibili si risolvono via variabili d'ambiente, mai hardcoded negli script.

Dettaglio in `GUIDA-TECNICA.md` sezioni 1.1-1.3.
