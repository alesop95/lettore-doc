# lettore-doc

Sistema per estrarre skill da documentazione locale (`.docx`, `.txt`, `.md`) e pubblicarle su un sito web statico come tassonomia navigabile di competenze.

Se hai perso il filo, parti da `STATO-DEL-PROGETTO.md`: e' la fotografia d'insieme dei flussi, dello stato reale e di dove vive ogni tipo di verita'. Per l'architettura di dettaglio vedere `GUIDA-TECNICA.md`. Questo README contiene i comandi operativi.

---

## Struttura del progetto

```
E:\lettore-doc\
├── .claude\
│   ├── agents\lettore-documentazione.md   subagente Claude Code
│   └── skills\
│       ├── grafo-conoscenza\SKILL.md
│       └── parsing-docx\SKILL.md
├── scripts\
│   ├── parse_docx.py                      parsing token-efficient dei .docx
│   ├── extract_entities.py                regex italiane per entità aziendali
│   ├── build_knowledge_graph.py           grafo di relazioni tra documenti
│   ├── generate_vault.py                  vault Obsidian privato
│   ├── prepare_graphify_source.py         pre-flight: filtro nomi di graphify
│   ├── enrich_graph.py                    anonymization_map + preview ancorato
│   ├── generate_taxonomy_index.py         indicizza la tassonomia da mkdocs.yml
│   ├── map_to_taxonomy.py                 classifica nodi → fit/new_cap/new_dom
│   ├── sanitize_taxonomy_diff.py          gate residui (obbligatorio)
│   ├── export_to_taxonomy.py              inietta, riscrive e rimuove evidenze
│   ├── ingest_state.py                    stato di avanzamento dell'ingest
│   ├── session_resume.ps1                 digest di apertura sessione
│   ├── start_graphify.ps1                 launcher sessione graphify
│   ├── sync_diary_md.py                   rigenera il .md del diario dal .docx
│   ├── append_diary_section.py            inserisce una sezione nuova nel .docx
│   ├── finalize_diary.ps1                 rigenera, mostra il diff, stampa i git
│   └── open_diary.ps1                     apre il diario in Word (caso manuale)
├── _intermediate\                         dati di lavoro (rigenerabili, gitignored)
├── vault-output\                          vault Obsidian privato (gitignored)
├── .venv\                                 ambiente Python (gitignored)
├── sources.yml                            configurazione sorgenti dati
├── requirements.txt
├── setup.ps1 / setup.sh
├── run_pipeline.ps1 / run_pipeline.sh     pipeline vault Obsidian privato
├── STATO-DEL-PROGETTO.md                  fotografia d'insieme
└── GUIDA-TECNICA.md
```

