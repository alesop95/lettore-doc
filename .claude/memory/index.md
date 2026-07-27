# Snapshot

Branch: `main`. Commit di riferimento: `6f3c2b8`.

## Stato delle schede

| Scheda | Stato |
|---|---|
| context/STACK.md | aggiornata |
| context/design-and-security.md | aggiornata |
| context/deployment.md | aggiornata |
| context/dev-testing.md | aggiornata |
| context/current-work.md | aggiornata |
| context/roadmap.md | aggiornata |

## Prossima azione concreta

Chiuse il 2026-07-27 entrambe le scoperte lasciate aperte dal ciclo Cybersec governance baseline. Il filtro sui nomi file di graphify ha ora un passo di pre-flight dedicato, `scripts/prepare_graphify_source.py`, da eseguire su ogni subfolder prima di lanciare graphify (passo 0 della sequenza in `CLAUDE.md`). Il misrouting delle evidenze GDPR e' risolto alla radice: la diagnosi originale (keyword `certification` troppo generica) era sbagliata ed e' rettificata nel work-log; le cause reali erano il troncamento a senso unico delle keyword in `generate_taxonomy_index.py` e il fatto che `Quality Certification` rivendicasse il data breach nel proprio Overview. Perimetro GDPR spostato su `Cybersecurity & IT Governance` nelle pagine pubbliche (skills-repo `88f4b8f`), con l'automatismo che ora riproduce da solo la correzione manuale di diciotto fit.

Chiuso anche il debito del diario, che aveva due mesi di ritardo: le sezioni C.9-C.12 sono dentro, inserite da `append_diary_section.py`, che automatizza il caso normale (nuove sezioni in coda) e riduce l'intervento manuale in Word a tabelle, immagini e modifiche a contenuto esistente.

Prossima azione: **nessun debito aperto, si puo' aprire un nuovo ciclo di ingest**. Partire da `.\scripts\session_resume.ps1` per il digest delle subfolder con delta o mai ingerite, e ricordare che la sequenza ora comincia dal passo 0 di pre-flight (`prepare_graphify_source.py`) prima di lanciare graphify. Il prossimo ciclo e' anche la prima verifica sul campo delle correzioni di oggi: se il routing regge senza correzioni manuali del `taxonomy_diff`, il fix e' confermato.

Modalita' corrente: manutenzione. Residui aperti non urgenti in `roadmap.md`: ereditarieta' dei token di community in `classify_nodes`, e `Soft Skills` a zero keyword. Popolare `current-work.md` se si apre una nuova feature.
