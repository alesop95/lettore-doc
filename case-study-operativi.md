# Case study operativi — lettore-doc + skills-repo

Tutti i casi d'uso reali con comandi concreti. I path usano le variabili di ambiente gia' settate nel sistema.

---

## Caso 1 — Primo run assoluto su una cartella sorgente

**Scenario**: il sistema e' appena stato installato. Nessun run precedente. Vuoi processare per la prima volta `LETTERDOC_SOURCE_ONEDRIVE`.

```powershell
# Apri Claude Code sulla cartella sorgente
cd $env:LETTERDOC_SOURCE_ONEDRIVE
claude
```

Dentro Claude Code:
```
/model claude-sonnet-4-5
/graphify .
```

Attendi il completamento (10-30 min su corpus grande). Leggi `graphify-out/GRAPH_REPORT.md` per verificare la qualita' dell'estrazione.

```powershell
# Torna su lettore-doc e lancia la pipeline offline
cd E:\lettore-doc

.\.venv\Scripts\python.exe scripts\generate_taxonomy_index.py `
  --output _intermediate\taxonomy_index.json

.\.venv\Scripts\python.exe scripts\enrich_graph.py `
  --graph   "$env:LETTERDOC_SOURCE_ONEDRIVE\graphify-out\graph.json" `
  --workdir "$env:LETTERDOC_SOURCE_ONEDRIVE" `
  --output  _intermediate\enriched_graph.json

.\.venv\Scripts\python.exe scripts\map_to_taxonomy.py `
  --enriched-graph _intermediate\enriched_graph.json `
  --taxonomy       _intermediate\taxonomy_index.json `
  --output-md      _intermediate\taxonomy_diff.md `
  --output-json    _intermediate\taxonomy_diff.json

# Revisiona
notepad _intermediate\taxonomy_diff.md

# Applica
.\.venv\Scripts\python.exe scripts\export_to_taxonomy.py `
  --diff-json   _intermediate\taxonomy_diff.json `
  --skills-repo "$env:LETTERDOC_SKILLS_REPO" --dry-run

.\.venv\Scripts\python.exe scripts\export_to_taxonomy.py `
  --diff-json   _intermediate\taxonomy_diff.json `
  --skills-repo "$env:LETTERDOC_SKILLS_REPO" --apply

# Pubblica
cd "$env:LETTERDOC_SKILLS_REPO"
git add docs\
git commit -m "Initial taxonomy population from documenti-it"
git push
```

**Risultato atteso**: sito aggiornato in ~1 minuto su `alesop95.github.io/skills/`.

---

## Caso 2 — Aggiornamento mensile (corpus invariato + nuovi documenti)

**Scenario**: e' passato un mese. Hai aggiunto nuovi file alla cartella sorgente ma la maggior parte dei documenti non e' cambiata. Vuoi un refresh efficiente.

```powershell
# graphify --update processa solo i file modificati dal run precedente
cd $env:LETTERDOC_SOURCE_ONEDRIVE
claude
```

Dentro Claude Code:
```
/model claude-sonnet-4-5
/graphify . --update
```

```powershell
cd E:\lettore-doc

.\.venv\Scripts\python.exe scripts\generate_taxonomy_index.py `
  --output _intermediate\taxonomy_index.json

.\.venv\Scripts\python.exe scripts\enrich_graph.py `
  --graph   "$env:LETTERDOC_SOURCE_ONEDRIVE\graphify-out\graph.json" `
  --workdir "$env:LETTERDOC_SOURCE_ONEDRIVE" `
  --output  _intermediate\enriched_graph.json

.\.venv\Scripts\python.exe scripts\map_to_taxonomy.py `
  --enriched-graph _intermediate\enriched_graph.json `
  --taxonomy       _intermediate\taxonomy_index.json `
  --output-md      _intermediate\taxonomy_diff.md `
  --output-json    _intermediate\taxonomy_diff.json

notepad _intermediate\taxonomy_diff.md

.\.venv\Scripts\python.exe scripts\export_to_taxonomy.py `
  --diff-json   _intermediate\taxonomy_diff.json `
  --skills-repo "$env:LETTERDOC_SKILLS_REPO" --apply

cd "$env:LETTERDOC_SKILLS_REPO"
git add docs\
git commit -m "Monthly taxonomy update — $(Get-Date -Format 'yyyy-MM-dd')"
git push
```