La cartella `.claude/` contiene anche `memory/` (stato e work-log), `context/` (schede tecniche per area) e `rules/` (regole vincolanti per l'agente). La mappa completa di cosa sta dove e' nella sezione 6 di `STATO-DEL-PROGETTO.md`.

---

## Prerequisiti

- **Python 3.10+** installato sul sistema
- **Claude Code** installato e autenticato con il proprio account
- **graphify** installato (vedi sotto)
- **Git** installato

---

## Installazione

### 1. Creare l'ambiente Python isolato

```powershell
# Windows
cd E:\lettore-doc
.\setup.ps1
```

```bash
# macOS / Linux
cd ~/lettore-doc
./setup.sh
```

Lo script crea `.venv/` localmente, aggiorna pip, e installa le dipendenze da `requirements.txt` (`python-docx`, `pyyaml`). Dura circa 15 secondi. Non modifica nulla al di fuori della cartella del progetto.

Per ricreare l'ambiente da zero:

```powershell
.\setup.ps1 -Force     # Windows
./setup.sh --force     # macOS / Linux
```

### 2. Installare graphify

```powershell
pipx install "graphifyy[office]"
graphify install --platform windows
```

Verificare con `graphify --version`. Atteso: `graphify 0.8.x`.

### 3. Configurare sources.yml

Editare `sources.yml` aggiungendo le cartelle sorgente:

```yaml
sources:
  - path: "C:/percorso/alla/prima/cartella"
    label: nome_sorgente_1
    include_extensions: [.docx, .txt, .md]
    exclude_patterns: ["~$*", "_archive/*"]

  - path: "D:/percorso/alla/seconda/cartella"
    label: nome_sorgente_2
    include_extensions: [.docx, .txt, .md]
    exclude_patterns: ["~$*"]
```

---

## Riprendere il lavoro (state tracking ingest)

Ad ogni nuova sessione di lavoro su `lettore-doc`, la prima azione utile e' guardare lo stato corrente dell'ingest e capire se ci sono file modificati sul disco rispetto all'ultimo ciclo. Lo state tracker (`scripts\ingest_state.py`) mantiene uno snapshot sha256+mtime per file di ogni subfolder sorgente gia' ingerita, in `_intermediate\ingest_state.json` (locale, non versionato).

### Digest di apertura sessione

```powershell
.\scripts\session_resume.ps1
```

Per ogni subfolder tracciata stampa: ultima data di ingest, commit associato sul `skills-repo`, e i conteggi `unchanged / modified / new / deleted`.

Focus su una singola subfolder (mostra l'elenco esplicito dei file cambiati):

```powershell
.\scripts\session_resume.ps1 -Folder "$env:LETTERDOC_SOURCE_ONEDRIVE\Helpdesk_PC formatting"
```

### Registrare/aggiornare uno snapshot (post-ingest)

Da eseguire una volta, al termine di un ciclo di ingest, dopo `--apply` su `skills-repo`:

```powershell
.\.venv\Scripts\python.exe scripts\ingest_state.py track `
    --folder "$env:LETTERDOC_SOURCE_ONEDRIVE\Helpdesk_PC formatting" `
    --source ONEDRIVE `
    --commit (git -C $env:LETTERDOC_SKILLS_REPO rev-parse HEAD)
```

Da quel momento, ogni sessione successiva mostrera' i delta rispetto a quello snapshot. Le subfolder che non sono mai state ingerite non compaiono nel digest finche' non vengono registrate la prima volta.

### Avviare graphify con il modello corretto

Le sessioni `/graphify` girano dentro la cartella sorgente, non nella root del progetto, quindi non ereditano il default modello di `lettore-doc`. Usare il launcher dedicato:

```powershell
.\scripts\start_graphify.ps1 -SourceFolder "$env:LETTERDOC_SOURCE_ONEDRIVE\<subfolder>"
```

Apre Claude Code dentro la subfolder con `--model claude-opus-4-7`; dentro la sessione lanciare poi `/graphify .`.

Sulle macchine con piu' account Claude Code configurati (directory `%USERPROFILE%\.claude-<name>`) si sceglie l'account con `-Account`:

```powershell
.\scripts\start_graphify.ps1 -SourceFolder "..." -Account account2
```

Lo script setta `CLAUDE_CONFIG_DIR` solo per il processo figlio: la selezione vale unicamente per quella sessione graphify e non modifica lo stato dell'utente. Se `-Account` e' omesso, la sessione eredita il default del terminale corrente.

---

## Uso - Pipeline di estrazione skill (aggiornamento tassonomia)

Questa pipeline estrae skill dai documenti sorgente e aggiorna `skills-repo` (il sito pubblico su GitHub Pages).

### Passo 0 - Selezione e pre-flight (nessun token)

I documenti del ciclo si scelgono a mano e si copiano in `_intermediate\src\<nome-ciclo>\`. Si escludono i materiali contrattuali e commerciali, i dati di terzi, e si neutralizza qualsiasi nome di file che contenga un dato personale. La cartella con gli originali va aggiunta a **entrambi** `.gitignore` e `.graphifyignore`, perche' contiene documenti aziendali non anonimizzati.

Poi il pre-flight, che replica il filtro sui nomi di graphify. Il default e' sola verifica e non scrive nulla:

```powershell
.\.venv\Scripts\python.exe scripts\prepare_graphify_source.py `
  --folder "_intermediate\src\<nome-ciclo>"

.\.venv\Scripts\python.exe scripts\prepare_graphify_source.py `
  --folder "_intermediate\src\<nome-ciclo>" --apply
```

L'`--apply` produce `<nome-ciclo>-sanitized\` con i documenti convertiti in Markdown e i soli nomi neutralizzati. E' su questa cartella che gira graphify, non sull'originale. Il passo non e' opzionale: graphify scarta in silenzio i file il cui nome contiene termini che sembrano segreti, e una policy intitolata "Configurazione-password-Windows.docx" spariva dal corpus senza segnale.

### Passo 1 - graphify sulla cartella preparata (consuma token Claude Code)

```powershell
.\scripts\start_graphify.ps1 `
  -SourceFolder "_intermediate\src\<nome-ciclo>-sanitized" -Account account2
```

Dentro la sessione che si apre: `/graphify .`. Attendere il completamento e verificare `graphify-out\GRAPH_REPORT.md` per il riepilogo dei nodi estratti. Per aggiornamenti incrementali sui soli file modificati, `/graphify . --update`.

### Passo 2 - Genera taxonomy index

```powershell
cd E:\lettore-doc
.\.venv\Scripts\python.exe scripts\generate_taxonomy_index.py `
  --skills-repo "J:\...\skills-repo" `
  --output _intermediate\taxonomy_index.json
```

### Passo 3 - Arricchisci il grafo

```powershell
.\.venv\Scripts\python.exe scripts\enrich_graph.py `
  --graph   "<cartella-sorgente>\graphify-out\graph.json" `
  --workdir "<cartella-sorgente>" `
  --output  _intermediate\enriched_graph.json
```

### Passo 4 - Classifica i nodi

```powershell
.\.venv\Scripts\python.exe scripts\map_to_taxonomy.py `
  --enriched-graph _intermediate\enriched_graph.json `
  --taxonomy       _intermediate\taxonomy_index.json `
  --output-md      _intermediate\taxonomy_diff.md `
  --output-json    _intermediate\taxonomy_diff.json
```

### Passo 5 - Revisionare il diff (obbligatorio)

```powershell
notepad _intermediate\taxonomy_diff.md
```

Si parte dai fit marcati `DA VERIFICARE`, che sono quelli la cui destinazione non e' determinata dal punteggio: margine entro `REVIEW_MARGIN` sul secondo classificato, oppure decisione poggiata su un solo token. Per ognuno il diff riporta il secondo classificato col suo punteggio e i token che hanno deciso, e sui pareggi il secondo e' spesso la destinazione giusta. Si eliminano poi i falsi positivi dalla sezione "Fit", si accettano o rinominano le "New Capabilities", si scartano le "New Domains" non rilevanti.

### Passo 6 - Gate dei residui (obbligatorio)

```powershell
.\.venv\Scripts\python.exe scripts\sanitize_taxonomy_diff.py `
  --input  _intermediate\taxonomy_diff.json `
  --output _intermediate\taxonomy_diff.sanitized.json
```

E' il file **sanitizzato** che va in export, non il diff grezzo. Leggere il report: dice quante entries ha scartato e per quale regola, e quante mascherature ha applicato. Zero mascherature su un corpus aziendale e' piu' sospetto di molte.

### Passo 7 - Applicare (dry-run poi apply)

```powershell
# Verifica senza modifiche
.\.venv\Scripts\python.exe scripts\export_to_taxonomy.py `
  --diff-json   _intermediate\taxonomy_diff.sanitized.json `
  --skills-repo $env:LETTERDOC_SKILLS_REPO --dry-run

# Applicazione
.\.venv\Scripts\python.exe scripts\export_to_taxonomy.py `
  --diff-json   _intermediate\taxonomy_diff.sanitized.json `
  --skills-repo $env:LETTERDOC_SKILLS_REPO --apply
```

Il dry-run elenca anche i collocamenti obsoleti, cioe' le evidenze pubblicate che questo diff non prevede piu' su quella pagina. Per rimuoverle servono `--prune-moved`, sicuro, oppure `--prune-unexpected`, invasivo; per riscrivere un blocco gia' pubblicato serve `--refresh`. Le tre modalita' sono spiegate nella sezione 4 di `STATO-DEL-PROGETTO.md`.

### Passo 8 - Controlli di riservatezza (con l'apply fatto e nulla committato)

Il riepilogo dell'export e il `git diff --numstat` **non** sono controlli di riservatezza. Nella finestra in cui `git checkout -- docs\` annulla tutto, si cercano esplicitamente nel `git diff` del repo pubblico i cognomi noti, il dominio aziendale, gli IP interni e gli hostname del parco macchine. Si verifica poi che ogni pagina toccata conservi le quattro H2 di contratto, si conta il numero di ID di evidenza prima e dopo, e si lancia `mkdocs build --strict`.

### Passo 9 - Commit, push e chiusura del ciclo

```powershell
cd $env:LETTERDOC_SKILLS_REPO
git add docs\
git commit -m "Update taxonomy - $(Get-Date -Format 'yyyy-MM-dd')"
git push
```

GitHub Actions fa la build MkDocs e pubblica su Pages. Il sito è aggiornato in ~1 minuto a https://alesop95.github.io/skills/.

Subito dopo, una volta sola per ciclo, si registra lo snapshot con `ingest_state.py track` passando il commit appena creato (vedi la sezione sullo state tracking sopra). Poi si scrive la sezione del diario.

---

## Uso - Vault Obsidian privato

Genera un vault Obsidian navigabile con grafo di relazioni dai documenti sorgente. Output in `vault-output/` (non pubblicato online).

```powershell
# Run completo
.\run_pipeline.ps1 -SourceFolder "<percorso-sorgente>"

# Solo vault (dopo aggiornamento sintesi narrative)
.\run_pipeline.ps1 -SourceFolder "<percorso-sorgente>" -OnlyVault

# Incrementale (salta i file con hash invariato)
.\run_pipeline.ps1 -SourceFolder "<percorso-sorgente>" -Incremental
```

Per le sintesi narrative, avviare Claude Code dalla cartella del progetto e usare il subagente:

```
Usa il subagente lettore-documentazione per generare le sintesi narrative
di tutti i documenti in _intermediate/structure.json.
Salva ogni sintesi in _intermediate/summaries/ con il safe-stem corrispondente.
```

---

## Uso - Knowledge Graph del portfolio

Genera una visualizzazione interattiva della tassonomia come grafo navigabile da aggiungere al sito pubblico (opzionale, consuma token).

```powershell
cd "J:\...\skills-repo"
claude
/graphify docs/
```

Prima esecuzione - sposta l'output dentro `docs/`:

```powershell
Move-Item graphify-out docs\graphify-out
```

Aggiornare `.gitignore` con i file intermedi:

```
docs/graphify-out/.graphify_*
docs/graphify-out/converted/
docs/graphify-out/*.json
docs/graphify-out/cost.json
docs/graphify-out/manifest.json
```

Commit e push di `docs/graphify-out/graph.html`. Il file sarà accessibile a `alesop95.github.io/skills/graphify-out/graph.html` e linkato dall'`index.md`.

---

## Problemi noti

**OneDrive "solo cloud"**: i file in modalità solo-cloud non sono accessibili a python-docx. Clic destro sulla cartella sorgente in Esplora File → "Mantieni sempre su questo dispositivo".

**File .doc legacy**: solo `.docx` è supportato. Aprire in Word e salvare come `.docx`.

**Documenti scansionati senza OCR**: il parser segnala `text_length: 0`. Eseguire OCR prima della pipeline.

**PowerShell rifiuta gli script**: se `.\setup.ps1` dà errore di execution policy, da PowerShell come admin:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

**macOS - permessi script .sh**:

```bash
chmod +x setup.sh run_pipeline.sh
```

**Git repo su filesystem non-NTFS** (es. Google Drive, exFAT): aggiungere il percorso alle directory sicure:

```powershell
git config --global --add safe.directory '<percorso-repo>'
```

---

## Sicurezza

Gli script Python della pipeline vault Obsidian sono completamente offline. Il contenuto integrale dei `.docx` non viene mai trasmesso a servizi esterni.

graphify trasmette il contenuto dei documenti al modello Claude durante la sessione Claude Code. I documenti vengono processati nell'account Claude dell'utente autenticato. La policy di Anthropic per i piani Team e superiori esclude l'uso dei dati per il training del modello.

La difesa della riservatezza e' a quattro strati, perche' ognuno ha fallito almeno una volta da solo. La separazione fisica fra i due repository, con un solo script autorizzato a scrivere in quello pubblico. La `anonymization_map` costruita da `enrich_graph.py`, che `export_to_taxonomy.py` applica a ogni testo in uscita, compreso il nome del file citato come fonte: ragioni sociali, nomi di persona, email, IP e hostname diventano `[AZIENDA_N]`, `[PERSONA_N]`, `[EMAIL_N]`, `[IP_N]`, `[HOSTNAME_N]`. Il gate `sanitize_taxonomy_diff.py`, che ispeziona il testo dopo l'anonimizzazione e scarta o scruba i residui che la mappa ha mancato. E la ricerca manuale delle stringhe sensibili nel diff reale prima del commit, che e' lo strato che ha trovato la sola fuga vera della storia del progetto mentre gli altri tre erano verdi. Il dettaglio e' nella sezione 5 di `STATO-DEL-PROGETTO.md`.

Una precisazione sulla policy: la ragione sociale nuda non e' trattata come segreto, perche' la pagina di presentazione della tassonomia dichiara volutamente ruolo e datore di lavoro. Sono trattati come segreti l'infrastruttura e le persone.

---

Per dettagli architetturali su ogni script, le soglie di classificazione, il formato dei file intermedi, e le estensioni future, vedere `GUIDA-TECNICA.md`.
