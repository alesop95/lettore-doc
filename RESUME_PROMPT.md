# RESUME_PROMPT

> Documento di passaggio scritto il 2026-07-29 alla chiusura di una sessione su
> `account3`, per riaprire su `account2`. Serve a far ripartire il lavoro senza
> ricostruire il contesto dalla conversazione precedente.
>
> Lo stato canonico e sintetico resta `.claude/memory/index.md`, e il work-log
> dettagliato `.claude/memory/progress.md`. Questo file e' il passaggio verboso
> di una transizione specifica: se lo si legge molto dopo il 2026-07-29, quei due
> hanno la precedenza.

> Aggiornamento del 2026-07-29, a valle della sessione che ha letto questo file:
> l'azione pendente e' stata eseguita (`1033bc1`) e i punti 1-4 della coda di
> lavoro qui sotto sono chiusi in `382f99e` piu' skills-repo `cfeada5`. Resta
> aperto il solo punto 5, il prossimo ciclo di ingest. Quello che di questo
> documento conserva valore e' la sezione su cosa e' stato provato e scartato e
> quella sulle trappole verificate su questa macchina; per lo stato vale
> `.claude/memory/index.md` e per il dettaglio `.claude/memory/progress.md`.

---

## Come ripartire

Aprire Claude Code nella root del progetto e seguire la procedura ordinaria:
leggere `.claude/memory/index.md`, poi `.claude/context/current-work.md`, poi
invocare la skill `sync-context` per il drift schede-codice. Questo file
aggiunge il contesto che quei tre non contengono, cioe' il perche' delle scelte
appena fatte e cosa e' stato provato e scartato.

---

## Stato esatto al momento della consegna

| Cosa | Valore |
|---|---|
| `lettore-doc` HEAD | `a0ea49b` |
| `skills-repo` HEAD | `502efe5` (allineato con origin) |
| Schede `context/` | frontmatter a `9594d44`, **da bumpare** ad `a0ea49b` |
| Evidenze pubblicate | 239 ID su 11+ pagine Capability |
| Ultimo ciclo di ingest | Cybersec endpoint governance, chiuso, skills-repo `5ca2dd6` |
| Diario | in pari, ultima sezione C.14 |

### Azione pendente immediata

Due schede sono modificate e non committate, perche' il `git add` e' andato a
capo in PowerShell e le righe successive sono state interpretate come stringhe a
se'. E' successo due volte in questa sessione: **dare sempre i comandi git su
riga singola**.

```powershell
git add scripts/map_to_taxonomy.py .claude/context/dev-testing.md .claude/context/roadmap.md
git commit -m "Marca i fit a destinazione incerta e ne dichiara il motivo"
git push
```

`scripts/map_to_taxonomy.py` e' gia' dentro `a0ea49b`, quindi il comando qui
sopra committa in pratica le sole due schede; includerlo e' innocuo.

Dopo il commit, bumpare `last-verified-commit` delle sei schede in
`.claude/context/` al nuovo sha e aggiornare il commit di riferimento in
`.claude/memory/index.md`.

---

## Cosa e' stato fatto nelle ultime due sessioni

Tre filoni, tutti chiusi.

**Ciclo di ingest Cybersec endpoint governance.** Nove documenti selezionati a
mano da due subfolder del segmento Cybersec, 28 evidenze pubblicate su 2
Capability. Ha confermato sul campo la correzione del routing GDPR fatta il
giorno prima (zero evidenze a `Quality Certification`, 5 correzioni manuali su
28 contro 18 su 34 del ciclo precedente) e ha scoperto una **fuga reale**:
ragione sociale e hostname uscivano nel repo pubblico attraverso i *nomi dei
file*, per due strade indipendenti, la riga `- **Source**:` scritta verbatim e il
frontmatter di tracciabilita' che finiva nel preview del corpo. Chiusa su tre
livelli. La fuga e' stata vista solo cercando le stringhe sensibili nel
`git diff` del repo pubblico con l'`--apply` gia' fatto e nulla committato: il
riepilogo dell'export e il `--numstat` erano entrambi verdi.

**Audit del pubblicato e riparazione retroattiva.** Audit su albero di lavoro e
su tutti i 20 commit della storia del repo pubblico: nessun cognome, email, IP
interno, hostname, dominio aziendale, fornitore o sede, in nessun commit. La sola
stringa presente era la ragione sociale nuda, che le pagine dichiarano
volutamente: rimossa la regola `residue-company-intrawelt` dal gate, con recupero
di 4 evidenze scartate a torto. L'audit ha invece trovato un difetto di qualita'
serio, 44 evidenze pubblicate con preview identico, riparate introducendo
`anchored_preview` (il preview era costruito per file e non per nodo) e la
modalita' `--refresh` in `export_to_taxonomy.py`, che prima non esisteva:
l'idempotenza per ID protegge dai duplicati e insieme immobilizzava gli errori.

