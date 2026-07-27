# Snapshot

Branch: `main`. Commit di riferimento: `397c0a8`.

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

Prossima azione: **aggiornare il diario tecnico**, unico pezzo rimasto. Il draft delle sezioni C.9-C.12 e' pronto in scratchpad (`draft-diario-C9-C12.md`) e copre il debito accumulato dal 2026-05-28; i tre passi manuali sono `.\scripts\open_diary.ps1`, editing in Word in coda all'Appendice C, poi `.\scripts\finalize_diary.ps1` e commit con prefisso `Diario:`. Se lo scratchpad di sessione viene ripulito prima, il draft va rigenerato dal work-log del 2026-07-27, che ne contiene tutti i fatti.

Modalita' corrente: manutenzione. Residui aperti non urgenti in `roadmap.md`: ereditarieta' dei token di community in `classify_nodes`, e `Soft Skills` a zero keyword. Popolare `current-work.md` se si apre una nuova feature.
