# lettore-doc

Sistema per estrarre skill da documentazione locale (`.docx`, `.txt`, `.md`) e pubblicarle
su un sito web statico come tassonomia navigabile di competenze.

Per l'architettura completa, vedere `GUIDA-TECNICA.md`. Questo README contiene
le istruzioni operative.

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
│   ├── enrich_graph.py                    post-processing italiano su graph.json
│   ├── generate_taxonomy_index.py         indicizza la tassonomia da mkdocs.yml
│   ├── map_to_taxonomy.py                 classifica nodi → fit/new_cap/new_dom
│   └── export_to_taxonomy.py             inietta evidenze in skills-repo
├── _intermediate\                         dati di lavoro (rigenerabili, gitignored)
├── vault-output\                          vault Obsidian privato (gitignored)
├── .venv\                                 ambiente Python (gitignored)
├── sources.yml                            configurazione sorgenti dati
├── requirements.txt
├── setup.ps1 / setup.sh
├── run_pipeline.ps1 / run_pipeline.sh     pipeline vault Obsidian privato
└── GUIDA-TECNICA.md
```

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

Lo script crea `.venv/` localmente, aggiorna pip, e installa le dipendenze da
`requirements.txt` (`python-docx`, `pyyaml`). Dura circa 15 secondi. Non
modifica nulla al di fuori della cartella del progetto.

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

Ad ogni nuova sessione di lavoro su `lettore-doc`, la prima azione utile e'
guardare lo stato corrente dell'ingest e capire se ci sono file modificati sul
disco rispetto all'ultimo ciclo. Lo state tracker (`scripts\ingest_state.py`)
mantiene uno snapshot sha256+mtime per file di ogni subfolder sorgente gia'
ingerita, in `_intermediate\ingest_state.json` (locale, non versionato).

### Digest di apertura sessione

```powershell
.\scripts\session_resume.ps1
```

Per ogni subfolder tracciata stampa: ultima data di ingest, commit associato
sul `skills-repo`, e i conteggi `unchanged / modified / new / deleted`.

Focus su una singola subfolder (mostra l'elenco esplicito dei file cambiati):

```powershell
.\scripts\session_resume.ps1 -Folder "$env:LETTERDOC_SOURCE_ONEDRIVE\Helpdesk_PC formatting"
```

### Registrare/aggiornare uno snapshot (post-ingest)

Da eseguire una volta, al termine di un ciclo di ingest, dopo `--apply` su
`skills-repo`:

```powershell
.\.venv\Scripts\python.exe scripts\ingest_state.py track `
    --folder "$env:LETTERDOC_SOURCE_ONEDRIVE\Helpdesk_PC formatting" `
    --source ONEDRIVE `
    --commit (git -C $env:LETTERDOC_SKILLS_REPO rev-parse HEAD)
```

Da quel momento, ogni sessione successiva mostrera' i delta rispetto a quello
snapshot. Le subfolder che non sono mai state ingerite non compaiono nel
digest finche' non vengono registrate la prima volta.

### Avviare graphify con il modello corretto

Le sessioni `/graphify` girano dentro la cartella sorgente, non nella root
del progetto, quindi non ereditano il default modello di `lettore-doc`.
Usare il launcher dedicato:

```powershell
.\scripts\start_graphify.ps1 -SourceFolder "$env:LETTERDOC_SOURCE_ONEDRIVE\<subfolder>"
```

Apre Claude Code dentro la subfolder con `--model claude-opus-4-7`; dentro la
sessione lanciare poi `/graphify .`.

---

## Uso - Pipeline di estrazione skill (aggiornamento tassonomia)

Questa pipeline estrae skill dai documenti sorgente e aggiorna `skills-repo`
(il sito pubblico su GitHub Pages).

### Passo 1 - graphify sulla sorgente (consuma token Claude Code)

```powershell
cd <cartella-sorgente>
claude
```

Dentro Claude Code:

```
/model claude-sonnet-4-5
/graphify .
```

Attendere il completamento. Verificare `graphify-out/GRAPH_REPORT.md` per un
riepilogo dei nodi estratti.

Per aggiornamenti incrementali (solo file modificati):

```
/graphify . --update
```

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

### Passo 5 - Revisionare il diff

