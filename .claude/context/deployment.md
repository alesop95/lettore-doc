---
generated-from-commit: 979d674
generated-from-branch: main
generated-date: 2026-06-17
covers-paths:
  - scripts/export_to_taxonomy.py
  - scripts/generate_taxonomy_index.py
last-verified-commit: aa801fa
source-doc: GUIDA-TECNICA.md
---

# Deployment

Il vault Obsidian privato e locale, senza deploy. Il sito pubblico della tassonomia e un MkDocs servito su GitHub Pages: `git push` su `main` del repo pubblico avvia `mkdocs build --strict` (fallisce sui link rotti, safety net voluto) e il deploy delle Pages. L'iniezione delle evidenze nelle pagine Capability avviene via `export_to_taxonomy.py`, sempre `--dry-run` prima di `--apply`, con idempotenza tramite ID SHA256 in commenti HTML; le quattro H2 fisse delle pagine sono invariate per contratto. Fra `map_to_taxonomy.py` e `export_to_taxonomy.py` gira ora `sanitize_taxonomy_diff.py` che produce `taxonomy_diff.sanitized.json`: e' quest'ultimo che viene passato a `--dry-run`/`--apply`, non il diff grezzo. Le new-capability suggerite ma non evidentemente skill-generali (titoli tipo "nome hostname + IP") si scartano cancellando i due `.md` prima del commit, per non impilarle sotto Infrastructure senza semantica.

L'export ha ora tre modalita' oltre all'iniezione. `--refresh` riscrive un blocco di evidenza gia' pubblicato, che l'idempotenza per ID altrimenti protegge rendendo impossibile correggerlo. `--prune-moved` e `--prune-unexpected` lo rimuovono, e chiudono il caso che l'idempotenza da sola produce: siccome l'ID stabile e' l'hash del nodo piu' lo slug della Capability, una riclassificazione che sposta un nodo genera un ID nuovo, il blocco nuovo viene iniettato sulla pagina giusta e quello vecchio resta orfano sulla pagina vecchia, cioe' evidenza duplicata. La ricerca dei collocamenti obsoleti gira comunque a ogni esecuzione, anche in dry-run e senza flag, ed e' descritta in `dev-testing.md` fra i controlli. Il vincolo di sicurezza dell'implementazione e' che un collocamento si dichiara obsoleto solo per un nodo che il diff corrente conosce, perche' l'assenza di un nodo dal diff non e' un giudizio ma ignoranza: e' cosi' che si evita di cancellare le evidenze dei cicli precedenti, i cui nodi vengono da un altro corpus. Una pagina svuotata da una rimozione torna al testo segnaposto iniziale, quindi resta conforme al contratto delle quattro H2.

Dal 2026-08-03 esiste anche `--repair-structure`, che ripulisce la sezione delle evidenze dalle intestazioni spurie prodotte da un preview appiattito, ed e' la sola via prevista per pagine in quello stato, dato che l'intervento a mano su quelle sezioni e' vietato.

Il repository pubblico e' stato **cancellato e ricreato** il 2026-08-03 per eliminare gli oggetti dei commit vecchi, che un push forzato non rimuove: cinque di essi rispondevano ancora `200` sull'API dopo la riscrittura della storia, e `raw.githubusercontent.com` serviva ancora il contenuto. La cancellazione porta via anche gli artifact e i log delle esecuzioni passate, dove il sito costruito conteneva le stesse pagine. Storia attuale: un solo commit iniziale.

Due conseguenze operative della ricreazione. Le Pages vanno abilitate **a mano** una volta, in Settings, Pages, Source GitHub Actions: provato ad automatizzarlo con `actions/configure-pages` e `enablement: true`, il passo fallisce perche' il token del workflow non ha i diritti per abilitare Pages dove non e' mai stato attivo, quindi il workflow e' tornato ai cinque passi originali. E `mkdocs.yml` ha ora `site_url`, che mancava e serve al sitemap e ai link canonici. Le annotazioni del workflow segnalano che Node.js 20 e' deprecato sui runner: `checkout@v4`, `setup-python@v5`, `upload-artifact@v4` e `deploy-pages@v4` andranno portati alle versioni su Node 24 prima che il deploy si fermi da solo.

Nessun commit sul repository pubblico senza che `scripts/verify_public_repo.py` sia uscito pulito; l'hook di pre-commit lo rende non aggirabile per distrazione.

Dettaglio in `GUIDA-TECNICA.md` sezioni 5-6.
