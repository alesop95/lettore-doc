# lettore-doc - Claude Code instructions

Sei nella cartella **privata** `E:\lettore-doc`. Questo repo non va mai online.
Il repo pubblico è in `$env:LETTERDOC_SKILLS_REPO` (GitHub: alesop95/skills).

---

## Variabili di ambiente richieste

| Variabile | Descrizione |
|-----------|-------------|
| `LETTERDOC_SKILLS_REPO` | Path al working tree di skills-repo |
| `LETTERDOC_SOURCE_ONEDRIVE` | Cartella OneDrive principale |
| `LETTERDOC_SOURCE_PORTFOLIO` | Cartella Google Drive Portfolio |

Verifica che siano settate:
```powershell
$env:LETTERDOC_SKILLS_REPO
$env:LETTERDOC_SOURCE_ONEDRIVE
$env:LETTERDOC_SOURCE_PORTFOLIO
```

Se vuote, settale (persistenti per l'utente):
```powershell
[System.Environment]::SetEnvironmentVariable("LETTERDOC_SKILLS_REPO", "J:\...\skills-repo", "User")
[System.Environment]::SetEnvironmentVariable("LETTERDOC_SOURCE_ONEDRIVE", "C:\...\Documenti-IT", "User")
[System.Environment]::SetEnvironmentVariable("LETTERDOC_SOURCE_PORTFOLIO", "J:\...\IT-RELATED", "User")
```

---

## Regole fondamentali

- **Non aprire mai un `.docx` direttamente con Read**: carica XML grezzo inutile.
  Usa sempre gli script Python o graphify.
- **Non scrivere mai in skills-repo direttamente**: usa solo `export_to_taxonomy.py --apply`.
- **Non lanciare graphify su questa cartella**: graphify va lanciato sulla cartella
  sorgente (es. `$env:LETTERDOC_SOURCE_ONEDRIVE`), non qui.
- Usa sempre `.\.venv\Scripts\python.exe scripts\<script>.py`.
- I file in `_intermediate\` sono rigenerabili: sovrascrivili liberamente.
- I file in `vault-output\` sono il vault privato: non toccarli senza motivo.

---

## Python e dipendenze

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\<script>.py [args]
```

---

## Pipeline di estrazione skill (ordine corretto)

```powershell
# 1. taxonomy index - legge skills_repo da sources.yml automaticamente
.\.venv\Scripts\python.exe scripts\generate_taxonomy_index.py `
  --output _intermediate\taxonomy_index.json

# 2. enrich graph
.\.venv\Scripts\python.exe scripts\enrich_graph.py `
  --graph   "<cartella-sorgente>\graphify-out\graph.json" `
  --workdir "<cartella-sorgente>" `
  --output  _intermediate\enriched_graph.json

# 3. map to taxonomy
.\.venv\Scripts\python.exe scripts\map_to_taxonomy.py `
  --enriched-graph _intermediate\enriched_graph.json `
  --taxonomy       _intermediate\taxonomy_index.json `
  --output-md      _intermediate\taxonomy_diff.md `
  --output-json    _intermediate\taxonomy_diff.json

# 4. export (sempre dry-run prima)
.\.venv\Scripts\python.exe scripts\export_to_taxonomy.py `
  --diff-json   _intermediate\taxonomy_diff.json `
  --skills-repo "$env:LETTERDOC_SKILLS_REPO" `
  [--dry-run | --apply]
```

---

## Pipeline vault Obsidian privato

```powershell
.\run_pipeline.ps1 -SourceFolder "$env:LETTERDOC_SOURCE_ONEDRIVE"
.\run_pipeline.ps1 -SourceFolder "$env:LETTERDOC_SOURCE_ONEDRIVE" -Incremental
.\run_pipeline.ps1 -SourceFolder "$env:LETTERDOC_SOURCE_ONEDRIVE" -OnlyVault
```

---

## File intermedi chiave

| File | Prodotto da | Consumato da |
|------|-------------|--------------|
| `_intermediate\structure.json` | `parse_docx.py skeleton` | `extract_entities.py`, `generate_vault.py` |
| `_intermediate\entities.json` | `extract_entities.py` | `build_knowledge_graph.py` |
| `_intermediate\graph.json` | `build_knowledge_graph.py` | `generate_vault.py` |
| `_intermediate\enriched_graph.json` | `enrich_graph.py` | `map_to_taxonomy.py` |
| `_intermediate\taxonomy_index.json` | `generate_taxonomy_index.py` | `map_to_taxonomy.py` |
| `_intermediate\taxonomy_diff.md/.json` | `map_to_taxonomy.py` | `export_to_taxonomy.py` |

---

## Subagente disponibile

`.claude\agents\lettore-documentazione.md` - specializzato per documentazione
aziendale italiana. Invocalo con:
```
Usa il subagente lettore-documentazione per [task].
```

---

## Cosa NON è in questo repo (gitignored)

- `.venv\` - ricrea con `setup.ps1`
- `_intermediate\` - rigenera dalla pipeline
- `vault-output\` - rigenera con `run_pipeline.ps1 -OnlyVault`
- `.env` - i tuoi valori locali delle variabili (mai committare)
