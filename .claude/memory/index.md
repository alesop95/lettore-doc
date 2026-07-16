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

Chiuso il 2026-07-16 il ciclo Cybersec governance baseline (skills-repo `5f2af1c`, 30 iniezioni su 5 Capability, tre subfolder OneDrive tracciate: Access Authentication, Procedura Data Breach, Regolamento utilizzo). Il ciclo ha portato due scoperte da riflettere in pipeline: (a) filtro `_SENSITIVE_PATTERNS` di graphify 0.8.14 che skippa silenziosamente file con `password`/`secret`/`credential`/`token` nel nome, workaround corrente = rename manuale in cartella `-sanitized/` parallela; (b) `map_to_taxonomy` instrada evidenze GDPR/Data Breach a `Quality Certification` invece di `Cybersecurity & IT Governance` per una keyword `certification` troppo generica. Prossimi passi operativi (opzionali): aggiornare il diario tecnico documentando entrambe, e valutare se le due scoperte richiedono un edit alle schede `design-and-security.md` o `dev-testing.md`. Modalita' corrente: manutenzione + estensione pipeline. Al prossimo cambiamento di codice o configurazione, rilanciare `sync-context` e bumpare. Popolare `current-work.md` se si apre una nuova feature; le candidate sono in `roadmap.md`.
