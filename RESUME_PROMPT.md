# RESUME_PROMPT

> Documento di passaggio riscritto il 2026-08-04 alla chiusura della sessione. Sostituisce integralmente la versione del 2026-07-29, la cui coda di lavoro e' stata chiusa.
>
> Lo stato canonico e sintetico resta `.claude/memory/index.md`, il work-log dettagliato `.claude/memory/progress.md`, e il racconto delle decisioni il diario, sezioni C.16 e C.17 per questa sessione. Questo file aggiunge cio' che quei tre non contengono: le trappole verificate sulla macchina e il perche' di alcune scelte che a rileggerle sembrano arbitrarie.

---

## Come ripartire

Aprire Claude Code nella root del progetto e seguire la procedura ordinaria: leggere `.claude/memory/index.md`, poi `.claude/context/current-work.md`, poi invocare la skill `sync-context`. Per orientarsi sull'insieme dei flussi c'e' `STATO-DEL-PROGETTO.md`, che e' la fotografia da leggere quando si e' perso il filo. Per un nuovo ciclo di ingest, il digest e' `.\scripts\session_resume.ps1`.

---

## Stato alla consegna

| Cosa | Valore |
|---|---|
| `lettore-doc` | ultimo commit di diario e schede, schede a `fee90a6` |
| `skills-repo` | `befbee0`, storia di un solo commit dopo la ricreazione |
| Evidenze pubblicate | 284 ID su 9+ pagine Capability |
| Ultimo ciclo di ingest | Helpdesk RWS GroupShare Studio, chiuso |
| Sito pubblico | trilingue, inglese in radice, `/it/` e `/es/` |
| Diario | in pari, ultima sezione C.17 |
| Debito aperto | nessuno |

---

## Cosa e' successo in questa sessione, in breve

Un normale ciclo di ingest si e' trasformato nella gestione di un incidente: l'audit del repository pubblico ha trovato **quattro password in chiaro pubblicate** nei preview delle evidenze, presenti in tutti i ventidue commit e servite anche da `raw.githubusercontent.com`. Il gate non aveva nessuna categoria per i segreti. Racconto completo in C.16.

Sono stati aggiunti cinque strati di difesa, l'albero di lavoro e' stato bonificato interamente dalla pipeline, e il repository pubblico e' stato cancellato e ricreato. Le quattro credenziali sono poi state esaminate una per una con l'utente: **nessuna rotazione e' stata necessaria**, perche' riguardavano risorse dismesse, una persona non piu' in azienda e un prodotto non piu' in uso. Cio' che contava era l'anonimizzazione, verificata su quattro scope con esito zero. Questa conclusione e' scritta anche nel work-log, perche' senza di essa una sessione futura riaprirebbe il caso.

Nella stessa sessione il ciclo di ingest e' stato chiuso (38 evidenze su 9 Capability) e il sito e' diventato trilingue. Dettagli in C.17.

---

## Le regole nuove, che valgono da adesso

**Nessun commit sul repository pubblico senza che `verify_public_repo.py` sia uscito pulito.** L'hook di `pre-commit` lo rende non aggirabile per distrazione, e si reinstalla con `scripts\install_hooks.ps1` dopo ogni clonazione, perche' la cartella degli hook non e' versionata da nessun repository.

**Una modifica al gate o alla classificazione va misurata su tutti i corpora disponibili, non su un campione.** Costa poco, perche' i corpora sono su disco sotto `_intermediate/src/` e gli stati intermedi sono file JSON. Il confronto si fa sulle destinazioni per ID di nodo, non sui totali, perche' due errori che si compensano tengono il totale fermo. Questa regola nasce da un errore reale: una misura su due corpora su quattro aveva dichiarato innocua una modifica che sugli altri due rubava evidenze.

**Un verificatore che segnala sempre qualcosa insegna a ignorarlo.** Ogni falso positivo va tolto con la stessa cura dedicata ai veri positivi.

---

## Coda di lavoro, in ordine

**1. Traduzione delle pagine Capability.** Il meccanismo trilingue e' completo e provato; restano trenta pagine di Capability piu' quella delle competenze trasversali. E' lavoro di contenuto e conviene procedere per domini, un blocco per sessione, cominciando da Infrastructure e Security. Il ripiego del plugin fa restare visibili in inglese le pagine non ancora tradotte, quindi non c'e' fretta e non ci sono buchi. Non creare file di traduzione vuoti: il ripiego mostra la pagina di default, evidenze comprese.

**2. Action di GitHub su Node 24.** Le annotazioni del workflow segnalano che Node.js 20 e' deprecato sui runner: `checkout@v4`, `setup-python@v5`, `upload-artifact@v4` e `deploy-pages@v4` vanno aggiornati prima che il deploy si fermi da solo.

**3. Prossimo ciclo di ingest.** Partire da `session_resume.ps1`. Candidate mai ingerite: `Helpdesk_T-Rex` (41 doc), `_DA SISTEMARE (Alessio)` (44), un blocco dei piccoli `Helpdesk_*` (circa 35 in totale), `TOOL AI coding assistance` (9). Le grandi (`ENIVIPA` 2500, `SCENIA` 918, `OpenAI` 267) vanno segmentate per coesione semantica. Nel segmento Cybersec restano `Privacy (GDPR e Contratti)` (33), `_VA e Pentest assessment` (12, con report di rischio da escludere), `_QUESTIONARI FORNITORI` (126, dati di terzi, da escludere) e dieci documenti di `_ GDPR E ISO27001`.

