# Stato del progetto — fotografia al 2026-07-29

Questo documento serve a orientarsi quando si e' perso il filo. Non sostituisce
gli altri: dice cosa il sistema fa oggi, come si usa oggi, dove vive ogni tipo
di verita', e cosa e' rimasto aperto. Va riscritto quando divergere da esso
costa piu' che aggiornarlo, non a ogni commit.

Per il dettaglio architetturale resta `GUIDA-TECNICA.md`, per la storia delle
decisioni il diario, per lo stato di avanzamento sintetico
`.claude/memory/index.md`.

---

## 1. Cosa fa il sistema, in una pagina

`lettore-doc` e' un motore privato che legge documentazione aziendale reale e
produce due cose indipendenti fra loro.

La prima e' un vault Obsidian locale in `vault-output/`, con una nota per
documento, un grafo di relazioni e sintesi narrative. Serve a consultare il
proprio materiale, non esce mai dalla macchina, e non ha nulla a che vedere con
la pubblicazione.

La seconda e' l'alimentazione di una tassonomia pubblica di competenze,
pubblicata come sito MkDocs su GitHub Pages. Qui il sistema non pubblica
documenti: estrae dai documenti dei *nodi di evidenza*, li classifica contro le
pagine di competenza esistenti, li anonimizza, e inietta un blocco di evidenza
nella pagina giusta. Nel repository pubblico non finisce mai un documento, mai un
nome di persona, mai un indirizzo di rete, mai un hostname del parco macchine.

Lo stato quantitativo di oggi, misurato e non stimato: otto domini e trentuno
pagine di competenza nella tassonomia pubblica, duecentotrentanove blocchi di
evidenza pubblicati, sette subfolder sorgente tracciate come ingerite per
centottantotto documenti di testo complessivi.

---

## 2. I due flussi

### Flusso A — vault Obsidian privato

Un solo comando, interamente deterministico e offline.

```
.\run_pipeline.ps1 -SourceFolder "<cartella sorgente>"
```

Dentro, in ordine: `parse_docx.py` legge i documenti a livelli di dettaglio
crescenti senza mai caricarli interi, `extract_entities.py` estrae le entita'
italiane con regex piu' NER spaCy locale, `build_knowledge_graph.py` calcola il
grafo pesato fra documenti, `generate_vault.py` scrive le note e i wiki-link. Le
sintesi narrative sono l'unico passo linguistico e si producono a parte, con il
subagente `lettore-documentazione`.

Le varianti utili sono `-Incremental`, che salta i file con hash invariato, e
`-OnlyVault`, che rigenera le sole note dopo aver aggiornato le sintesi.

### Flusso B — estrazione skill verso la tassonomia pubblica

Questo e' il flusso che conta, ed e' quello che negli ultimi cicli e' cambiato
di piu'. Sette passi, di cui uno solo interattivo.

```
selezione a mano  ->  _intermediate/src/<ciclo>/
                          |
                  prepare_graphify_source.py --apply
                          |
                      <ciclo>-sanitized/          nomi neutralizzati, corpo intatto
                          |
                   /graphify .                    UNICO passo interattivo
                          |
                    graphify-out/graph.json
                          |
                     enrich_graph.py              anonymization_map + preview ancorato
                          |
                   enriched_graph.json
                          |
                    map_to_taxonomy.py            fit / new_capability / new_domain
                          |            \
              taxonomy_diff.json        taxonomy_diff.md    <- REVISIONE UMANA
                          |
                 sanitize_taxonomy_diff.py        GATE: scarta e scruba i residui
                          |
              taxonomy_diff.sanitized.json
                          |
                   export_to_taxonomy.py          --dry-run poi --apply
                          |
                    skills-repo/docs/*.md         commit e push manuali
                          |
                    ingest_state.py track         chiude il ciclo
```

Tre cose di questo flusso non sono ovvie e sono le piu' facili da dimenticare.

