# Snapshot

Branch: `main`. Commit di riferimento: `aa801fa`.

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

Chiuse il 2026-07-29 le prime quattro voci della coda di lavoro del `RESUME_PROMPT.md`, dettagli nel work-log. In sintesi: `export_to_taxonomy.py` sa ora rimuovere un'evidenza pubblicata e non solo riscriverla, che era il prerequisito dichiarato di qualsiasi riclassificazione retroattiva, ed e' quindi ora valutabile un cambio della funzione di punteggio applicato allo storico; il gate ha la regola `residue-domain-third-party`, ultimo punto aperto di riservatezza; `ingest_state.py` esclude l'archivio di scraping e ha il comando `resnapshot` per assorbire un cambio di esclusioni senza falsificare la data di ingest; la pagina `soft/index.md` e' a contratto (skills-repo `cfeada5`) e la Capability `Soft Skills` non e' piu' a zero keyword. La scoperta di metodo, ora regola in `dev-testing.md`, e' che il diff sintetico dice se una regola scatta ma non cosa scarterebbe di buono: ogni modifica al gate o alla classificazione va rilanciata sui due corpora storici e confrontata per ID di nodo.

Il 2026-08-03, aprendo il ciclo su `Helpdesk_RWS-Groupshare-Studio`, un audit del repository pubblico ha trovato **quattro password in chiaro pubblicate** nei preview delle evidenze, presenti in tutti i 22 commit e servite anche da `raw.githubusercontent.com`. Il gate non aveva nessuna categoria per i segreti. Chiusi in giornata cinque strati nuovi (segreti che scartano, dichiarazione dei nodi scartati dal gate, neutralizzazione Markdown piu' riparazione struttura, nomi propri parziali, `verify_public_repo.py` con hook di pre-commit), bonifica integrale via pipeline da 17 riscontri a 0, e repository pubblico **cancellato e ricreato** perche' il push forzato non cancella gli oggetti. Sito ripubblicato e verificato pulito. Racconto in C.16, dettagli nel work-log.

Le quattro credenziali sono state esaminate una per una il 2026-08-04 e **la rotazione non e' servita**: due riguardavano risorse dismesse (una macchina virtuale non piu' esistente e un file di backup credenziali cancellato), una l'account di una persona non piu' dipendente, una la console di un antivirus non piu' in uso. Cio' che contava era l'anonimizzazione, verificata su quattro scope, cioe' file tracciati, ogni blob della storia, sito servito nelle tre lingue e grafo HTML pubblicato, con zero occorrenze cercando esplicitamente nomi, utenze e valori.

Chiuso il 2026-08-04 il **ciclo Helpdesk RWS GroupShare Studio**: skills-repo `befbee0`, 38 evidenze su 9 Capability, ID pubblicati da 246 a 284, `ingest_state` registrato, deploy verde, quattro controlli post-apply passati. Diario C.17.

Chiusa la voce **tassonomia in tre lingue** lato meccanismo: sito trilingue con plugin i18n a suffisso e ripiego, inglese di default, export che scrive in tutte le varianti con ID sullo slug base. Restano da tradurre 30 pagine di Capability piu' quella delle competenze trasversali: lavoro di contenuto, per domini, una sessione per blocco.

Prossima azione: **nessun debito aperto**. Per un nuovo ciclo partire da `.\scripts\session_resume.ps1`. Partire da `.\scripts\session_resume.ps1`; la sequenza comincia dal passo 0 di pre-flight (`prepare_graphify_source.py`). Candidate mai ingerite, per dimensione: `Helpdesk_T-Rex` (41 doc), `_DA SISTEMARE (Alessio)` (44), `Helpdesk_RWS-Groupshare-Studio` (17, gia' proposta in C.8), un blocco coeso dei piccoli `Helpdesk_*` (NinjaOne, Microsoft 365, Onboarding, Amministrazione, INFOCERT, ABBYY, Timbracartellini, circa 35 in totale), `TOOL AI coding assistance` (9). Le grandi (`ENIVIPA` 2500, `SCENIA` 918, `OpenAI` 267) restano da affrontare con una segmentazione per coesione semantica, non in blocco.

Due note operative. Nel segmento `Cybersec & IT Governance` restano non lavorate le subfolder `Privacy (GDPR e Contratti)` (33), `_VA e Pentest assessment` (12, con report di rischio da escludere), `_QUESTIONARI FORNITORI` (126, dati di terzi, da escludere), e i dieci documenti non processati di `_ GDPR E ISO27001`. I 996 file che il digest segnalava come nuovi su `Miscellaneous procedure e utilities`, tutti scraping di brochure di fondi di terzi, non compaiono piu': la cartella e' in `EXCLUDE_DIR_NAMES` e lo snapshot e' stato riallineato con `resnapshot`.

Modalita' corrente: manutenzione. Residui aperti non urgenti in `roadmap.md`: ereditarieta' dei token di community in `classify_nodes`, avviso esplicito per una Capability a zero keyword (oggi lo zero passa silenzioso), e la voce di fondo sugli embeddings, che ora ha il suo prerequisito soddisfatto. Popolare `current-work.md` se si apre una nuova feature.
