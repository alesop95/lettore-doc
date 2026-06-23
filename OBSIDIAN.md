# Obsidian — lettore-doc

Questo file documenta come aprire e usare il vault Obsidian generato dalla pipeline
di `lettore-doc`. Va letto insieme a `CLAUDE.md` e `GUIDA-TECNICA.md`.

---

## Cos'e' il vault

`vault-output/` e' lo spazio di lavoro interno della pipeline: ogni volta che
`run_pipeline.ps1` viene lanciato su uno o piu' source, il generatore di vault
(`scripts/generate_vault.py`) scrive qui le note estratte dai documenti, le
sintesi narrative, i wiki-link automatici e il grafo delle relazioni tra entita'.

Non e' un vault da replicare altrove. La cartella `.obsidian/` che Obsidian crea
al primo open resta intatta tra un run e l'altro perche' `generate_vault.py` scrive
solo i file di contenuto, mai la configurazione Obsidian.

Tutti i source configurati in `sources.yml` (OneDrive, Portfolio, qualsiasi altro)
confluiscono nella stessa `vault-output/` in modalita' incrementale: solo i
documenti con hash diverso dalla run precedente vengono rielaborati.

---

## Aprire il vault

File -> Open folder as vault -> `E:\lettore-doc\vault-output\`

Se la cartella e' vuota (pipeline mai lanciata), prima eseguire:

```powershell
.\run_pipeline.ps1 -SourceFolder $env:LETTERDOC_SOURCE_ONEDRIVE
```

---

## Plugin necessari

Tre plugin da abilitare in Settings -> Community plugins dopo il primo open.

*BRAT* (Beta Reviewer's Auto-update Tool, autore TFT hacker): gestore di plugin
beta da GitHub. Va abilitato per primo perche' installa e aggiorna gli altri due.

*3D Graph* (installato via BRAT da `Apoo711/obsidian-3d-graph`): visualizzazione
tridimensionale force-directed del grafo delle note. Utile per navigare le relazioni
tra documenti e entita' estratte. Si apre dall'icona nella barra laterale sinistra
o con Ctrl+P -> Open 3D Graph. Limitare il numero massimo di nodi resi a 1000 se
il vault cresce molto (impostazione nel pannello del plugin).

*Embed HTML* (autore mnaoumov): apre i file `.html` come tab nativi di Obsidian
invece di forzare la sintassi `![[...]]`. Utile se la pipeline producesse HTML
interattivi nel vault (ad esempio un graph.html locale generato da graphify su
`vault-output/`).

---

## Cosa si vede nel vault

Ogni documento sorgente produce una nota Markdown con il titolo del documento,
le sezioni estratte, le entita' rilevate (aziende, tecnologie, persone, riferimenti
normativi), i wiki-link verso le entita' condivise con altri documenti, e una
sintesi narrativa quando disponibile.

La cartella `_data/` contiene i file strutturati intermedi (JSON) usati dalla
pipeline e non e' destinata alla lettura diretta in Obsidian.

Il grafo nativo di Obsidian (Ctrl+G o Ctrl+Shift+G per il grafo globale) mostra
le connessioni tra le note via wiki-link. Il plugin 3D Graph aggiunge una vista
piu' immersiva dello stesso grafo.

---

## Flusso completo

```
source (OneDrive / Portfolio / altri)
    |
    v
run_pipeline.ps1
    |
    +---> _intermediate/  (structure.json, entities.json, graph.json)
    |
    +---> vault-output/   <-- questo vault
              |
              v
         [opzionale] /graphify su vault-output/ per grafo semantico locale
              |
              v
         enrich_graph.py + map_to_taxonomy.py + export_to_taxonomy.py
              |
              v
         E:\skills  (repo pubblico alesop95/skills -> alesop95.github.io/skills/)
```

---

## Aggiornare il vault dopo nuovi documenti

```powershell
# Modalita' incrementale: rielabora solo i documenti modificati
.\run_pipeline.ps1 -SourceFolder $env:LETTERDOC_SOURCE_ONEDRIVE -Incremental
.\run_pipeline.ps1 -SourceFolder $env:LETTERDOC_SOURCE_PORTFOLIO -Incremental
```

Obsidian aggiorna automaticamente le note aperte non appena i file cambiano su
disco, senza bisogno di riavviare il vault.