**Risparmio token**: proporzionale alla percentuale di file invariati. Su 200 file di cui 10 modificati, il risparmio e' circa 95%.

---

## Caso 3 — Nuovo progetto completato (case study dal documento incollato)

**Scenario**: hai appena completato una migrazione server. Hai prodotto tre .docx con analisi tecnica, configurazioni e verbale. Li hai salvati in una sottocartella dedicata. Vuoi che le competenze appaiano sul sito entro stasera.

```powershell
# Vai nella cartella del progetto specifico
$projectPath = "J:\googleDrive_sync\Portfolio and ongoing studies\IT-RELATED\Progetti\2026-migration-server"
cd $projectPath
claude
```

Dentro Claude Code:
```
/model claude-sonnet-4-5
/graphify .
```

Stima: 3 file -> ~15k token, meno di un minuto. Leggi `graphify-out/GRAPH_REPORT.md`: god nodes attesi "Proxmox VE Cluster Migration", "SSH Tunnel Configuration", "Veeam Backup Strategy".

```powershell
cd E:\lettore-doc

.\.venv\Scripts\python.exe scripts\generate_taxonomy_index.py `
  --output _intermediate\taxonomy_index.json

.\.venv\Scripts\python.exe scripts\enrich_graph.py `
  --graph   "$projectPath\graphify-out\graph.json" `
  --workdir "$projectPath" `
  --output  _intermediate\enriched_graph.json

.\.venv\Scripts\python.exe scripts\map_to_taxonomy.py `
  --enriched-graph _intermediate\enriched_graph.json `
  --taxonomy       _intermediate\taxonomy_index.json `
  --output-md      _intermediate\taxonomy_diff.md `
  --output-json    _intermediate\taxonomy_diff.json

notepad _intermediate\taxonomy_diff.md
```

**Cosa trovi nel diff e come gestirti**:

