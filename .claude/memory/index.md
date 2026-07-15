# Snapshot

Branch: `main`. Commit di riferimento: `233c39c`.

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

Schede bumpate a `233c39c` (checkpoint dopo commit di `.graphifyignore` + regola di allineamento con `.gitignore`). Edit chirurgico su `design-and-security.md` (sezione "Separazione dei piani dati") per menzionare il confine graphify; `.graphifyignore` aggiunto ai `covers-paths` della stessa scheda cosi' il prossimo drift viene intercettato direttamente. Modalita' corrente: manutenzione. Al prossimo cambiamento di codice o configurazione, rilanciare `sync-context` e bumpare. Popolare `current-work.md` all'apertura della prossima feature; le candidate sono in `roadmap.md`.
