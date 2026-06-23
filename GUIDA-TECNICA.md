# Guida tecnica - lettore-doc

*Sistema di estrazione skill da documentazione locale e pubblicazione su sito web statico*

Versione 2.0 - Maggio 2026

---

## Indice

1. [Architettura generale](#1-architettura-generale)
2. [Le sorgenti dati](#2-le-sorgenti-dati)
3. [Il motore privato - lettore-doc](#3-il-motore-privato--lettore-doc)
4. [La pipeline del vault Obsidian privato](#4-la-pipeline-del-vault-obsidian-privato)
5. [La pipeline di estrazione skill](#5-la-pipeline-di-estrazione-skill)
6. [Il sito pubblico - skills-repo](#6-il-sito-pubblico--skills-repo)
7. [Il workflow operativo](#7-il-workflow-operativo)
8. [Manutenzione e tuning](#8-manutenzione-e-tuning)
9. [Estensioni future](#9-estensioni-future)

---

## 1. Architettura generale

### 1.1 I due repository

Il sistema è composto da due repository con scopi opposti.

**`lettore-doc`** (privato, locale su `E:\lettore-doc\`) è il motore di elaborazione. Legge documenti grezzi da cartelle locali, estrae conoscenza semantica tramite un modello LLM, applica post-processing specializzato per italiano formale aziendale, e prepara contenuto curato da pubblicare. Non va mai online. Contiene tutto il codice, i dati di lavoro intermedi (rigenerabili e gitignored), e il vault Obsidian privato.

**`skills-repo`** (`alesop95/skills`, pubblico su GitHub) è l'output. Contiene esclusivamente il risultato già elaborato e anonimizzato: le pagine della tassonomia di competenze, servite come sito web statico su GitHub Pages. Nessun file sorgente, nessun dato sensibile lo attraversa mai.

### 1.2 Il confine di sicurezza

Il confine è fisico: `export_to_taxonomy.py` è l'unico script che scrive in `skills-repo`, e prima di farlo applica l'`anonymization_map` prodotta da `enrich_graph.py`, sostituendo ragioni sociali con `[AZIENDA_N]` e nomi propri con `[PERSONA_N]`. Il testo che arriva in `skills-repo` non contiene mai nomi di clienti, codici progetto interni, o riferimenti organizzativi sensibili.

La separazione tra `_intermediate/` e `vault-output/` riflette lo stesso principio: la prima cartella contiene dati di lavoro che possono essere cancellati e rigenerati in qualsiasi momento (derivati dalla cartella sorgente). La seconda contiene il vault navigabile che l'utente apre, esplora, e può modificare a mano. I due piani non si toccano, permettendo di rifare l'indicizzazione senza perdere annotazioni manuali nel vault.

### 1.3 Disclosure progressiva a tre livelli

I documenti sorgente sono lunghi. Un `.docx` aziendale tipico vale circa 15-20k token. Una cartella di cento documenti vale quindi più o meno un milione e mezzo di token - una finestra di contesto da 200k token non basta a contenerne nemmeno un sesto. Caricarli tutti nel modello sarebbe non solo impossibile, ma sbagliato: l'ottanta per cento del contenuto serve come riferimento ricercabile, non come materiale di ragionamento attivo.

La soluzione è una disclosure progressiva su tre livelli:

- **Livello 1 - Scheletro**: solo titolo, gerarchia di intestazioni e conteggi per sezione. Pesa tra 50 e 200 token per documento. Un'intera cartella di duecento file entra in meno di trentamila token.
- **Livello 2 - Sezioni-preview**: aggiunge i primi 200 caratteri e gli ultimi 100 di ogni sezione, più le entità rilevate. Pesa tra 500 e 2.000 token per documento. Va caricato solo per i documenti su cui si vuole ragionare.
- **Livello 3 - Contenuto completo di una sezione**: lettura puntuale, si attiva solo per rispondere a una domanda precisa su un documento specifico (`parse_docx.py full-section --file X --section "..."`)

Il subagente Claude Code lavora prevalentemente al Livello 1, scende al Livello 2 per le sintesi narrative, e al Livello 3 solo su richiesta esplicita.

### 1.4 Separazione tra deterministico e linguistico

- **Deterministico** (script Python locali): parsing dei `.docx`, estrazione entità con regex, calcolo del grafo, generazione Markdown, arricchimento del grafo, classificazione verso la tassonomia, iniezione nelle pagine. Veloce, offline, costo zero, output identico a ogni esecuzione.
- **Linguistico** (graphify + modello Claude): estrazione semantica di entità e relazioni dai documenti, sintesi narrative del vault. Consuma token, output variabile tra esecuzioni.

Tre conseguenze pratiche: il sistema è **riproducibile** (rilanciando gli script si ottiene lo stesso grafo), **economico** (il parsing costa CPU locale, non token), **ispezionabile** (tutti gli stati intermedi sono JSON leggibili e modificabili a mano per correggere errori senza rilanciare nulla).

### 1.5 L'ambiente Python isolato

Il virtual environment vive in `.venv/` dentro la cartella del progetto. Tutto è contenuto in `E:\lettore-doc\`. Gli script di orchestrazione lanciano direttamente il Python del venv tramite path completo, senza attivare nulla nella sessione.

**Attenzione al rename/spostamento della cartella**: i launcher dentro `.venv/Scripts/` hanno il path della cartella originale codificato. Se la cartella viene rinominata o spostata, il venv va ricreato da zero:

```powershell
Remove-Item -Recurse -Force .\.venv
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python -m spacy download it_core_news_sm
```

---

## 2. Le sorgenti dati

Le sorgenti sono configurate in `sources.yml` nella root di `lettore-doc`:

```yaml
sources:
  - path: "C:/Users/Utente/OneDrive/Documenti-IT"
    label: documenti_it
    include_extensions: [.docx, .txt, .md]
    exclude_patterns: ["~$*", "_archive/*"]

  - path: "J:/googleDrive_sync/Portfolio and ongoing studies/IT-RELATED"
    label: portfolio_it
    include_extensions: [.docx, .txt, .md]
    exclude_patterns: ["~$*"]
```

I formati processati: `.docx` (convertiti in Markdown tramite python-docx), `.txt` (letti direttamente), `.md` (letti direttamente), `.png`/`.jpg` (analizzati in modalità vision per estrarne contenuto testuale, es. diagrammi con etichette).

**Attenzione OneDrive**: i file in modalità "solo cloud" (icona nuvola) non sono accessibili a python-docx. Clic destro → "Mantieni sempre su questo dispositivo" prima di lanciare la pipeline.

---

## 3. Il motore privato - `lettore-doc`

### 3.1 Struttura del repository

```
E:\lettore-doc\
├── .claude\
│   ├── agents\lettore-documentazione.md   subagente Claude Code
│   └── skills\
│       ├── grafo-conoscenza\SKILL.md
│       └── parsing-docx\SKILL.md
├── scripts\
│   ├── parse_docx.py                   parsing token-efficient (3 livelli)
│   ├── extract_entities.py             regex italiane, 10 categorie
│   ├── build_knowledge_graph.py        grafo pesato, 6 etichette semantiche
│   ├── generate_vault.py               vault Obsidian privato
│   ├── enrich_graph.py                 post-processing italiano su graph.json
│   ├── generate_taxonomy_index.py      indicizza tassonomia da mkdocs.yml
│   ├── map_to_taxonomy.py              classifica nodi → fit/new_cap/new_dom
│   └── export_to_taxonomy.py           inietta evidenze in skills-repo
├── _intermediate\                      dati di lavoro (gitignored)
│   ├── structure.json
│   ├── entities.json
│   ├── graph.json
│   ├── enriched_graph.json
│   ├── taxonomy_index.json
│   ├── taxonomy_diff.md / .json
│   ├── sections\                       un JSON per documento
│   └── summaries\                      sintesi narrative scritte dal modello
├── vault-output\                       vault Obsidian privato (gitignored)
│   └── _data\                          graph.json e entities.json per Dataview
├── .venv\                              (gitignored)
├── sources.yml
├── requirements.txt
├── setup.ps1 / setup.sh
└── run_pipeline.ps1 / run_pipeline.sh
```

### 3.2 Il subagente Claude Code

`.claude/agents/lettore-documentazione.md` definisce un subagente con system prompt, tool consentiti (Read, Write, Edit, Bash, Glob, Grep), e modello (Sonnet). La regola principale: **non aprire mai un `.docx` con il tool Read direttamente** - su un `.docx` caricherebbe l'intera struttura XML producendo migliaia di token inutili. La via corretta è sempre usare gli script Python.

---

## 4. La pipeline del vault Obsidian privato

Orchestrata da `run_pipeline.ps1/.sh`. Genera il vault Obsidian locale, non produce output pubblici.

### 4.1 Fase 1 - Parsing skeleton

`parse_docx.py skeleton` estrae la gerarchia di intestazioni da ogni `.docx`. Riconoscimento heading duplice: stile Word (`Heading 1`, `Titolo 1`) oppure pattern numerico in testa al paragrafo (`1.`, `1.1`, `1.1.1`) come fallback - necessario perché molti documenti aziendali italiani numerano manualmente senza usare gli stili nativi.

**Parallelizzazione**: `concurrent.futures.ProcessPoolExecutor` con worker = min(CPU, 8). Su macchina a 8 core: 200 documenti scheletrati in <30 secondi.

**Modalità incrementale** (`--incremental`): confronta hash SHA256 dei primi 256 KB con il run precedente, processa solo i file modificati. Su 200 documenti di cui 5 modificati: risparmio ~40×.

Output: `_intermediate/structure.json` (~4-5 MB anche per 200 documenti).

### 4.2 Fase 2 - Sections-preview

`parse_docx.py sections-preview` scrive un JSON per documento in `_intermediate/sections/<safe-stem>.json`, con per ogni sezione: incipit (200 char), chiusura (100 char), tabelle estratte come lista di dict, flag `has_images`.

La separazione in due fasi (scheletro + preview) ottimizza il primo accesso: il subagente vede lo scheletro dell'intera cartella prima di decidere dove scendere al Livello 2.

### 4.3 Fase 3 - Estrazione entità

`extract_entities.py` applica regex calibrate per l'italiano tecnico-amministrativo. Per nove categorie su dieci è euristica deterministica; la categoria `PROPER_NOUN` usa spacy (modello `it_core_news_sm`) per NER[^1] su testo italiano quando il pacchetto è installato, e cade in fallback regex+stoplist in sua assenza. Il fallback funziona ma produce qualità inferiore sui nomi di persona, che alimentano i wiki-link tra le note.

[^1]: *NER*, Named Entity Recognition — tecnica che identifica e classifica automaticamente entità nominate nel testo (persone, luoghi, organizzazioni) senza regole scritte a mano.

**Setup spacy** (una volta per venv):
```powershell
.\.venv\Scripts\pip install spacy
.\.venv\Scripts\python -m spacy download it_core_news_sm
```
spacy è già in `requirements.txt`; il download del modello linguistico è un passaggio separato non gestibile da pip.

**Le 10 categorie:**

| Categoria | Descrizione | Esempio |
|-----------|-------------|---------|
| `ACRONYM` | Sigle 2-7 lettere maiuscole (con stoplist) | RTI, DURC, SAL |
| `COMPANY` | Ragioni sociali con suffisso societario | AlphaBeta SpA, Gamma Srl |
| `PROPER_NOUN` | Nomi propri di persona o entità | Mario Rossi |
| `PROJECT_CODE` | Codici alfanumerici con separatore | PRJ-001, TECH-2024-08 |
| `LAW_REF` | Riferimenti normativi italiani/europei | D.Lgs 50/2016, art. 80 |
| `DATE` | Date in formati italiani, ISO, testuale | 15/03/2024, 15 marzo 2024 |
| `AMOUNT` | Importi in euro | EUR 15.000,00 |
| `EMAIL` | Indirizzi email | mario@example.com |
| `URL` | Web | https://example.com |
| `DOC_REF` | Riferimenti espliciti a documenti | "vedi specifica X.docx" |

La `ACRONYM_STOPLIST` esclude acronimi tecnici comuni (PDF, API, CSV, XML, SSL, URL, ecc.).

**Merge degli alias societari**: "AlphaBeta SpA" e "AlphaBeta S.p.A." vengono unificate. Lo script normalizza rimuovendo suffisso, spazi e punteggiatura, portando in minuscolo. La variante più lunga diventa il nome canonico, i conteggi vengono sommati.

Output `_intermediate/entities.json`.

### 4.4 Fase 4 - Grafo di conoscenza

`build_knowledge_graph.py` calcola tutti gli archi candidati tra documenti. Formula del peso:

```
peso(A,B) = W_JACCARD × Jaccard(entità_A, entità_B)
          + W_EXPLICIT_REF × min(riferimenti/3, 1.0)
          + W_FOLDER × vicinanza_cartella(A, B)
          + W_TEMPORAL × vicinanza_temporale(A, B)
          + W_TITLE_SIM × similarità_titolo(A, B)
```

**Pesi di default:**

| Parametro | Valore | Motivazione |
|-----------|--------|-------------|
| `W_JACCARD` | 0.40 | Sovrapposizione entità - segnale semantico più affidabile |
| `W_EXPLICIT_REF` | 0.30 | Riferimento esplicito - specifico ma raro; saturato a 3 |
| `W_FOLDER` | 0.10 | Stessa cartella (1.0) / cartella padre comune (0.5) |
| `W_TEMPORAL` | 0.10 | 1.0 se ≤7 gg, lineare fino a 0 a 180 gg |
| `W_TITLE_SIM` | 0.10 | Jaccard token del nome file - cattura serie temporali |

Il **Jaccard sulle entità** usa le categorie ACRONYM, COMPANY, PROPER_NOUN, PROJECT_CODE. Il **Jaccard del titolo** esclude token come "docx", "final", "copia", "v", "rev".

**Le 6 etichette semantiche degli archi** (in ordine di priorità decrescente del segnale):

| Etichetta | Condizione | Tipo di segnale |
|-----------|-----------|-----------------|
| `riferisce_esplicitamente` | ≥1 riferimento esplicito | Fatto certo |
| `serie_temporale` | title_sim ≥ 0.5 AND temporal ≥ 0.3 | Quasi certo |
| `stesso_progetto` | title_sim ≥ 0.4 | Molto probabile |
| `condivide_entita_chiave` | ≥5 entità in comune | Statistico forte |
| `topica_affine` | Jaccard entità > 0.15 | Statistico medio |
| `correlato_debole` | Tutto il resto sopra soglia | Segnale lasco |

**Soglie**: archi < 0.15 non vengono mostrati (ma conservati in `graph.json`). Cap di 8 link per nodo. Nodi con ≥15 archi → "hub", candidati a MOC dedicata.

Output `_intermediate/graph.json`: archi, top-K vicini per nodo, hub, documenti isolati, clustering naive per entità rappresentativa.

### 4.5 Fase 5 - Generazione del vault

`generate_vault.py` produce un file `.md` per ogni documento in `vault-output/`.

**Struttura di ogni file:**

```
1. Frontmatter YAML (titolo, file_sorgente, tipologia, data, hash, entità,
   acronimi, riferimenti normativi, tag gerarchici, data aggiornamento)
2. H1 titolo + callout > [!summary] con sintesi narrativa
3. Indice sezioni del documento sorgente
4. "Documenti correlati" raggruppati per etichetta semantica (con peso numerico)
5. Estratto per sezione con wiki-link inline automatici
```

**Frontmatter YAML standard:**
```yaml
---
titolo: "Nome documento sorgente"
file_sorgente: "percorso/relativo/originale.docx"
tipologia: procedura | contratto | verbale | manuale | capitolato | specifica | altro
data_documento: YYYY-MM-DD
hash_origine: <sha256_8char>
parole_totali: 4218
sezioni: 12
collegamenti: 5
entita_principali: [Cliente X, PRJ-001]
acronimi: [RTI, DURC]
riferimenti_normativi: ["D.Lgs 50/2016"]
tags: [tipologia/procedura, azienda/cliente_x_spa, progetto/prj-001]
aggiornato: 2026-05-22T14:30:00
---
```

I tag sono gerarchici (`#progetto/prj-001`, `#azienda/alphabeta_spa`), usabili come filtri in Obsidian.

**Wiki-link inline automatici**: lo script scansiona il testo degli estratti e sostituisce la prima occorrenza di qualsiasi parola (≥4 caratteri) che corrisponde al radicale del nome di un altro documento del vault con `[[Nome Documento]]`. Max un link per documento per estratto, per evitare rumore.

**`_data/`**: dentro `vault-output/`, contiene copie di `graph.json` e `entities.json` per i plugin Obsidian come Dataview (query SQL-like sul vault).

**Tipologia** dedotta dal nome file via euristica: "verbale" → verbale, "contratto" → contratto, ecc. Non riconosciuti → "altro".

---

## 5. La pipeline di estrazione skill

Estrae skill dai documenti sorgente e aggiorna `skills-repo`.

### 5.1 graphify (consuma token)

Skill registrata in Claude Code. Si lancia con `/graphify .` dalla cartella sorgente. Usa il modello attivo nella sessione per costruire un grafo semantico.

**Output in `graphify-out/`:**
- `graph.json` - nodi (`label`, `id`, `community`, `norm_label`, `source_file`, `file_type`), archi (`source`, `target`, `relation`, `confidence`, `confidence_score`, `weight`), iperedges (relazioni di gruppo)
- `graph.html` - visualizzazione interattiva
- `GRAPH_REPORT.md` - god nodes, surprising connections, community labels, suggested questions
- `cost.json` - token consumati
- `manifest.json` - hash per `--update` incrementale

**Stima token**: 39 file / 126k parole → 113k input + 29k output (~3.700 token/file). Proiezione 200 documenti: ~580k token. La modalità `--update` processa solo i file modificati dall'ultimo run.

### 5.2 enrich_graph.py (offline)

Per ogni nodo: legge il testo del `source_file`, applica le 10 regex di `extract_entities.py`, aggiunge `italian_entities` e `text_preview` (200 char).

Costruisce l'`anonymization_map`: COMPANY e PROPER_NOUN ordinate per frequenza decrescente → `[AZIENDA_1]`, `[PERSONA_1]`, ecc.

Output: `_intermediate/enriched_graph.json` (stessa struttura di `graph.json` + campi aggiuntivi).

### 5.3 generate_taxonomy_index.py (offline)

Legge `mkdocs.yml` di `skills-repo`, per ogni Capability estrae keyword da "Technologies & tools" e "Overview" (36-60 keyword/Capability). Include `domain_keywords` base per ogni Domain.

Output: `_intermediate/taxonomy_index.json` (7 Domain, 29 Capability, keyword per Capability e Domain).

### 5.4 map_to_taxonomy.py (offline)

Classifica ogni nodo via **recall score**:

```
recall(nodo, cap) = |tokens_nodo ∩ keywords_cap| / |tokens_nodo|
```

Token del community label del nodo aggiunti per aumentare copertura semantica.

| Condizione | Classificazione |
|------------|----------------|
| recall_cap ≥ 0.15 | `fit` sulla Capability |
| recall_cap < 0.15 AND domain_recall ≥ 0.08 | `new_capability` nel Domain |
| nessuna corrispondenza | `new_domain` |
| score < 0.01 | non classificato |

Output: `taxonomy_diff.md` + `taxonomy_diff.json` (sezioni ✅ Fit, 🆕 New Capabilities, 🗂 New Domains, ⚠️ Non classificati).

### 5.5 Revisione manuale

Aprire `_intermediate/taxonomy_diff.md`:
- **Fit**: rimuovere falsi positivi (specie da nodi `.png` con solo il titolo come testo)
- **New Capabilities**: accettare, rinominare se necessario, verificare ≥2-3 nodi rilevanti
- **New Domains**: valutare caso per caso

### 5.6 export_to_taxonomy.py (offline)

`--dry-run` (default): stampa le operazioni senza toccare nulla. `--apply`: scrive i file.

**Per i fit**: inietta un H3 sotto `## Projects & evidence` di ogni Capability:

```markdown
### Nome nodo
<!-- graphify-evidence-id: abc123def456 -->

- **Source**: `nome-file.md`
- **Graph community**: Community Label

Testo preview anonimizzato...

*Technology stack: to be enriched from source document.*
```

Il commento HTML è l'**ID di idempotenza** (SHA256 breve di `node_id + capability_slug`). Lo script controlla prima se l'ID esiste già - se sì, salta. Eseguibile più volte senza duplicare contenuto.

**Per le new Capability**: crea il `.md` con schema a quattro H2 e stampa la riga da aggiungere manualmente al `mkdocs.yml` (non automatizzato per scelta: ogni modifica della navigazione pubblica va approvata consapevolmente).

---

## 6. Il sito pubblico - `skills-repo`

### 6.1 Struttura

```
J:\...\skills-repo\
├── .github\workflows\deploy.yml   build MkDocs + deploy Pages
├── docs\
│   ├── index.md
│   ├── cloud\, data\, infrastructure\, it-operations\
│   ├── management\, security\, software-engineering\
│   └── graphify-out\graph.html    Knowledge Graph interattivo
├── mkdocs.yml
├── requirements.txt               mkdocs-material>=9.5.0
├── README.md
└── .gitignore
```

### 6.2 Schema fisso delle Capability pages

Ogni Capability page ha quattro H2 in ordine invariato:

| Sezione | Autore | Mai sovrascritta? |
|---------|--------|-------------------|
| `## Overview` | Manuale | Sì |
| `## Technologies & tools` | Manuale | Sì |
| `## Responsibilities & operational scope` | Manuale | Sì |
| `## Projects & evidence` | `export_to_taxonomy.py` | No (append only) |

### 6.3 GitHub Actions e deploy

`git push` su `main` → build `mkdocs build --strict` → deploy Pages (~1 minuto). Il flag `--strict` fa fallire la build su link rotti - safety net voluto.

### 6.4 Knowledge Graph del portfolio

`/graphify docs/` in Claude Code → `docs/graphify-out/graph.html`. Visualizzazione interattiva della tassonomia come grafo. Da lanciare solo quando la struttura cambia significativamente.

```powershell
cd "J:\...\skills-repo"
claude
/graphify docs/
# Prima volta:
Move-Item graphify-out docs\graphify-out
# Versionare solo graph.html, aggiungere al .gitignore i file intermedi
git add docs\graphify-out\graph.html
git commit -m "Update Skills Knowledge Graph"
git push
```

### 6.5 Obsidian come editor

Aprire `docs/` come vault Obsidian (`File → Open folder as vault`). `.obsidian/` nel `.gitignore`. Utile per editing manuale e navigazione. Non è il canale di scrittura automatica.

---

## 7. Il workflow operativo

### 7.1 Ciclo di aggiornamento tassonomia

```powershell
# PASSO 1 - graphify (consuma token, ~3-20 min)
cd <cartella-sorgente>
claude
/model claude-sonnet-4-5
/graphify .

# PASSO 2 - taxonomy index + enrich (~30 sec, offline)
cd E:\lettore-doc
.\.venv\Scripts\python.exe scripts\generate_taxonomy_index.py `
  --skills-repo "J:\...\skills-repo" --output _intermediate\taxonomy_index.json

.\.venv\Scripts\python.exe scripts\enrich_graph.py `
  --graph "<sorgente>\graphify-out\graph.json" --workdir "<sorgente>" `
  --output _intermediate\enriched_graph.json

# PASSO 3 - classifica (~5 sec, offline)
.\.venv\Scripts\python.exe scripts\map_to_taxonomy.py `
  --enriched-graph _intermediate\enriched_graph.json `
  --taxonomy _intermediate\taxonomy_index.json `
  --output-md _intermediate\taxonomy_diff.md `
  --output-json _intermediate\taxonomy_diff.json

# PASSO 4 - revisione manuale
notepad _intermediate\taxonomy_diff.md

# PASSO 5 - apply (~5 sec, offline)
.\.venv\Scripts\python.exe scripts\export_to_taxonomy.py `
  --diff-json _intermediate\taxonomy_diff.json `
  --skills-repo "J:\...\skills-repo" --dry-run
# ...poi --apply dopo verifica

# PASSO 6 - deploy (~1 min)
cd "J:\...\skills-repo"
git add docs\
git commit -m "Update taxonomy - $(Get-Date -Format 'yyyy-MM-dd')"
git push
```

### 7.2 Pipeline vault Obsidian privato

```powershell
cd E:\lettore-doc
.\run_pipeline.ps1 -SourceFolder "<percorso>"
.\run_pipeline.ps1 -SourceFolder "<percorso>" -Incremental
.\run_pipeline.ps1 -SourceFolder "<percorso>" -OnlyVault
```

Per le sintesi narrative, usare il subagente `lettore-documentazione` dentro Claude Code.

### 7.3 Tempi tipici (aggiornamento tassonomia)

| Corpus | graphify | offline | revisione | totale |
|--------|----------|---------|-----------|--------|
| 20-30 file | 2-5 min | 1 min | 5 min | ~15 min |
| 100-150 file | 10-15 min | 3 min | 15 min | ~35 min |
| 200+ file | 20-30 min | 5 min | 25 min | ~55 min |

---

## 8. Manutenzione e tuning

### 8.1 Soglie di classificazione (`map_to_taxonomy.py`)

```python
THRESHOLD_FIT    = 0.15   # alzare a 0.20 se troppi falsi positivi
THRESHOLD_DOMAIN = 0.08   # abbassare a 0.06 se troppo pochi new_capability
MIN_SCORE_REPORT = 0.01   # sotto questa → non classificato
```

Dopo modifica, rilanciare solo `map_to_taxonomy.py` - `enriched_graph.json` rimane valido.

### 8.2 Pesi del grafo (`build_knowledge_graph.py`)

```python
W_JACCARD      = 0.40   # alzare se molti documenti simili nella forma
W_EXPLICIT_REF = 0.30
W_FOLDER       = 0.10
W_TEMPORAL     = 0.10
W_TITLE_SIM    = 0.10   # alzare per serie ben strutturate (v1, v2, v3)
MIN_EDGE_WEIGHT = 0.15  # alzare per grafo più rado, abbassare per più denso
MAX_LINKS_PER_DOC = 8
```

Dopo modifica, rilanciare `build_knowledge_graph.py` + `generate_vault.py`. graphify non va rilanciato.

### 8.3 Regex italiane (`extract_entities.py`)

- `PROJECT_CODE_RE`: adattare al formato dei codici progetto locali
- `ACRONYM_STOPLIST`: aggiungere acronimi settoriali che generano rumore
- `COMPANY_SUFFIX_RE`: già copre SpA, Srl, SaS, GmbH, Ltd, Inc e varianti

Dopo modifica, rilanciare `enrich_graph.py` a partire dal `graph.json` già prodotto.

### 8.4 Keyword della tassonomia

Arricchire le sezioni "Technologies & tools" e "Overview" nei `.md` di `skills-repo` per migliorare il matching di quella Capability. Rilanciare `generate_taxonomy_index.py`.

Le `DOMAIN_BASE_KEYWORDS` base sono in testa a `generate_taxonomy_index.py`.

### 8.5 Migrazione su nuovo PC

```powershell
# 1. Copia lettore-doc senza .venv, _intermediate, vault-output
# 2. Sul nuovo PC:
.\setup.ps1
# 3. Scarica il modello spacy italiano (non incluso in requirements.txt):
.\.venv\Scripts\python -m spacy download it_core_news_sm
# 4. Clona skills-repo:
git clone git@github-personal:alesop95/skills.git "E:\skills"
```

---

## 9. Estensioni future

### 9.1 Automazione multi-sorgente completa

`run_graphify_all.ps1` gestisce il ciclo da `sources.yml`, ma il passaggio graphify rimane semi-interattivo (richiede sessione Claude Code). L'automazione completa richiede API key Anthropic separata o un futuro flag CLI di graphify per headless mode.

### 9.2 Embeddings semantici

Il matching attuale usa recall su keyword. Con embeddings vettoriali si catturano relazioni che le keyword non vedono (stesse competenze, terminologie diverse). L'architettura è predisposta: cambia solo la funzione di scoring in `map_to_taxonomy.py`, il resto della pipeline rimane invariato.

### 9.3 Connettori MCP per sorgenti remote

Gli script lavorano su `graph.json` indipendentemente da come è stato prodotto. Basterebbe un secondo script che produce lo stesso formato attingendo da API Google Drive, Notion, Confluence via MCP.

### 9.4 Clustering gerarchico

Il clustering nel vault usa un approccio naive (un solo seed per documento). Per cluster più sofisticati: clustering gerarchico via scipy sul vettore di entità per documento. Valore aggiunto raramente giustifica la dipendenza.