**Fragilita' del punteggio: misurata e resa visibile, non risolta.** Vedi la
sezione seguente, che e' la piu' importante da leggere prima di riprovarci.

---

## Cosa e' stato provato e scartato (non ritentare senza motivo nuovo)

Il problema: `recall_score` e' una sovrapposizione di insiemi fra i token del
nodo e le keyword della Capability. Con label di tre-sei token il segnale e'
sottile, e nel ciclo endpoint **otto fit su ventotto avevano margine esattamente
zero** sul secondo classificato, cioe' la destinazione veniva decisa dall'ordine
di iterazione del nav di MkDocs.

**Pesaggio IDF dei token per capacita' discriminante. Scartato.** Implementato e
misurato contro le sei assegnazioni note come sbagliate: ne correggeva due ma
rompeva una che era giusta (`Problema connessione RDP LAN`, da Networking
corretto a Cybersecurity sbagliato) e spostava un'altra da sbagliata a
diversamente sbagliata. Guadagno netto di uno su sei: non giustifica di toccare
una funzione di punteggio tarata sul campo. Annullato con `git checkout`.

**Ponte bilingue italiano-inglese sui token. Scartato, peggiora.** Una mappa di
termini IT italiani verso i corrispondenti inglesi porta il nodo `PSGSI Politica
Sicurezza Informazioni` da non classificato a instradato **con sicurezza sulla
pagina sbagliata** (`Microsoft 365 Business`, che matcha su `policy` e
`security`). Un errore confidente e' peggio di un silenzio.

**Conclusione.** Nessun aggiustamento lessicale riduce gli errori su questa
classe di casi: li sposta. La strada strutturale e' una rappresentazione
semantica, cioe' la voce sugli embeddings in `roadmap.md`. Chi la riprende
sappia che le due alternative economiche sono state provate e misurate.

**Cosa e' stato fatto invece.** `map_to_taxonomy.py` marca **DA VERIFICARE** i
fit in cui la destinazione non e' determinata dal punteggio, con due criteri:
margine entro `REVIEW_MARGIN` (0.05) sul secondo classificato, oppure decisione
poggiata su un solo token. Per ciascuno il diff stampa il secondo classificato
col suo punteggio e i token che hanno deciso. Sul ciclo endpoint: 10 marcati su
31, e **tutti e cinque** gli errori poi corretti a mano stavano fra quelli.
Precisione 50%, richiamo 100%. Sui pareggi il secondo classificato e' spesso la
destinazione giusta, quindi la correzione e' immediata. Non e' una soluzione
della fragilita': e' una revisione mirata invece che cieca.

---

## Coda di lavoro, in ordine di priorita'

**1. Via di rimozione per un'evidenza pubblicata.** E' il prerequisito di
qualsiasi riclassificazione retroattiva, e finche' non esiste non si possono
valutare cambi della funzione di punteggio applicati allo storico. Il problema:
l'ID stabile e' `sha256(node_id + "::" + cap_slug)[:12]`, quindi se una
riclassificazione sposta un nodo di pagina l'ID cambia, `--refresh` inietta il
blocco nuovo sulla pagina giusta ma **non riconosce piu' quello vecchio**, che
resta orfano. Risultato, evidenza duplicata su due pagine. Si e' visto dal vivo
in un dry-run: "5 iniezioni pianificate, 25 gia' presenti" su un diff dove i 5
erano nodi mal instradati con ID nuovo. Serve una passata che, dato il diff
corrente, trovi gli ID di evidenza presenti nel repo pubblico e non piu' previsti,
e li rimuova; `replace_block` in `export_to_taxonomy.py` ha gia' la logica di
delimitazione del blocco da cui partire.

**2. Domini di terzi nel gate residue.** L'unico punto aperto che riguarda la
riservatezza e non la qualita'. I pattern in `sanitize_taxonomy_diff.py` coprono
il dominio aziendale ma non domini esterni arbitrari. Il nodo `Dominio
sabaerospace.com`, che e' il dominio di un terzo, non e' stato pubblicato perche'
ha preso punteggio zero, non perche' il gate lo abbia fermato.

**3. `EXCLUDE_DIR_NAMES` in `ingest_state.py`.** Il digest segnala e continuera' a
segnalare 996 file nuovi su `Miscellaneous procedure e utilities`, tutti scraping
di brochure di fondi di terzi sotto `Web scraping - Downloaded Web sites`. Non e'
materiale da ingerire. Due righe, accanto a `_archive` e `templates`.

**4. Capability `Soft Skills` a zero keyword.** Non puo' ricevere evidenze. Da
verificare se la pagina abbia le due sezioni H2 da cui
`generate_taxonomy_index.py` estrae.