**4. Voci minori in `roadmap.md`.** Avviso esplicito per una Capability a zero parole chiave, distinguendo il caso dichiarato in `MANUAL_ONLY_FILES` da quello accidentale. Ereditarieta' dei token di community in `classify_nodes`. Embeddings al posto del punteggio lessicale, che ora ha il suo prerequisito soddisfatto perche' esiste la via di rimozione.

---

## Trappole verificate su questa macchina

**Un push forzato sposta un riferimento, non cancella oggetti.** Dopo la riscrittura della storia, cinque vecchi commit rispondevano ancora `200` sull'API pubblica e `raw.githubusercontent.com` serviva ancora il contenuto. Con zero fork la via completa e' cancellare e ricreare il repository, che elimina gli oggetti e porta via anche artifact e log delle esecuzioni.

**Ogni verifica va accompagnata da un controllo di validita'.** Un primo test dichiarava i vecchi commit irraggiungibili, ma dava lo stesso esito su un commit che esisteva: non misurava niente. Su quell'endpoint `422` significa SHA assente e `200` presente, quindi il controllo e' verificare che il commit attuale risponda `200`.

**`git commit --dry-run` non esegue gli hook**, quindi non serve a provarli. Si esegue l'hook a mano con il contenuto in stage.

**Le Pages non si abilitano dal workflow.** `actions/configure-pages` con `enablement: true` fallisce perche' il token non ha quei diritti dove Pages non e' mai stato attivo. L'abilitazione e' manuale una volta sola, in Settings, Pages, Source GitHub Actions.

**Uno strumento che ripulisce non ha il diritto di presumere.** La prima stesura della riparazione strutturale trattava come corruzione ogni blocco senza ancora e cancello' contenuto scritto a mano. Si rimuove solo cio' che porta la firma dimostrabile del difetto.

**Comandi git su riga singola**, e con il `cd` esplicito: due errori di questa sessione, uno con un `git add` andato a capo in PowerShell e uno con un comando lanciato nella cartella sbagliata.

**Mai patchare file esistenti con `write_text` in Python su Windows**: traduce LF in CRLF e riscrive tutto. Usare `write_bytes` o l'editor. Tutti gli script del progetto sono a LF.

**Account per le sessioni graphify.** `scripts\start_graphify.ps1` prende `-SourceFolder` e opzionalmente `-Account`; senza `-Account` la sessione eredita il default del terminale.

**Il `--numstat` non e' un controllo di riservatezza**, e in modalita' refresh non vale nemmeno la regola "solo aggiunte". I controlli reali sono in `.claude/context/dev-testing.md`.

**Un preview migliore amplia la superficie da sanitizzare.** Da quando e' ancorato al nodo, il testo pubblicato e' contenuto reale preso dal centro dei documenti.

---

## Note su cosa c'e' su disco

`_intermediate/src/` contiene i corpora dei cicli lavorati e i loro grafi, ed e' la base su cui gira la regola di misura: **non va svuotata**. Le tre righe di esclusione per-subfolder in `.gitignore` e `.graphifyignore` puntano a cartelle staged ora rimosse: sono state lasciate come guardia, perche' se un ciclo futuro ricreasse una cartella con lo stesso nome l'esclusione tornerebbe utile.

Per ARCHITETTURA e Miscellaneous la cartella non si puo' potare tenendo solo `graphify-out`: tre dei quindici documenti sorgente stanno in una sottocartella esterna e servono al ri-arricchimento. Verificato, non ipotizzato.

---

## Comandi di riferimento

```
# digest dello stato ingest
.\scripts\session_resume.ps1

# verifica di riservatezza sul repo pubblico (obbligatoria prima di ogni commit)
.\.venv\Scripts\python.exe scripts\verify_public_repo.py
.\.venv\Scripts\python.exe scripts\verify_public_repo.py --history

# installazione degli hook nel repo pubblico
.\scripts\install_hooks.ps1

# pre-flight graphify (passo 0, sola verifica)
.\.venv\Scripts\python.exe scripts\prepare_graphify_source.py --folder "_intermediate\src\<nome>"

# sessione graphify
.\scripts\start_graphify.ps1 -SourceFolder "_intermediate\src\<nome>-sanitized" -Account account2

# catena a valle
.\.venv\Scripts\python.exe scripts\generate_taxonomy_index.py --output _intermediate\taxonomy_index.json
.\.venv\Scripts\python.exe scripts\enrich_graph.py --graph "<...>\graphify-out\graph.json" --workdir "<...>" --output _intermediate\enriched_graph.json
.\.venv\Scripts\python.exe scripts\map_to_taxonomy.py --enriched-graph _intermediate\enriched_graph.json --taxonomy _intermediate\taxonomy_index.json --output-md _intermediate\taxonomy_diff.md --output-json _intermediate\taxonomy_diff.json
notepad _intermediate\taxonomy_diff.md   # REVISIONE: partire dai DA VERIFICARE
.\.venv\Scripts\python.exe scripts\sanitize_taxonomy_diff.py --input _intermediate\taxonomy_diff.json --output _intermediate\taxonomy_diff.sanitized.json --extra-residue-terms "<nomi singoli trovati in revisione>"
.\.venv\Scripts\python.exe scripts\export_to_taxonomy.py --diff-json _intermediate\taxonomy_diff.sanitized.json --skills-repo $env:LETTERDOC_SKILLS_REPO --prune-moved --prune-unexpected --dry-run

# diario: draft in _notes\, poi
.\.venv\Scripts\python.exe scripts\append_diary_section.py --draft "_notes\<draft>.md"
.\.venv\Scripts\python.exe scripts\append_diary_section.py --draft "_notes\<draft>.md" --apply
.\scripts\finalize_diary.ps1
```