```powershell
notepad _intermediate\taxonomy_diff.md
```

Rimuovere i falsi positivi dalla sezione "Fit". Accettare o rinominare le
"New Capabilities" proposte. Eliminare le "New Domains" non rilevanti.

### Passo 6 - Applicare (dry-run poi apply)

```powershell
# Verifica senza modifiche
.\.venv\Scripts\python.exe scripts\export_to_taxonomy.py `
  --diff-json   _intermediate\taxonomy_diff.json `
  --skills-repo "J:\...\skills-repo" --dry-run

# Applicazione
.\.venv\Scripts\python.exe scripts\export_to_taxonomy.py `
  --diff-json   _intermediate\taxonomy_diff.json `
  --skills-repo "J:\...\skills-repo" --apply
```

### Passo 7 - Commit e push

```powershell
cd "J:\...\skills-repo"
git add docs\
git commit -m "Update taxonomy - $(Get-Date -Format 'yyyy-MM-dd')"
git push
```

GitHub Actions fa la build MkDocs e pubblica su Pages. Il sito è aggiornato
in ~1 minuto a https://alesop95.github.io/skills/.

---

## Uso - Vault Obsidian privato

Genera un vault Obsidian navigabile con grafo di relazioni dai documenti sorgente.
Output in `vault-output/` (non pubblicato online).

```powershell
# Run completo
.\run_pipeline.ps1 -SourceFolder "<percorso-sorgente>"

# Solo vault (dopo aggiornamento sintesi narrative)
.\run_pipeline.ps1 -SourceFolder "<percorso-sorgente>" -OnlyVault

# Incrementale (salta i file con hash invariato)
.\run_pipeline.ps1 -SourceFolder "<percorso-sorgente>" -Incremental
```

Per le sintesi narrative, avviare Claude Code dalla cartella del progetto e
usare il subagente:

```
Usa il subagente lettore-documentazione per generare le sintesi narrative
di tutti i documenti in _intermediate/structure.json.
Salva ogni sintesi in _intermediate/summaries/ con il safe-stem corrispondente.
```

---

## Uso - Knowledge Graph del portfolio

Genera una visualizzazione interattiva della tassonomia come grafo navigabile
da aggiungere al sito pubblico (opzionale, consuma token).

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

Commit e push di `docs/graphify-out/graph.html`. Il file sarà accessibile a
`alesop95.github.io/skills/graphify-out/graph.html` e linkato dall'`index.md`.

---

## Problemi noti

**OneDrive "solo cloud"**: i file in modalità solo-cloud non sono accessibili a
python-docx. Clic destro sulla cartella sorgente in Esplora File →
"Mantieni sempre su questo dispositivo".

**File .doc legacy**: solo `.docx` è supportato. Aprire in Word e salvare
come `.docx`.

**Documenti scansionati senza OCR**: il parser segnala `text_length: 0`.
Eseguire OCR prima della pipeline.

**PowerShell rifiuta gli script**: se `.\setup.ps1` dà errore di execution
policy, da PowerShell come admin:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

**macOS - permessi script .sh**:

```bash
chmod +x setup.sh run_pipeline.sh
```

**Git repo su filesystem non-NTFS** (es. Google Drive, exFAT): aggiungere
il percorso alle directory sicure:

```powershell
git config --global --add safe.directory '<percorso-repo>'
```

---

## Sicurezza

Gli script Python della pipeline vault Obsidian sono completamente offline.
Il contenuto integrale dei `.docx` non viene mai trasmesso a servizi esterni.

graphify trasmette il contenuto dei documenti al modello Claude durante la
sessione Claude Code. I documenti vengono processati nell'account Claude
dell'utente autenticato. La policy di Anthropic per i piani Team e superiori
esclude l'uso dei dati per il training del modello.

`export_to_taxonomy.py` applica l'`anonymization_map` prima di scrivere
qualsiasi testo in `skills-repo`: nomi di persone e ragioni sociali vengono
sostituiti con `[PERSONA_N]` e `[AZIENDA_N]`. Il repository pubblico non
contiene mai dati nominativi.

---

Per dettagli architetturali su ogni script, le soglie di classificazione,
il formato dei file intermedi, e le estensioni future, vedere `GUIDA-TECNICA.md`.
