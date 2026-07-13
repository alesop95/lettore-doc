# Work-log

> Append-only, ordine cronologico inverso.

## 2026-07-13 — Bump schede a `cb35334`

Sync-context da `ab89133` a `cb35334`. Nessun drift sui `covers-paths`: i due commit intermedi (`32a5920` aggiornamento templates, `cb35334` aggiunta skill `studio-didattico`) toccano solo `.claude/templates/**` e `.claude/skills/**`, aree non coperte da nessuna scheda. Bump di checkpoint su tutte e sei le schede senza edit di contenuto, per mantenere il prossimo confronto pulito.

## 2026-06-25 — Riconciliazione schede a `ab89133`

Sync-context da `979d674` a `ab89133`. Drift su quattro aree: `requirements.txt` (+`spacy>=3.7.0`, +`click>=8.0.0`), `.gitignore` (+`_notes/` per screenshot effimeri), `scripts/extract_entities.py` (NER `PROPER_NOUN` migrato a spaCy `it_core_news_lg` label `PER`, con fallback regex+stoplist). Edit chirurgico su `STACK.md` sezione "Deterministico prima del linguistico" per posizionare correttamente spaCy come modello statistico locale a zero token LLM, non come lavoro linguistico LLM. Le altre cinque schede ricevono solo bump a checkpoint: cambi marginali (`_notes/` in design/security; download spaCy gia' assorbito da setup; tuning permanente coerente con manutenzione corrente; nessun impatto su deployment e roadmap).

## 2026-06-17 — Adozione dello standard di progetto

Adottato il sistema portabile di contesto e documentazione: motore di riconciliazione, regole (`token-economy`, `interaction-style`, `git-identity-and-repo`, `manual-screenshots`), skill engine piu `onboard`, e catalogo pacchetti. Create le schede `context/` con frontmatter ancorato a `979d674`, riconciliate con `GUIDA-TECNICA.md` senza duplicarla, e la memoria iniziale. Attivati `code-context` (MCP, per mappare gli script Python) e `caveman` (uso selettivo, solo sessioni operative). `knowledge-wiki` non adottata: il progetto ha gia una knowledge base nativa (vault Obsidian piu graphify). Segreti verificati: `.env` mai committato. Skill custom `grafo-conoscenza`/`parsing-docx` e agent `lettore-documentazione` preservati.
