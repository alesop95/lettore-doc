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
last-verified-commit: 6f3c2b8
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

A monte di graphify c'e' un passo di preparazione, `scripts/prepare_graphify_source.py`. graphify scarta i file il cui nome contiene `password`, `credential`, `secret`, `token` o `private_key`, guardando solo il nome e mai il contenuto. In teoria lo scarto e' osservabile, perche' `detect` restituisce un campo `skipped_sensitive`; nel caso reale del ciclo Cybersec non lo era, perche' quella lista si popola in un loop a valle del pre-detect e il pre-detect aveva gia' abortito con `total_files: 0`, facendo concludere alla sessione `needs_graph: false` senza eseguire nulla. Una policy IT aziendale intitolata "Configurazione-password-Windows.docx" sparisce quindi dal corpus senza alcun segnale. Lo script replica quel filtro (`_SENSITIVE_DIRS` e `_SENSITIVE_PATTERNS` di graphify 0.8.14, duplicati e non importati perche' graphify vive in un virtualenv pipx separato), in sola verifica elenca cosa verrebbe scartato, e con `--apply` genera una cartella `<nome>-sanitized/` con i documenti convertiti in Markdown e i soli nomi neutralizzati secondo una mappa esplicita in italiano. Il corpo non viene toccato: l'anonimizzazione dei dati resta compito di `enrich_graph.py` e `sanitize_taxonomy_diff.py` a valle. I file di vero materiale crittografico, riconosciuti per estensione, non si rinominano e restano esclusi.

Accanto alla pipeline vive un gruppo di tooling per il diario tecnico, che non elabora documenti sorgente ma tiene allineata la coppia `.docx` piu `.md` versionata in root. `sync_diary_md.py` e' il convertitore deterministico che rigenera il `.md` dal `.docx` estraendo paragrafi, blocchi codice, tabelle, note a pie' di pagina e immagini in `diario-assets/`. `scripts/append_diary_section.py` scrive nella direzione opposta: legge un draft Markdown e ne inserisce le sezioni nel `.docx` prima di un paragrafo di ancoraggio, per default l'intestazione "Lezioni apprese", mappando `## C.N` su Heading 2 e `### x` su Heading 3, rendendo corsivo, grassetto e monospazio come run formattati, e convertendo i marcatori `[^n]` in note a pie' di pagina vere. Le note richiedono una scrittura diretta in `word/footnotes.xml`, che python-docx tratta come blob opaco e non modella: si alloca un id libero, si costruisce la nota con lo stesso impianto di quelle esistenti e si inserisce nel corpo un run con `w:footnoteReference`. `scripts/open_diary.ps1` apre il `.docx` in Word ed elenca i draft piu' recenti, e serve ora il solo caso manuale. `scripts/finalize_diary.ps1` chiude il ciclo: invoca il convertitore, si ferma se non c'e' alcuna modifica, altrimenti mostra il diff del `.md` come review testuale che il binario da solo non consente e stampa i comandi git nel doppio blocco PowerShell piu' bash imposto dalla regola `git-commands-format.md`. Nessuno di questi helper esegue git: commit e push restano manuali per policy.

## Anonimizzazione multi-strato

`extract_entities.py` estrae dieci categorie (ACRONYM, COMPANY, PROPER_NOUN, PROJECT_CODE, LAW_REF, DATE, AMOUNT, EMAIL, URL, DOC_REF) piu due dedicate all'infrastruttura (IP_ADDR dotted-quad con CIDR opzionale, HOSTNAME con prefissi WIN/SRV/PC-/NAS/USG/VM e forma dashed uppercase). `enrich_graph.py` costruisce una `anonymization_map` con placeholder `[AZIENDA_N]`, `[PERSONA_N]`, `[EMAIL_N]`, `[IP_N]`, `[HOSTNAME_N]`; `map_to_taxonomy.py` la propaga nel `taxonomy_diff.json`, `sanitize_taxonomy_diff.py` la applica e scarta entries con residui non catturati dalla mappa (dominio aziendale nudo, nomi fornitori, sede fisica, IP abbreviato tra parentesi, hostname con spazi), `export_to_taxonomy.py` la applica ai label H3, ai name H1 delle new-capability, al community label e al preview del body, oltre a rigenerare lo slug/file path dal name anonimizzato per non esporre IP/hostname nel nome del file pubblicato.

Il dettaglio (formule, pesi, categorie, comandi) e in `GUIDA-TECNICA.md`.
