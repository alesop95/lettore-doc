# CLAUDE.md — Istruzioni per Claude Code nel progetto lettore-doc

Questo file viene letto automaticamente da Claude Code all'avvio di ogni sessione
aperta nella root di `lettore-doc`. Contiene il contesto minimo necessario perche'
una sessione possa operare correttamente senza dover ri-spiegare l'architettura.

---

## Cos'e' questo progetto

`lettore-doc` e' il motore privato di analisi documentale del sistema di tassonomia
delle competenze IT. Riceve in input una o piu' cartelle di documentazione aziendale
(`.docx`, `.txt`, `.md`, `.png`), produce due output indipendenti:

1. Un **vault Obsidian privato** in `vault-output/` con il grafo dei documenti,
   sintesi narrative e wiki-link automatici (per uso personale interno).

2. **Evidenze sanitizzate** iniettate nel repository pubblico
   `${LETTERDOC_SKILLS_REPO}` tramite la pipeline di estrazione skill
   (pubblicate su GitHub Pages all'URL `alesop95.github.io/skills/`).

Il repository `lettore-doc` non va mai pubblicato. Il `.gitignore` esclude
`_intermediate/`, `vault-output/`, `.venv/` e `.env`.

---

## Documenti di riferimento del progetto

Sono presenti nella root del repository quattro documenti che descrivono il sistema
da angolazioni diverse e che vanno considerati come fonte di verita' per Claude
Code in qualsiasi sessione:

- `README.md` — guida operativa rapida con i comandi quotidiani
- `GUIDA-TECNICA.md` — architettura dettagliata, formule, algoritmi
- `case-study-operativi.md` — otto scenari pratici con comandi precisi
- `diario-tecnico-progetto (lettore-doc + skills-repo).docx` — storia completa
  del progetto, decisioni architetturali, fasi di sviluppo, manutenzione
- `diario-tecnico-progetto (lettore-doc + skills-repo).md` — versione Markdown
  del diario, generata automaticamente per consentire `git diff` testuali

---

## Sistema di contesto (standard adottato)

Il progetto adotta il sistema portabile descritto in `.claude/PROJECT-SYSTEM.md`. A inizio sessione
si segue la procedura di ripresa: si legge per primo `.claude/memory/index.md` (branch, commit di
riferimento, stato delle schede, prossima azione), poi `.claude/context/current-work.md` se c'e una
feature attiva, e si invoca la skill `sync-context` per il drift schede-codice. Le schede in
`.claude/context/` (`STACK.md`, `design-and-security.md`, `deployment.md`, `dev-testing.md`,
`roadmap.md`) riassumono e riconciliano `GUIDA-TECNICA.md`, che resta il dettaglio. Il work-log e in
`.claude/memory/progress.md`, le decisioni in `.claude/memory/decisions.md`. La skill `onboard` da la
spiegazione completa a chi parte da zero. Claude non scrive da solo in `memory/` e `context/`: si
aggiornano su richiesta esplicita.

### Strumenti attivati e uso in questo progetto

- `code-context` (MCP tree-sitter, vedi `.mcp.json`): per mappare con precisione gli script Python
  di `scripts/` quando si lavora sul codice o si riconciliano le schede.
- `caveman` (riduzione dei token di output, plugin esterno `juliusbrussee/caveman`): NON e' incluso
  nel repo, perche e' un plugin che si auto-attiva. Si installa su richiesta col suo installer
  (`install.ps1` / `INSTALL.md` del repo) e si abilita SOLO per la singola sessione operativa sul
  codice, poi si disabilita. Va tenuto disattivato quando si aggiorna il diario o si genera prosa
  per la tassonomia pubblica, perche ne degraderebbe lo stile.
- `knowledge-wiki` NON adottata: il progetto ha gia una knowledge base nativa (vault Obsidian piu
  graphify e la skill `grafo-conoscenza`).

## REGOLA OPERATIVA - Sincronia diario .docx e .md

Il diario tecnico esiste in due formati paralleli, **entrambi versionati nel
repository** e **sempre sincronizzati**. Il `.docx` e' il file di lavoro umano
modificabile in Microsoft Word. Il `.md` e' la sua copia testuale leggibile da
Git per `git diff`, `git blame`, e per la consultazione rapida in editor di testo.

La regola e': **il .docx e' la sorgente di verita'. Il .md viene rigenerato
dal .docx tramite uno script di conversione automatica, non viene mai
modificato a mano.**

### Quando il diario va aggiornato

Ogni volta che si verifica un cambiamento significativo del sistema:

- Nuovo script aggiunto alla pipeline
- Modifica architetturale a uno script esistente
- Soglia o peso di tuning modificato in modo permanente
- Nuovo caso operativo emerso nell'uso quotidiano
- Bug rilevante identificato e risolto
- Nuova dipendenza esterna integrata (es. nuovo server MCP)

### Procedura di aggiornamento (passi obbligatori in ordine)

1. **Modificare il `.docx`** in Microsoft Word, salvare con lo stesso nome.

2. **Rigenerare il `.md`** dalla root del repository:

   ```
   .\.venv\Scripts\python.exe scripts\sync_diary_md.py
   ```

   Lo script legge il `.docx` aggiornato, estrae paragrafi, blocchi di
   codice, tabelle e note a pie' di pagina, e sovrascrive il `.md` con
   il contenuto convertito. Estrae anche le immagini in `diario-assets/`.

3. **Verificare il diff testuale** prima di committare:

   ```
   git diff "diario-tecnico-progetto (lettore-doc + skills-repo).md"
   ```

   Questo mostra esattamente cosa e' cambiato nel diario in formato leggibile,
   cosa che il `.docx` da solo (essendo binario) non permette di vedere.

4. **Committare entrambi i file insieme** nello stesso commit:

   ```
   git add "diario-tecnico-progetto (lettore-doc + skills-repo).docx"
   git add "diario-tecnico-progetto (lettore-doc + skills-repo).md"
   git add diario-assets/
   git commit -m "Diario: <descrizione modifica>"
   git push
   ```

   Il prefisso `Diario:` nel commit message rende immediatamente identificabili
   nello storico le modifiche al diario.

### Cosa NON fare mai

- **Mai modificare il `.md` a mano**: viene sovrascritto al successivo run
  dello script di sincronia, e ogni modifica manuale viene persa.
- **Mai committare solo uno dei due file**: i due file disallineati
  perdono il loro valore di coppia.
- **Mai cambiare il nome del file** senza aggiornare anche `sync_diary_md.py`
  e questo `CLAUDE.md` con il nuovo nome.

### Verifica di allineamento

Per controllare in qualsiasi momento se il `.md` e' allineato al `.docx`
(ad esempio dopo un `git pull` su un'altra macchina), basta rigenerare:

```
.\.venv\Scripts\python.exe scripts\sync_diary_md.py
git status
```

Se `git status` mostra il `.md` come modificato, il file su disco era
disallineato rispetto al `.docx` e la rigenerazione lo ha ripristinato.
Se non c'e' modifica, i due file erano gia' sincronizzati.

---

## REGOLA OPERATIVA - State tracking ingest

Il file `_intermediate\ingest_state.json` e' la **sorgente di verita' del
progresso ingest** sulla macchina locale. Per ciascuna subfolder sorgente
che e' stata ingerita almeno una volta tiene uno snapshot sha256+mtime per
ogni file di testo (`.docx`, `.txt`, `.md`), insieme alla data dell'ultimo
ingest e al commit del `skills-repo` associato.

Lo gestisce esclusivamente lo script `scripts\ingest_state.py`. Il file vive
in `_intermediate\` che e' in `.gitignore`: lo stato e' locale e per macchina
(la storia "ufficiale" e condivisa e' Git su `skills-repo` + il diario).

### Comandi (sempre tramite il virtualenv del progetto)

```
# Digest di stato (alla ripresa di una sessione)
.\scripts\session_resume.ps1

# Focus su una subfolder con elenco esplicito dei file cambiati
.\scripts\session_resume.ps1 -Folder "<path>"

# Aggiornare lo snapshot di una subfolder (post-ingest)
.\.venv\Scripts\python.exe scripts\ingest_state.py track `
    --folder "<path>" --source ONEDRIVE --commit <sha>

# Rimuovere una subfolder dal tracking
.\.venv\Scripts\python.exe scripts\ingest_state.py untrack --folder "<path>"
```

### Regole

- Il file va aggiornato **una sola volta per ciclo**, esclusivamente con
  `track`, e **solo dopo aver eseguito `export_to_taxonomy.py --apply` con
  successo e committato sul `skills-repo`**.
- Mai modificare il file a mano: il formato e' interno allo script.
- Mai committare il file: vive in `_intermediate\` (gitignored). Se viene
  spostato fuori da quella directory si rompe il contratto di riservatezza.
- Le subfolder che non sono mai state ingerite non compaiono nel digest
  finche' non vengono registrate la prima volta con `track`.

### Modello di default per le sessioni

Il progetto imposta `claude-opus-4-7` come modello di default tramite
`E:\lettore-doc\.claude\settings.json`. Le sessioni Claude Code aperte nella
root del progetto lo ereditano. Le sessioni `/graphify`, che girano dentro la
**cartella sorgente** (non nella root del progetto), non lo ereditano: per
quelle usare sempre il launcher `scripts\start_graphify.ps1` che forza
`--model claude-opus-4-7`. La pipeline a valle e' interamente Python
deterministico, quindi il modello non influisce su nessuno step diverso da
`/graphify`.

---

## Variabili di ambiente attese

Tutte le path sensibili sono risolte tramite variabili di ambiente. Verificare
con queste righe in PowerShell:

```
$env:LETTERDOC_SKILLS_REPO       # path al repo pubblico alesop95/skills
$env:LETTERDOC_SOURCE_ONEDRIVE   # path alla cartella sorgente OneDrive
$env:LETTERDOC_SOURCE_PORTFOLIO  # path alla cartella sorgente Portfolio
```

Se una variabile risulta vuota, il valore non e' stato propagato nella sessione
corrente: rilanciare PowerShell oppure forzare il refresh con:

```
$env:NOME = [System.Environment]::GetEnvironmentVariable("NOME", "User")
```

Per il setup iniziale su una nuova macchina vedere README.md sezione "Setup"
oppure Appendice A del diario.

---

## Comandi principali

Tutti i comandi assumono che il virtualenv sia attivo o che venga invocato
esplicitamente `.venv\Scripts\python.exe`.

### Pipeline vault privato

```
.\run_pipeline.ps1 -SourceFolder $env:LETTERDOC_SOURCE_ONEDRIVE
```

### Pipeline estrazione skill verso il repo pubblico

```
# 1. Indicizza la tassonomia attuale del repo pubblico
.\.venv\Scripts\python.exe scripts\generate_taxonomy_index.py `
    --output _intermediate\taxonomy_index.json

# 2. Arricchisce il graph.json prodotto da graphify
.\.venv\Scripts\python.exe scripts\enrich_graph.py `
    --graph "$env:LETTERDOC_SOURCE_ONEDRIVE\graphify-out\graph.json" `
    --workdir $env:LETTERDOC_SOURCE_ONEDRIVE `
    --output _intermediate\enriched_graph.json

# 3. Classifica i nodi vs tassonomia
.\.venv\Scripts\python.exe scripts\map_to_taxonomy.py `
    --enriched-graph _intermediate\enriched_graph.json `
    --taxonomy _intermediate\taxonomy_index.json `
    --output-md _intermediate\taxonomy_diff.md `
    --output-json _intermediate\taxonomy_diff.json

# 4. REVISIONE MANUALE del taxonomy_diff.md (sempre obbligatoria)
notepad _intermediate\taxonomy_diff.md

# 5. Apply al repo pubblico (sempre prima --dry-run)
.\.venv\Scripts\python.exe scripts\export_to_taxonomy.py `
    --diff-json _intermediate\taxonomy_diff.json `
    --skills-repo $env:LETTERDOC_SKILLS_REPO --dry-run

.\.venv\Scripts\python.exe scripts\export_to_taxonomy.py `
    --diff-json _intermediate\taxonomy_diff.json `
    --skills-repo $env:LETTERDOC_SKILLS_REPO --apply
```

### Sincronia del diario .md (vedi sezione dedicata sopra)

```
.\.venv\Scripts\python.exe scripts\sync_diary_md.py
```

---

## Strumenti esterni usati dal sistema

### graphify

`graphify` e' una skill registrata in Claude Code che produce un grafo semantico
da una cartella documentale. Si invoca con `/graphify .` dentro una sessione
Claude Code aperta nella cartella sorgente.

Dove si usa: sulle cartelle sorgente (per la pipeline skill) e sul repository
pubblico `${LETTERDOC_SKILLS_REPO}\docs\` (utilizzo ortogonale per il
Knowledge Graph della tassonomia).

Dove NON si usa: sul vault Obsidian privato, che e' prodotto interamente dagli
script Python locali.

### Server MCP obsidian-vault (opzionale)

Si configura in Claude Desktop puntandolo a una cartella vault. Una volta
collegato, Claude Code ottiene tool di filesystem per leggere e scrivere file
direttamente nel vault. Utile per editing assistito delle pagine della
tassonomia. Non sostituisce `export_to_taxonomy.py` che rimane l'unica via
ufficiale per popolare la sezione `## Projects & evidence` con controllo di
idempotenza.

---

## Regole operative

- Mai committare `_intermediate/`, `vault-output/`, `.env`, `.venv/`.
- Mai hardcodare path assoluti negli script: sempre via variabili di ambiente.
- Mai eseguire `export_to_taxonomy.py --apply` senza prima averlo testato in
  `--dry-run` e aver letto il `taxonomy_diff.md` revisionato.
- Mai modificare a mano le sezioni `## Projects & evidence` del repo pubblico:
  sono gestite esclusivamente da `export_to_taxonomy.py` tramite il meccanismo
  di idempotenza basato su ID SHA-256 in commenti HTML.
- Le quattro sezioni H2 fisse delle pagine Capability (`## Overview`,
  `## Technologies & tools`, `## Responsibilities & operational scope`,
  `## Projects & evidence`) sono invariate per contratto: lo script di export
  presuppone esattamente questa struttura.
- Mai modificare a mano il diario `.md`: rigenerare sempre tramite
  `sync_diary_md.py` come descritto nella sezione dedicata sopra.