Il passo di preparazione non e' opzionale. graphify scarta da solo i file il cui
*nome* contiene termini che sembrano segreti, guardando il nome e mai il
contenuto, e lo fa in silenzio: una policy intitolata
"Configurazione-password-Windows.docx" spariva dal corpus senza alcun segnale.
`prepare_graphify_source.py` replica quel filtro a monte, dice cosa verrebbe
scartato, e con `--apply` produce una cartella parallela con i soli nomi
neutralizzati. Il corpo non viene toccato: l'anonimizzazione dei dati e' un
problema diverso e la risolvono i passi a valle.

Il file che va in export non e' il diff prodotto dalla classificazione, e' quello
sanitizzato. Fra i due c'e' il gate, che e' obbligatorio.

La revisione umana del diff e' obbligatoria e non e' cieca. `map_to_taxonomy.py`
marca `DA VERIFICARE` i fit la cui destinazione non e' determinata dal punteggio,
e per ognuno stampa il secondo classificato e i token che hanno deciso. Si parte
da quelli: sul ciclo di endpoint erano dieci su trentuno e contenevano tutti e
cinque gli errori poi corretti a mano.

---

## 3. Come si esegue un ciclo, in concreto

I comandi assumono di stare nella root del progetto. La forma completa con tutti
i parametri e' in `CLAUDE.md`; qui c'e' la sequenza con il minimo indispensabile
e le decisioni che accompagnano ogni passo.

**Prima di tutto, il digest.** Dice quali subfolder sono state ingerite, quando,
con quale commit del repo pubblico, e quali file sono cambiati da allora.

```
.\scripts\session_resume.ps1
```

**Passo 0, selezione e preparazione.** Si scelgono a mano i documenti del ciclo e
si copiano in `_intermediate/src/<nome-ciclo>/`. La selezione e' una decisione,
non un automatismo: si escludono i materiali contrattuali e commerciali, i dati
di terzi, e i documenti il cui *nome* contiene un dato personale, che va
neutralizzato all'ingresso. La cartella con gli originali va aggiunta a
`.gitignore` e `.graphifyignore`, entrambi, perche' contiene documenti aziendali
non anonimizzati. Poi il pre-flight, prima in sola verifica e poi con `--apply`.

**Passo 1, graphify.** Unico passo interattivo e unico che consuma token.

```
.\scripts\start_graphify.ps1 -SourceFolder "_intermediate\src\<ciclo>-sanitized" -Account account2
```

Dentro la sessione, `/graphify .`. Il parametro `-Account` conta su questa
macchina, dove ci sono piu' account Claude Code configurati: senza di esso la
sessione eredita il default del terminale, ed e' cosi' che un ciclo e' finito
sull'account sbagliato.

**Passi 2 e 3, indice e arricchimento.** Si rigenera l'indice della tassonomia
dal `mkdocs.yml` del repo pubblico, perche' le pagine possono essere cambiate, e
si arricchisce il grafo. L'arricchimento e' il passo che costruisce la mappa di
anonimizzazione e il testo di anteprima ancorato al nodo.

**Passo 4, classificazione.** Produce il diff in due formati, JSON per la
macchina e Markdown per la lettura.

**Passo 5, revisione.** Si legge il Markdown partendo dai `DA VERIFICARE`. E' il
punto in cui il giudizio umano non e' sostituibile.

**Passo 6, gate.** `sanitize_taxonomy_diff.py` produce il `.sanitized.json`. Il
suo report dice quante entries ha scartato e per quale regola, e quante
mascherature ha applicato: zero mascherature su un corpus aziendale e' piu'
sospetto di molte.

**Passo 7, export.** Sempre `--dry-run` prima di `--apply`. Il dry-run elenca
anche i collocamenti obsoleti, cioe' le evidenze pubblicate che questo diff non
prevede piu' su quella pagina.

