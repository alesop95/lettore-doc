---
generated-from-commit: 979d674
generated-from-branch: main
generated-date: 2026-06-17
covers-paths:
  - scripts/export_to_taxonomy.py
  - scripts/generate_taxonomy_index.py
last-verified-commit: 382f99e
source-doc: GUIDA-TECNICA.md
---

# Deployment

Il vault Obsidian privato e locale, senza deploy. Il sito pubblico della tassonomia e un MkDocs servito su GitHub Pages: `git push` su `main` del repo pubblico avvia `mkdocs build --strict` (fallisce sui link rotti, safety net voluto) e il deploy delle Pages. L'iniezione delle evidenze nelle pagine Capability avviene via `export_to_taxonomy.py`, sempre `--dry-run` prima di `--apply`, con idempotenza tramite ID SHA256 in commenti HTML; le quattro H2 fisse delle pagine sono invariate per contratto. Fra `map_to_taxonomy.py` e `export_to_taxonomy.py` gira ora `sanitize_taxonomy_diff.py` che produce `taxonomy_diff.sanitized.json`: e' quest'ultimo che viene passato a `--dry-run`/`--apply`, non il diff grezzo. Le new-capability suggerite ma non evidentemente skill-generali (titoli tipo "nome hostname + IP") si scartano cancellando i due `.md` prima del commit, per non impilarle sotto Infrastructure senza semantica.

L'export ha ora tre modalita' oltre all'iniezione. `--refresh` riscrive un blocco di evidenza gia' pubblicato, che l'idempotenza per ID altrimenti protegge rendendo impossibile correggerlo. `--prune-moved` e `--prune-unexpected` lo rimuovono, e chiudono il caso che l'idempotenza da sola produce: siccome l'ID stabile e' l'hash del nodo piu' lo slug della Capability, una riclassificazione che sposta un nodo genera un ID nuovo, il blocco nuovo viene iniettato sulla pagina giusta e quello vecchio resta orfano sulla pagina vecchia, cioe' evidenza duplicata. La ricerca dei collocamenti obsoleti gira comunque a ogni esecuzione, anche in dry-run e senza flag, ed e' descritta in `dev-testing.md` fra i controlli. Il vincolo di sicurezza dell'implementazione e' che un collocamento si dichiara obsoleto solo per un nodo che il diff corrente conosce, perche' l'assenza di un nodo dal diff non e' un giudizio ma ignoranza: e' cosi' che si evita di cancellare le evidenze dei cicli precedenti, i cui nodi vengono da un altro corpus. Una pagina svuotata da una rimozione torna al testo segnaposto iniziale, quindi resta conforme al contratto delle quattro H2.

Dettaglio in `GUIDA-TECNICA.md` sezioni 5-6.
