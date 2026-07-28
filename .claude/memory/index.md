# Snapshot

Branch: `main`. Commit di riferimento: `21e11b3`.

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

Chiuso il 2026-07-28 il ciclo Cybersec endpoint governance (skills-repo `5ca2dd6`, 28 evidenze su 2 Capability). Il fix del routing e' confermato sul campo: zero evidenze a `Quality Certification`, 5 correzioni manuali su 28 contro 18 su 34 del ciclo precedente. Il ciclo ha pero' scoperto e chiuso una fuga reale di ragione sociale e hostname attraverso i nomi dei file, dettagli nel work-log.

Prossima azione: **nessun debito aperto**. Per un nuovo ciclo partire da `.\scripts\session_resume.ps1`; la sequenza comincia dal passo 0 di pre-flight (`prepare_graphify_source.py`). Candidate mai ingerite, per dimensione: `Helpdesk_T-Rex` (41 doc), `_DA SISTEMARE (Alessio)` (44), `Helpdesk_RWS-Groupshare-Studio` (17, gia' proposta in C.8), un blocco coeso dei piccoli `Helpdesk_*` (NinjaOne, Microsoft 365, Onboarding, Amministrazione, INFOCERT, ABBYY, Timbracartellini, circa 35 in totale), `TOOL AI coding assistance` (9). Le grandi (`ENIVIPA` 2500, `SCENIA` 918, `OpenAI` 267) restano da affrontare con una segmentazione per coesione semantica, non in blocco.

Due note operative. Nel segmento `Cybersec & IT Governance` restano non lavorate le subfolder `Privacy (GDPR e Contratti)` (33), `_VA e Pentest assessment` (12, con report di rischio da escludere), `_QUESTIONARI FORNITORI` (126, dati di terzi, da escludere), e i dieci documenti non processati di `_ GDPR E ISO27001`. Il digest continuera' inoltre a segnalare 996 file nuovi su `Miscellaneous procedure e utilities`, tutti scraping di brochure di fondi di terzi sotto `Web scraping - Downloaded Web sites`: non e' materiale da ingerire, e la cartella andrebbe aggiunta a `EXCLUDE_DIR_NAMES` in `ingest_state.py`, dove stanno gia' `_archive` e `templates`.

Modalita' corrente: manutenzione. Residui aperti non urgenti in `roadmap.md`: ereditarieta' dei token di community in `classify_nodes`, e `Soft Skills` a zero keyword. Popolare `current-work.md` se si apre una nuova feature.