**5. Prossimo ciclo di ingest.** Candidate mai ingerite, per dimensione:
`Helpdesk_T-Rex` (41 doc), `_DA SISTEMARE (Alessio)` (44),
`Helpdesk_RWS-Groupshare-Studio` (17), un blocco coeso dei piccoli `Helpdesk_*`
(circa 35 in totale), `TOOL AI coding assistance` (9). Le grandi (`ENIVIPA` 2500,
`SCENIA` 918, `OpenAI` 267) vanno segmentate per coesione semantica, non prese in
blocco. Nel segmento Cybersec restano non lavorate `Privacy (GDPR e Contratti)`
(33), `_VA e Pentest assessment` (12, con report di rischio da escludere),
`_QUESTIONARI FORNITORI` (126, dati di terzi, da escludere) e dieci documenti di
`_ GDPR E ISO27001`.

---

## Trappole verificate su questa macchina

**Comandi git su riga singola.** In PowerShell un `git add` andato a capo fa
interpretare le righe successive come stringhe a se': e' successo due volte, con
commit incompleti che sono stati scoperti solo controllando `git status` dopo.

**Mai patchare file esistenti con `write_text` in Python su Windows.** Traduce
`\n` in `\r\n` e riscrive il file per intero: e' capitato su
`export_to_taxonomy.py`, che era l'unico script a LF, facendo apparire 504 righe
cambiate invece di 59. Usare `write_bytes`, o l'editor, o `newline=""`. Tutti gli
script del progetto sono a LF.

**Account per le sessioni graphify.** La skill e' installata su `account1`,
`account2` e `account3`. Il launcher `scripts/start_graphify.ps1` prende
`-SourceFolder` (non `-Folder`) e opzionalmente `-Account`; senza `-Account` la
sessione eredita il default del terminale, ed e' cosi' che il ciclo del 28 luglio
e' finito su `account1` mentre quello di luglio era su `account2`. **Su `account1`
il login risultava in scadenza in tre giorni al 2026-07-28**: verificarlo prima
di aprire un ciclo lungo.

**`enrich_graph.py` ha ora una cache per file.** Prima rifaceva l'estrazione NER
una volta per nodo invece di una per file, e su ARCHITETTURA (203 nodi, una
ventina di documenti) significava minuti. Ora la riesecuzione di quel ciclo e'
questione di secondi. Se una modifica futura rompe la cache, il sintomo e' un
enrich che va in background per dieci minuti.

**Il `--numstat` non e' un controllo di riservatezza**, e in modalita' `--refresh`
non vale nemmeno la regola "solo aggiunte", perche' le cancellazioni sono
legittime. I controlli reali sono in `.claude/context/dev-testing.md`: ricerca
esplicita delle stringhe sensibili nel `git diff` del repo pubblico con l'apply
fatto e nulla committato, conteggio degli ID di evidenza prima e dopo, e presenza
delle quattro H2 di contratto in ogni pagina toccata.

**Un preview migliore amplia la superficie da sanitizzare.** Da quando il preview
e' ancorato al nodo, il testo pubblicato e' contenuto reale preso dal centro dei
documenti e i residui arrivano davvero. Ogni miglioramento della qualita' del
preview va accompagnato da una rilettura dei pattern residue.

---

## Comandi di riferimento

```
# digest dello stato ingest
.\scripts\session_resume.ps1

# pre-flight graphify su una subfolder (passo 0, sola verifica)
.\.venv\Scripts\python.exe scripts\prepare_graphify_source.py --folder "_intermediate\src\<nome>"

# sessione graphify
.\scripts\start_graphify.ps1 -SourceFolder "<path>" -Account account2

# catena a valle
.\.venv\Scripts\python.exe scripts\generate_taxonomy_index.py --output _intermediate\taxonomy_index.json
.\.venv\Scripts\python.exe scripts\enrich_graph.py --graph "<...>\graphify-out\graph.json" --workdir "<...>" --output _intermediate\enriched_graph.json
.\.venv\Scripts\python.exe scripts\map_to_taxonomy.py --enriched-graph _intermediate\enriched_graph.json --taxonomy _intermediate\taxonomy_index.json --output-md _intermediate\taxonomy_diff.md --output-json _intermediate\taxonomy_diff.json
.\.venv\Scripts\python.exe scripts\sanitize_taxonomy_diff.py --input _intermediate\taxonomy_diff.json --output _intermediate\taxonomy_diff.sanitized.json
notepad _intermediate\taxonomy_diff.md   # REVISIONE: partire dai DA VERIFICARE
.\.venv\Scripts\python.exe scripts\export_to_taxonomy.py --diff-json _intermediate\taxonomy_diff.sanitized.json --skills-repo $env:LETTERDOC_SKILLS_REPO --dry-run

# diario: draft in _notes\, poi
.\.venv\Scripts\python.exe scripts\append_diary_section.py --draft "_notes\<draft>.md"
.\.venv\Scripts\python.exe scripts\append_diary_section.py --draft "_notes\<draft>.md" --apply
.\scripts\finalize_diary.ps1
```