- `Fit [Infrastructure] Infrastructure & Virtualization` -> Proxmox VE Cluster Migration, High Availability Configuration: corretto, tieni.
- `Fit [Infrastructure] Backup & Disaster Recovery` -> Veeam Backup Strategy: corretto, tieni.
- `Fit [IT Operations] System Administration` -> SSH Tunnel Configuration: corretto, tieni.
- `Fit [Infrastructure] Networking & Security` -> SSH Multi-Account Setup: falso positivo (e' documentazione Git non rete aziendale). Elimina.
- `New Capability [Infrastructure]` -> "Proxmox Ve Cluster Migration": rinomina in taxonomy_diff.md come "Proxmox VE & HA Cluster Operations", slug `proxmox-ha-cluster`, file `infrastructure/proxmox-ha-cluster.md`.

```powershell
.\.venv\Scripts\python.exe scripts\export_to_taxonomy.py `
  --diff-json   _intermediate\taxonomy_diff.json `
  --skills-repo "$env:LETTERDOC_SKILLS_REPO" --dry-run

# Output atteso: 3 iniezioni in Capability esistenti, 1 nuovo file da creare.

.\.venv\Scripts\python.exe scripts\export_to_taxonomy.py `
  --diff-json   _intermediate\taxonomy_diff.json `
  --skills-repo "$env:LETTERDOC_SKILLS_REPO" --apply
```

Lo script stampa la riga da aggiungere a `mkdocs.yml`:
```yaml
- Proxmox VE & HA Cluster Operations: infrastructure/proxmox-ha-cluster.md
```

Apri `mkdocs.yml` in `skills-repo`, aggiungi la riga sotto `Infrastructure:`, salva.

```powershell
cd "$env:LETTERDOC_SKILLS_REPO"
git add docs\
git add mkdocs.yml
git commit -m "Add evidence from 2026-migration-server — new Capability: Proxmox VE & HA Cluster Operations"
git push
```

**Risultato**: in ~1 minuto il sito ha la pagina `alesop95.github.io/skills/infrastructure/proxmox-ha-cluster/` stabile e inseribile nel CV. Tempo totale: 13 minuti.

---

## Caso 4 — Elaborare piu' sorgenti in sequenza

**Scenario**: vuoi processare sia OneDrive che Google Drive Portfolio in un unico ciclo e aggregare le skill da entrambe.

```powershell
# Sorgente 1: OneDrive
cd $env:LETTERDOC_SOURCE_ONEDRIVE
claude
# /graphify . --update
# (esci da Claude Code)

# Sorgente 2: Portfolio
cd $env:LETTERDOC_SOURCE_PORTFOLIO
claude
# /graphify . --update
# (esci da Claude Code)

cd E:\lettore-doc

# Enrich e map su sorgente 1
.\.venv\Scripts\python.exe scripts\enrich_graph.py `
  --graph   "$env:LETTERDOC_SOURCE_ONEDRIVE\graphify-out\graph.json" `
  --workdir "$env:LETTERDOC_SOURCE_ONEDRIVE" `
  --output  _intermediate\enriched_graph_onedrive.json

# Enrich e map su sorgente 2
.\.venv\Scripts\python.exe scripts\enrich_graph.py `
  --graph   "$env:LETTERDOC_SOURCE_PORTFOLIO\graphify-out\graph.json" `
  --workdir "$env:LETTERDOC_SOURCE_PORTFOLIO" `
  --output  _intermediate\enriched_graph_portfolio.json

# Genera taxonomy index (una volta sola)
.\.venv\Scripts\python.exe scripts\generate_taxonomy_index.py `
  --output _intermediate\taxonomy_index.json

# Map ciascuna sorgente e revisiona i diff separatamente
.\.venv\Scripts\python.exe scripts\map_to_taxonomy.py `
  --enriched-graph _intermediate\enriched_graph_onedrive.json `
  --taxonomy       _intermediate\taxonomy_index.json `
  --output-md      _intermediate\taxonomy_diff_onedrive.md `
  --output-json    _intermediate\taxonomy_diff_onedrive.json

.\.venv\Scripts\python.exe scripts\map_to_taxonomy.py `
  --enriched-graph _intermediate\enriched_graph_portfolio.json `
  --taxonomy       _intermediate\taxonomy_index.json `
  --output-md      _intermediate\taxonomy_diff_portfolio.md `
  --output-json    _intermediate\taxonomy_diff_portfolio.json

notepad _intermediate\taxonomy_diff_onedrive.md
notepad _intermediate\taxonomy_diff_portfolio.md

# Applica entrambi in sequenza (idempotente: nessun duplicato)
.\.venv\Scripts\python.exe scripts\export_to_taxonomy.py `
  --diff-json   _intermediate\taxonomy_diff_onedrive.json `
  --skills-repo "$env:LETTERDOC_SKILLS_REPO" --apply

.\.venv\Scripts\python.exe scripts\export_to_taxonomy.py `
  --diff-json   _intermediate\taxonomy_diff_portfolio.json `
  --skills-repo "$env:LETTERDOC_SKILLS_REPO" --apply

cd "$env:LETTERDOC_SKILLS_REPO"
git add docs\
git commit -m "Update taxonomy from all sources — $(Get-Date -Format 'yyyy-MM-dd')"
git push
```

---

## Caso 5 — Vault Obsidian privato (navigazione locale della documentazione)

**Scenario**: vuoi esplorare le relazioni tra documenti in locale, cercare chi cita chi, navigare il grafo privato.

```powershell
cd E:\lettore-doc
.\run_pipeline.ps1 -SourceFolder $env:LETTERDOC_SOURCE_ONEDRIVE
```

A fine run apri Obsidian: `File -> Open folder as vault` -> seleziona `E:\lettore-doc\vault-output\`.

Navigazione di partenza: `index.md` (Mappa della Conoscenza). Graph view: `Ctrl+G`.

**Per aggiornamento incrementale** (solo file modificati):
```powershell
.\run_pipeline.ps1 -SourceFolder $env:LETTERDOC_SOURCE_ONEDRIVE -Incremental
```

**Per rigenere solo il vault** (dopo aver aggiunto sintesi narrative):
```powershell
.\run_pipeline.ps1 -SourceFolder $env:LETTERDOC_SOURCE_ONEDRIVE -OnlyVault
```

---

## Caso 6 — Sintesi narrative con il subagente (vault privato)

**Scenario**: hai generato il vault ma le pagine mostrano il placeholder "Sintesi non ancora generata". Vuoi aggiungere le sintesi.

```powershell
cd E:\lettore-doc
claude
```

Dentro Claude Code, incolla questo prompt:
```
Usa il subagente lettore-documentazione.

Genera le sintesi narrative di tutti i documenti in _intermediate/structure.json
che NON hanno gia' un file in _intermediate/summaries/.
Per ogni documento: leggi sections/<safe-stem>.json, scrivi una sintesi
in INGLESE di 150-200 parole (scopo, tecnologie, output, contesto operativo,
nessun nome di cliente). Salva in _intermediate/summaries/<safe-stem>.md.
Procedi a lotti di 5. Dopo ogni lotto elenca i file elaborati e quanti restano.
```

A sintesi completate:
```powershell
.\run_pipeline.ps1 -SourceFolder $env:LETTERDOC_SOURCE_ONEDRIVE -OnlyVault
```

---

## Caso 7 — Aggiunta manuale di una Capability senza graphify

**Scenario**: hai competenze su un'area non ancora nella tassonomia e vuoi aggiungerla manualmente senza aspettare un run graphify.

Crea `J:\...\skills-repo\docs\<domain>\<slug>.md`:

```markdown
# Nome Capability

## Overview
[3-6 righe che descrivono la Capability]

## Technologies & tools
- **Tool 1** (versione) — qualificazione
- **Tool 2** — qualificazione

## Responsibilities & operational scope
- Responsabilita' 1
- Responsabilita' 2

## Projects & evidence
*Project entries are populated automatically from anonymized project
documentation. None yet.*
```

Aggiungi al `mkdocs.yml` sotto il Domain corretto:
```yaml
- Nome Capability: <domain>/<slug>.md
```

```powershell
cd "$env:LETTERDOC_SKILLS_REPO"
git add docs\<domain>\<slug>.md mkdocs.yml
git commit -m "Add capability: Nome Capability"
git push
```

---

## Caso 8 — Utilizzo ortogonale: Knowledge Graph del portfolio

**Scenario**: vuoi aggiornare la visualizzazione interattiva del portfolio (il `graph.html` che mostra le relazioni tra Capability come grafo navigabile). Da fare quando la struttura della tassonomia cambia significativamente.

```powershell
cd "$env:LETTERDOC_SKILLS_REPO"
claude
```

Dentro Claude Code:
```
/model claude-sonnet-4-5
/graphify docs/
```

graphify legge i .md delle Capability e costruisce un grafo semantico del portfolio (come nello screenshot: 141 nodi, 195 archi, 14 community).

Dopo il run:
```powershell
# Se graphify-out/ e' gia' dentro docs/ (run successivi al primo):
# niente da spostare, aggiorna solo graph.html

# Primo run assoluto - sposta nella posizione corretta:
# Move-Item graphify-out docs\graphify-out

# Aggiorna .gitignore se non gia' fatto:
# docs/graphify-out/.graphify_*
# docs/graphify-out/converted/
# docs/graphify-out/*.json

git add docs\graphify-out\graph.html
git add docs\graphify-out\GRAPH_REPORT.md
git commit -m "Update Skills Knowledge Graph"
git push
```

**Risultato**: `alesop95.github.io/skills/graphify-out/graph.html` mostra il grafo interattivo. I god nodes (Capability con piu' connessioni) riflettono le aree di maggiore trasversalita' del tuo profilo.

**Nota**: consuma token (graphify legge tutti i .md di docs/). Stimato: ~30 file .md * 1.500 token = ~45k token per run.

---

## Riepilogo: quando usare cosa

| Situazione | Caso | Token |
|------------|------|-------|
| Primo setup del sistema | Caso 1 | Alti (corpus intero) |
| Nuovo progetto finito oggi | Caso 3 | Bassi (3-10 file) |
| Refresh mensile | Caso 2 | Bassi (solo file modificati) |
| Piu' sorgenti insieme | Caso 4 | Medi (per sorgente) |
| Esplorare la documentazione in locale | Caso 5 | Zero |
| Aggiungere sintesi narrative al vault | Caso 6 | Medi |
| Nuova area di competenza da aggiungere | Caso 7 | Zero |
| Aggiornare il Knowledge Graph portfolio | Caso 8 | Bassi (~45k) |