**Passo 8, i controlli veri.** Con l'`--apply` fatto e nulla committato, cioe'
nella finestra in cui `git checkout -- docs/` annulla tutto, si cercano
esplicitamente le stringhe sensibili nel `git diff` del repo pubblico. Il
riepilogo dell'export e il conteggio delle righe non sono controlli di
riservatezza: nel ciclo del 28 luglio erano entrambi verdi mentre nel diff
c'erano quattordici occorrenze della ragione sociale. Si verifica poi che ogni
pagina toccata conservi le quattro intestazioni di contratto, e si lancia
`mkdocs build --strict`.

**Passo 9, chiusura.** Commit e push manuali sul repo pubblico, poi
`ingest_state.py track` una sola volta, con il commit appena creato. Solo dopo
questo il ciclo e' chiuso, e va scritta la sezione del diario.

---

## 4. Le modalita' dell'export, che sono tre e vanno distinte

`export_to_taxonomy.py` e' l'unico script che scrive nel repository pubblico, e
le sezioni `## Projects & evidence` sono di sua competenza esclusiva: non si
editano a mano, mai.

L'iniezione normale aggiunge i blocchi mancanti e salta quelli gia' presenti,
riconoscendoli da un identificatore stabile scritto in un commento HTML
invisibile. E' idempotente: rilanciare non duplica nulla.

`--refresh` riscrive un blocco gia' pubblicato. Serve perche' l'idempotenza, che
protegge dai duplicati, rendeva anche impossibile correggere un errore: quando un
difetto della pipeline ha prodotto quarantaquattro evidenze con lo stesso testo,
l'unica alternativa sarebbe stata editare a mano, che le regole vietano.

`--prune-moved` e `--prune-unexpected` rimuovono. Chiudono il caso che
l'idempotenza da sola produce: l'identificatore dipende dalla pagina di
destinazione, quindi una riclassificazione che sposta un nodo genera un
identificatore nuovo, inietta il blocco sulla pagina giusta e lascia orfano
quello vecchio, cioe' un'evidenza duplicata su due pagine. Il primo flag copre i
nodi che il diff colloca altrove ed e' sicuro; il secondo copre quelli scesi
sotto soglia ed e' invasivo, perche' una variazione di soglia cancellerebbe
evidenze valide. La ricerca dei collocamenti obsoleti gira comunque a ogni
esecuzione, anche senza flag, perche' e' l'unico controllo che vede questa classe
di difetto.

---

## 5. Come e' fatta la difesa della riservatezza

Sono quattro strati, e la ragione per cui sono quattro e' che ognuno ha fallito
almeno una volta da solo.

Il primo e' la separazione fisica: due repository con scopi opposti, e uno solo
script autorizzato a scrivere in quello pubblico.

Il secondo e' la mappa di anonimizzazione, costruita da `enrich_graph.py`, che
sostituisce ragioni sociali, nomi di persona, indirizzi di posta, indirizzi di
rete e hostname con segnaposto numerati. Si applica a ogni testo che finisce nel
repository pubblico, compreso il nome del file citato come fonte e lo slug del
file di una nuova pagina.

Il terzo e' il gate dei residui, che ispeziona il testo *dopo* l'anonimizzazione
e interviene su cio' che la mappa ha mancato. Sul titolo dell'evidenza scarta,
perche' un titolo mascherato spesso non significa piu' niente; sul nome del file
e sull'anteprima scruba, perche' un residuo li' non rende l'evidenza inutile.
Copre indirizzi di rete e di posta, hostname, il dominio aziendale, i fornitori
ricorrenti, le sedi fisiche, e dal 29 luglio i domini di aziende terze.

Il quarto e' la ricerca manuale delle stringhe sensibili nel diff reale prima del
commit, ed e' quello che ha trovato la sola fuga vera della storia del progetto.
Gli altri tre erano tutti verdi.

Una distinzione che regge tutto il sistema e che vale ricordare: la ragione
sociale nuda non e' un segreto, perche' la pagina di presentazione della
tassonomia dichiara volutamente il ruolo e il datore di lavoro. Sono segreti
l'infrastruttura e le persone. La stessa logica governa la lista di eccezioni sui
domini: un prodotto dichiarato come tecnologia e' curriculum, un sottodominio di
infrastruttura e' un sistema di terzi.

---

## 6. Dove vive ogni tipo di verita'

La proliferazione di documenti e' la ragione principale per cui si perde il filo,
quindi questa e' la mappa.

`README.md` sono le istruzioni operative e i comandi, piu' installazione e
problemi noti. `GUIDA-TECNICA.md` e' l'architettura di dettaglio, con formule,
soglie e pesi. `case-study-operativi.md` sono otto scenari pratici con i comandi
esatti. Il diario in `.docx`, con il suo specchio `.md` rigenerato
automaticamente, e' la storia: perche' una decisione e' stata presa, cosa e'
stato provato e scartato, cosa e' andato storto. Questo documento e' la
fotografia d'insieme.

Sotto `.claude/` sta la memoria di lavoro. `memory/index.md` e' lo stato
sintetico, cioe' branch, commit di riferimento, stato delle schede e prossima
azione, ed e' il primo file da leggere all'apertura di una sessione.
`memory/progress.md` e' il work-log in ordine cronologico inverso.
`memory/decisions.md` sono le decisioni. Le schede in `context/` riassumono
l'architettura per area, ciascuna con il commit a cui e' stata verificata, e si
riconciliano con la skill `sync-context`. `CLAUDE.md` e le regole in
`.claude/rules/` sono le istruzioni vincolanti per l'agente.

Lo stato dell'ingest non e' in git: vive in `_intermediate/ingest_state.json`,
locale alla macchina, ed e' gestito esclusivamente da `ingest_state.py`. La
storia condivisa e' Git sul repository pubblico piu' il diario.

---

## 7. Cosa e' aperto

Il punto di fondo e' la fragilita' della classificazione. Il punteggio e' una
sovrapposizione di insiemi fra i token del nodo e le parole chiave della pagina,
e con etichette di tre a sei token il segnale e' sottile: nel ciclo di endpoint
otto fit su ventotto avevano margine esattamente zero sul secondo classificato,
cioe' la destinazione era decisa dall'ordine di iterazione del menu. Due rimedi
economici sono stati provati e misurati, il pesaggio dei token per capacita'
discriminante e un ponte bilingue italiano-inglese, e sono stati scartati perche'
spostano gli errori invece di ridurli; il secondo peggiora, perche' trasforma un
silenzio in un errore confidente. La strada resta una rappresentazione semantica,
e da oggi e' percorribile anche sullo storico, perche' esiste la via di rimozione.
Nel frattempo la mitigazione e' la marcatura `DA VERIFICARE`.

Restano poi voci minori, tutte in `roadmap.md`: l'ereditarieta' dei token di
community, che fa muovere le community in blocco; un avviso esplicito per una
pagina di competenza a zero parole chiave, oggi silenzioso; l'allargamento dei
suffissi di dominio nel gate, da fare solo su evidenza dal corpus.

Il lavoro sostanziale che resta e' l'ingest. Le candidate mai ingerite sono
elencate in `memory/index.md`; le grandi vanno segmentate per coesione semantica
e non prese in blocco. Alcune subfolder sono escluse per scelta: i questionari
fornitori perche' contengono dati di terzi, i report di rischio dei penetration
test perche' descrivono vulnerabilita' reali.

---

## 8. La regola di metodo che vale piu' delle altre

Una modifica al gate di riservatezza o alla classificazione non si considera
fatta finche' non e' stata rilanciata sui corpora storici e confrontata con
l'esito precedente, mettendo a confronto le destinazioni per identificatore di
nodo e non i totali, perche' due errori che si compensano tengono il totale
fermo. Un test sintetico dice se una regola scatta, non cosa scarterebbe di
buono: la regola sui domini di terzi passava il test sintetico e sui corpora
reali scartava tre tecnologie dichiarate. Il costo di questa verifica e' di pochi
minuti solo perche' i corpora sono su disco e ogni stato intermedio e' un file
JSON ispezionabile, che e' il rendimento della scelta di tenere il lavoro
deterministico fuori dal modello.
