# Tassonomia di Competenze IT — Diario tecnico di sviluppo

*Versione Markdown del documento `diario-tecnico-progetto (lettore-doc + skills-repo).docx`. Le due versioni sono mantenute sincronizzate: vedere `CLAUDE.md` di lettore-doc per le regole di aggiornamento.*

**Repository**: `alesop95/lettore-doc` (privato) + `alesop95/skills` (pubblico)  
**Sito live**: [alesop95.github.io/skills/](https://alesop95.github.io/skills/)

---
# Introduzione

Questo documento racconta la storia di un sistema costruito per risolvere un problema operativo preciso: estrarre automaticamente le competenze dimostrate da una cartella di documentazione aziendale in formato .docx e pubblicarle come tassonomia navigabile su un sito web accessibile da qualsiasi interlocutore tecnico tramite un URL stabile. Questo documento ricostruisce le decisioni prese, i problemi incontrati, le soluzioni adottate e le ragioni tecniche che le hanno determinate, nell'ordine in cui si sono verificate. È scritto per capire il sistema, mantenerlo, eventualmente estenderlo, e per comprendere non solo il cosa ma il perchè di ogni scelta.

Il sistema si articola su due repository Git separati e distinti per scopo.

Il primo, lettore-doc, è il motore privato di elaborazione: legge i documenti sorgente, costruisce un grafo semantico dei concetti e delle relazioni contenuti in essi, applica post-processing specializzato per l'italiano formale aziendale, sanitizza i dati prima che escano dal perimetro privato, e prepara il contenuto curato per la pubblicazione. Non va mai online, e contiene tutto il codice operativo del sistema.

Il secondo, skills-repo, è il prodotto finale: una tassonomia di competenze organizzata in file Markdown che vengono trasformati in un sito web statico da MkDocs Material[^1] e pubblicati automaticamente su GitHub Pages[^2] ad ogni aggiornamento tramite GitHub Actions[^3].

Il confine tra i due domini non è una scelta stilistica: è un presidio di sicurezza fisico che impedisce strutturalmente che dati sensibili - nomi di clienti, codici progetto interni, configurazioni di rete reali - finiscano in un repository pubblico.

# Il problema originale

Il punto di partenza era una tassonomia di skill per IT manager gia' parzialmente strutturata in file Markdown, organizzata secondo una gerarchia a tre livelli: un Domain per area tematica, una Capability per competenza specifica, e all'interno di ogni Capability una serie di sezioni che descrivono tecnologie usate, responsabilita' operative ed evidenze progettuali. Parallelamente esisteva una cartella di documentazione aziendale di grandi dimensioni, composta da verbali di progetto, capitolati tecnici, specifiche, procedure operative e manuali, tutti in formato .docx. L'obiettivo era stabilire un collegamento automatico tra i due: far si' che le skill dimostrabili sulla base di quanto documentato in quella cartella andassero ad arricchire la tassonomia in modo verificabile, tracciabile e ripetibile.

Il problema non era banale per due ragioni indipendenti che si sovrapponevano. La prima era di volume: una cartella di cento o duecento documenti aziendali, ciascuno di quaranta-sessanta pagine, rappresenta nell'ordine di uno-due milioni di token[^4]. Una finestra di contesto di un LLM[^5] da duecentomila token ne contiene meno di un sesto, il che rende impossibile caricare l'intero corpus in una singola sessione di analisi. La seconda ragione era di riservatezza: quella documentazione conteneva nomi di clienti, codici progetto interni, importi di contratti, configurazioni di rete, dati personali di tecnici e referenti. Qualsiasi sistema che pubblicasse automaticamente le skill estratte avrebbe dovuto, prima di farlo, garantire che nessun dato identificativo transitasse verso l'esterno.

A queste due ragioni se ne aggiungeva una terza di natura pratica: il formato .docx non è un file di testo. È un archivio ZIP che contiene una struttura XML complessa con stili, immagini incorporate, tabelle, revisioni e metadati. Aprirlo con un editor di testo produce caratteri binari illeggibili. Leggerlo in modo strutturato richiede una libreria come python-docx, che espone paragrafi, sezioni, tabelle e stili come oggetti navigabili. Questa complessita' ha implicazioni dirette sulla pipeline di elaborazione: non si tratta semplicemente di leggere file di testo, ma di estrarne la struttura logica in modo affidabile su documenti stilisticamente eterogenei, spesso prodotti con formattazioni non standard o heading numerati manualmente anzichè tramite gli stili nativi di Word.

# Il piano iniziale e i suoi limiti strutturali

La prima proposta strutturata prevedeva un pipeline Python in quattro fasi sequenziali, orchestrato da Claude Code[^6] come agente autonomo. La prima fase avrebbe scritto uno script con python-docx che itera tutti i file nella cartella, estrae il testo grezzo di ciascun documento e lo salva in un formato intermedio .json con il nome del file come chiave. La separazione tra estrazione e analisi era pensata per rendere il processo riprendibile in caso di interruzione: se la pipeline si interrompesse dopo cento documenti, alla ripresa non si sarebbe dovuto ripartire da zero. La seconda fase avrebbe letto i file Markdown della tassonomia esistente e costruito una struttura dati gerarchica che rappresentasse le skill gia' censite, con i loro livelli e categorie, da usare come riferimento per la fase di estrazione successiva.

La terza fase era quella computazionalmente piu' costosa. Per ogni documento, o per batch di documenti piu' piccoli, lo script avrebbe chiamato le API[^7] di Anthropic con un prompt strutturato: "dato questo documento di progetto, elenca le skill IT manager dimostrate o richieste, mappandole sulle categorie della tassonomia esistente". I risultati sarebbero stati accumulati in un file JSON[^8] progressivo con checkpoint per documento, in modo da tollerare interruzioni senza perdere lavoro gia' fatto. La quarta e ultima fase avrebbe aggregato tutti i risultati delle chiamate, deduplicate le skill ricorrenti, identificato quelle non presenti nella tassonomia originale, e generato i file Markdown aggiornati o un diff rispetto all'originale.

Il piano aveva una coerenza interna, ma conteneva tre problemi strutturali che solo l'analisi approfondita ha reso evidenti. Il primo era che la "Fase 1" stava reinventando da zero qualcosa che esisteva gia' nel progetto lettore-doc: un parser .docx con parallelismo automatico, modalita' incrementale via hash, gestione corretta dei path OneDrive con accenti e spazi, e disclosure progressiva a tre livelli di dettaglio. Costruire un secondo parser da zero sarebbe stato un raddoppio di codice senza nessun guadagno tecnico rispetto a estendere quello gia' esistente e testato.

Il secondo problema era economico. Ogni chiamata alla terza fase consumava token dell'API Anthropic a pagamento. Con una stima conservativa di duemila-tremila token per documento (solo la sezioni-preview, non il testo integrale), su una cartella di duecento documenti si arrivava nell'ordine di cinquecentomila-seicentomila token di input piu' i token di output per le skill estratte. Il costo non era astronomico, ma era variabile, difficile da prevedere prima del run, e soprattutto non necessario: come si vedra' nella sezione successiva, esisteva un modo per fare la stessa analisi usando la quota della sessione Claude Code inclusa nel piano Team, a costo marginale zero.

Il terzo problema era operativo e riguardava il ruolo ipotizzato di Claude.ai Projects nella fase di supervisione. L'idea era di caricare i file Markdown della tassonomia e un campione di .docx nella knowledge base del progetto, e usare le istruzioni di progetto per mantenere path e convenzioni tra conversazioni diverse. Il problema concreto era che Claude.ai non può scrivere file sul filesystem locale dell'utente. "Aggiornamento in-place" dei Markdown significava che il modello avrebbe generato il contenuto aggiornato come testo nella chat, e l'utente avrebbe dovuto copiarlo manualmente nel file corrispondente sul disco. Per una tassonomia con 29 Capability su 7 Domain, quel copia-incolla manuale sarebbe diventato rapidamente il collo di bottiglia dominante dell'intero processo, vanificando l'automazione.

# Il cambio di paradigma

## L'integrazione con lettore-doc

La prima svolta concettuale è stata la realizzazione che la pipeline di estrazione skill non andava costruita accanto a lettore-doc, ma sopra di esso. Il legame tra i due progetti era molto più forte di quanto sembri a prima vista, e la risposta è netta: non vanno tenuti separati, e nemmeno semplicemente "accostati". Il lettore-doc è esattamente l'infrastruttura che la pipeline-tassonomia descrive come "Fase 1" e parte della "Fase 2 / 3", ma scritta meglio di quanto verrebbe ricostruita da zero. Costruire un secondo pipeline parallelo sarebbe stato un raddoppio di codice senza guadagno tecnico. La pipeline prevedeva quattro fasi: estrazione testo (extract.py), normalizzazione della tassonomia, estrazione skill via API Claude in batch (analyze.py), merge nei markdown (merge.py). Le prime due fasi e mezza erano già implementate nel lettore-doc-intrawelt, e in modo notevolmente più robusto di quanto serva costruire da zero.

Il progetto conteneva gia' un parser .docx che non era un semplice estrattore di testo grezzo, ma un sistema a tre livelli di disclosure progressiva concepito precisamente per il problema del volume in relazione alla finestra di contesto. Il primo livello, lo scheletro, estrae solo la gerarchia di intestazioni e i conteggi per sezione: un intero documento di sessanta pagine diventa un oggetto JSON di cinquanta-duecento token. Una cartella di duecento documenti si riduce quindi a un oggetto navigabile di 20-30k token, meno del 15% della finestra di contesto disponibile, che può essere caricato interamente per dare al modello una panoramica completa del corpus prima ancora di scendere nel dettaglio di un singolo file.

Il secondo livello, la sezioni-preview, aggiunge per ogni sezione del documento i primi duecento caratteri e gli ultimi cento: abbastanza per capire di cosa parla quella sezione e se vale la pena leggerla integralmente, senza consumare i token necessari a leggerla per intero. Il terzo livello, la sezione completa on demand, viene attivato solo quando si deve rispondere a una domanda precisa su un contenuto specifico. Il documento originale del piano a quattro script avvertiva esplicitamente: "se i .docx sono molto lunghi, nella fase di analisi potresti dover troncare o suddividere il testo". La soluzione a quel problema era gia' implementata nel sistema esistente, e non richiedeva alcun chunking aggiuntivo: richiedeva semplicemente di usare la disclosure progressiva come aveva sempre fatto il parser.

Analogamente, extract_entities.py gia' riconosceva dieci categorie di entità tramite espressioni regolari[^9] calibrate per l'italiano tecnico-amministrativo: ragioni sociali con suffisso societario, riferimenti normativi come D.Lgs o Regolamenti UE, codici progetto alfanumerici con separatore, acronimi aziendali, date, importi in euro, indirizzi email, URL, e riferimenti espliciti ad altri documenti. Questo non era un sistema di Named Entity Recognition[^10] basato su machine learning, ma un'euristica deterministica che produceva output identico a ogni esecuzione sullo stesso input. Passare queste entità come contesto aggiuntivo al modello di analisi delle skill aumentava significativamente la precisione della classificazione: sapere che un documento conteneva acronimi come DURC, RTI, capitolato, SAL indicava immediatamente al modello che il contesto era quello degli appalti pubblici italiani, e questo cambiava quali skill era sensato cercare in quel documento.

Inoltre, build_knowledge_graph.py produce un grafo di relazioni tra documenti. Questo non serve direttamente all'estrazione skill, ma serve a un passo successivo che il documento originale di proposta non considera: una volta che hai mappato skill → documenti, il grafo già esistente ti dice automaticamente quali documenti parlano dello stesso progetto, e quindi quali "evidenze di skill" vanno aggregate (non vuoi che la stessa competenza esercitata in un singolo progetto, raccontata in cinque documenti diversi, venga contata cinque volte come "skill ricorrente").

## La scoperta di graphify: eliminare il costo API

La seconda svolta è stata l'introduzione di graphify[^11], che ha risolto il problema del costo delle chiamate API in modo strutturale anzichè ottimizzativo. graphify è uno strumento che gira all'interno di Claude Code come skill registrata: non è uno script esterno che chiama l'API Anthropic, ma un componente che usa direttamente il modello attivo nella sessione corrente di Claude Code. Nel caso di un piano Team, questo significa che l'elaborazione avviene all'interno della quota inclusa nel piano, senza costi aggiuntivi per token. La differenza non è di scala ma di natura: dove il piano originale prevedeva costi variabili proporzionali al volume del corpus, graphify trasforma il costo in un consumo della sessione attiva, che per un piano Team è gia' prepagato.

Inoltre, se la variabile ANTHROPIC_API_KEY è settata sul PC, Claude Code la userà al posto della subscription, e addebita le chiamate API anche se si ha un piano Team Premium.

Il funzionamento tecnico di graphify è il seguente. Riceve come input una cartella del filesystem, converte automaticamente i file .docx in Markdown tramite python-docx, legge direttamente i file .txt e .md, e analizza le immagini .png e .jpg in modalita' vision per estrarne il contenuto testuale rilevante, utile per diagrammi con etichette e screenshot di configurazioni. Usa il modello Claude attivo nella sessione per costruire un grafo semantico dei concetti e delle relazioni contenuti nei documenti. Ogni nodo del grafo rappresenta un concetto o un documento; ogni arco rappresenta una relazione, classificata come esplicita quando deriva da una citazione diretta presente nel testo, o inferita quando il modello identifica una connessione semantica tra nodi. Le relazioni inferite ricevono un punteggio di confidence che indica il grado di certezza del modello nella sua identificazione.

L'output di graphify è composto da quattro file. Il graph.json contiene il grafo strutturato in formato machine-readable, con per ogni nodo il label originale, il label normalizzato in inglese, l'identificatore della community di appartenenza, e il percorso del file sorgente. Il graph.html è una visualizzazione interattiva del grafo con layout force-directed[^12]: i nodi si distribuiscono nello spazio in base alle loro connessioni, i cluster di nodi strettamente connessi si raggruppano visivamente, e i cosiddetti god nodes - i nodi con il maggior numero di archi in ingresso e uscita - emergono al centro delle rispettive community. Il GRAPH_REPORT.md è un'analisi testuale prodotta dal modello che elenca i nodi piu' connessi, le relazioni inaspettate, le domande che il grafo suggerisce di esplorare ulteriormente. Il manifest.json registra gli hash dei file processati e consente la modalita' incrementale --update: alla seconda esecuzione, graphify processa solo i file il cui hash è diverso dal run precedente, riducendo drasticamente il consumo di token per corpus in prevalenza invariati.

Un aspetto particolarmente rilevante è che graphify produce i label dei nodi in inglese anche quando i documenti sorgente sono in italiano. Questo non è un difetto ma una caratteristica deliberata che si rivela preziosa in questo contesto: la tassonomia pubblica è in inglese per ragioni di posizionamento professionale internazionale, e avere label gia' in inglese come output dell'estrazione semplifica enormemente la fase di classificazione verso la tassonomia, eliminando la necessita' di un passaggio di traduzione intermedio.

### Prima prova con graphify

#### Installazione graphify

Innanzitutto, si può andare su https://claude.ai/settings/billing e verificare se si è "Premium seat"  dove è incluso Claude Code non è incluso e la roadmap non parte. Parallelamente: echo $env:ANTHROPIC_API_KEY su PowerShell, deve restituire vuoto. Se non lo è, va rimosso dalla configurazione utente ([Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", $null, "User")) per capire con quale account ti autentichi quando lanci claude da terminale. Se è il tuo account personale Pro/Max, allora il consumo è sul tuo budget personale e graphify lavora senza problemi ma sotto i tuoi limiti (considerando che Pro è abbastanza stretto per processare centinaia di docx).

Ad esempio, Claude Code 2.1.142, Opus 4.7 con contesto 1M, autenticato come membro del Team Intrawelt funziona ma sui token si ha budget limitato, quindi è ancora più importante limitare /graphify ai run strettamente necessari.

Quindi va fatto il login con l’account Team e installato graphifycon [office] per supporto .docx. Poi si farà il test rapido su una cartella esempio con pochi docx per validare che l'estrazione funzioni in italiano (graphify non è specializzato per italiano, è importante vedere cosa intercetta).

Si può verificare intanto se c’è pipx (se non si è mai usato no):
pipx --version

Se restituisce errore "non riconosciuto", installa pipx prima di tutto (powershell):
python -m pip install --user pipx
python -m pipx ensurepath

Chiudere e riaprire il terminale dopo ensurepath per ricaricare il PATH.

Installare graphify con extras office in un colpo solo:
pipx install "graphifyy[office]"

Le virgolette sono obbligatorie su PowerShell (le parentesi quadre vengono altrimenti interpretate). Con una sola invocazione: installa il pacchetto base + il supporto .docx/.xlsx. Si può quindi registrare la skill in Claude Code (versione Windows):
graphify install --platform windows
questo praticamente scrive SKILL.md nelle posizioni che Claude Code legge automaticamente cosicchè, da quel momento in poi /graphify diventa un comando riconosciuto dentro la sessione claude.

Per verificare si può fare:
pipx list
che ha avuto come output:
venvs are in C:\Users\Utente\pipx\venvs
apps are exposed on your $PATH at C:\Users\Utente\.local\bin
manual pages are exposed at C:\Users\Utente\.local\share\man
   package graphifyy 0.8.14, installed using Python 3.13.1
    - graphify.exe
e poi il comando:
graphify –version
che ha come output atteso qualcosa come “graphify 0.8.14” e poi:
graphify install --platform windows
che ha avuto come output:
skill installed  ->  C:\Users\Utente\.claude\skills \graphify\SKILL.md

CLAUDE.md        ->  created at C:\Users\Utente\.claude\CLAUDE.md

Done. Open your AI coding assistant and type:
/graphify

A questo punto, per il motivo descritto sopra, non è stato necessario lanciare /graphify da nessuna parte. Il primo run reale lo si farà nella fase successiva, su una cartella sorgente piccola e selezionata, in modo da contenere il consumo token.
……….

#### Test condotto

Il test condotto su un corpus di 39 file di documentazione tecnica relativa a Git e GitHub, per un totale di circa 126k parole, ha prodotto 66 nodi, 63 archi e 21 community, consumando 113k mila token in input e 29k in output. La distribuzione tra entità estratte da citazioni esplicite e relazioni inferite dal modello era rispettivamente del quarantotto per cento e del cinquantadue per cento, con una confidence media sulle inferenze di 0.85, un valore che nella pratica indica una qualita' di estrazione superiore a quella ottenibile con soli pattern testuali.

### Riflessione sull'integrazione di graphify con lettore-doc e sovrapposizione di scopo

Siccome graphify e lettore-doc hanno una sovrapposizione di scopo significativa: entrambi prendono cartelle di docs e producono un grafo di relazioni si sono anche comprese le differenze per poi proseguire con una scelta di integrazione.

Il lettore-doc è specializzato per italiano aziendale (regex specifiche per ragioni sociali, riferimenti normativi italiani, codici progetto), produce un vault Obsidian con disclosure progressiva a tre livelli token-efficient, ed è scritto da te quindi modificabile chirurgicamente. graphify è general-purpose ma molto più maturo (47k stars, versionamento attivo, multi-piattaforma), ha già un sistema MCP server per query strutturate, ha visualizzazione HTML interattiva nativa, e si integra direttamente con Claude Code senza che noi scriviamo prompt engineering.

La scelta migliore di integrazione è graphify come motore di estrazione semantica, lettore-doc come libreria di euristiche italiane: questo è il punto in cui i due strumenti si compongono in modo non ridondante. graphify legge i .docx sorgente dentro Claude Code e produce graph.json con entità + relazioni semantiche. Uno script nostro (che eredita le regex italiane di extract_entities.py) legge graph.json e arricchisce/disambigua le entità riconosciute applicando il post-processing italiano. Poi export_to_taxonomy.py mappa il risultato sulle Capability di skills -repo.

In questo modo: graphify fa la parte costosa (parsing semantico via LLM) usando la quota Team Premium di Claude Code con zero costi aggiuntivi. La specializzazione italiana sopravvive come layer di post-processing. Il vault Obsidian che lettore-docgenera continua a esistere come "vista privata" per te in locale; il sito pubblico MkDocs è l'output verso l'esterno.

Ci sarà anche un quarto utilizzo, ortogonale e gratis: lanciare graphify anche su skills stesso, dentro Claude Code, per generare un grafo visivo navigabile delle Capability/Domain del sito pubblico. Il graph.html risultante diventa una pagina extra del sito MkDocs ("Knowledge Graph") che mostra al recruiter una visualizzazione interattiva della struttura. È valore aggiunto al portfolio.

Difatti, una delle scoperte piu' interessanti avvenute durante lo sviluppo e' che graphify puo' essere usato non solo per analizzare le cartelle di documentazione privata, ma anche per costruire una visualizzazione interattiva della tassonomia stessa (Il Knowledge Graph come asset statico del sito). Lanciando /graphify docs/ all'interno di una sessione Claude Code aperta nella root di skills-repo, graphify legge i file Markdown delle ventinove Capability e costruisce un grafo delle loro relazioni semantiche: le Capability che condividono tecnologie, responsabilita' operative o approcci metodologici risultano connesse, e i cluster che emergono riflettono aree di trasversalita' del profilo professionale che la struttura gerarchica della tassonomia da sola non renderebbe visibili.

### Riflessione sul vincolo "tutto sempre aggiornato"

Lo scopo finale che hai ribadito ha tre componenti che vanno tenute insieme:
skills sempre aggiornato,
capacità di leggere documenti enormi da più cartelle,
tutto incrementale. graphify nativamente supporta --update (re-estrae solo i file modificati)
e ha git hooks (graphify hook install) che ricostruiscono dopo ogni commit. lettore-docha già la modalità incrementale via hash. Quindi entrambi gli strumenti soddisfano già il requisito di aggiornamento incrementale, e basta orchestrarli.

Per le 5+ cartelle sorgente: graphify accetta un path per invocation. La strategia è una sources.yml letta da uno script orchestratore che cicla sulle sorgenti, lancia graphify su ognuna, e accumula i graph.json risultanti. Oppure (preferibile) graphify ha il comando merge-graphs a.json b.json --out merged.json che fonde i grafi di run diversi. Quindi il pipeline diventa: ciclo sulle sorgenti → graphify per ciascuna → merge dei graph.json → post-processing italiano → mapping su taxonomy.

## La separazione pubblico e privato come requisito ingegneristico

La terza svolta è stata la piu' importante sul piano architetturale, perchè ha ridefinito non solo come costruire il sistema ma cosa esso fosse. La tassonomia di competenze non è un artefatto interno del progetto di analisi: è il prodotto pubblico finale. Questo cambia la natura del problema in modo sostanziale. Non si tratta di estrarre skill e scriverle in qualche file, si tratta di costruire un sistema che attraversa un confine di dominio: da un lato il dominio privato con tutti i dati sensibili, dall'altro il dominio pubblico che deve contenere esclusivamente informazioni che possono essere viste da chiunque.

Il passaggio tra i due domini richiede un passo di sanitizzazione esplicito e verificabile. La logica adottata è la seguente: lo script enrich_graph.py, che elabora il graph.json prodotto da graphify, costruisce durante il suo funzionamento una anonymization_map, un dizionario che associa ogni ragione sociale e ogni nome proprio identificato nel corpus al suo placeholder anonimizzato. Le aziende vengono sostituite con [AZIENDA_1], [AZIENDA_2] e cosi' via, ordinate dalla piu' citata alla meno citata. I nomi propri diventano [PERSONA_1], [PERSONA_2]. Questa mappa viene salvata all'interno del enriched_graph.json e viene applicata da export_to_taxonomy.py prima di scrivere qualsiasi testo nelle pagine del sito pubblico. Il testo che raggiunge il repository pubblico è quindi strutturalmente garantito privo di qualsiasi riferimento identificativo, indipendentemente da quanto specifico fosse il testo estratto dal documento originale.

# Le decisioni architetturali chiave

## Due repository fisicamente separati

La decisione di usare due repository Git distinti invece di un monorepo con sottocartelle e .gitignore[^13] complesso è motivata da una considerazione di sicurezza strutturale. Con un monorepo, la garanzia che contenuto privato non finisca nel repository pubblico dipende dalla correttezza del file .gitignore e dalla disciplina dell'operatore nel momento del commit. Entrambi sono fattori cognitivi soggetti a errore. Un merge sbagliato, un git add . eseguito dalla directory sbagliata, una GitHub Action configurata male possono esporre _intermediate/ o il vault Obsidian a un repository pubblico. Con due repository fisicamente separati, questa possibilita' è eliminata per costruzione: il repository pubblico non vede mai file che non siano stati esplicitamente scritti dallo script ponte dopo la sanitizzazione. Non c'è nessuna configurazione da ricordare, nessuna regola da applicare manualmente, nessun rischio di sbagliare.

Il repository privato alesop95/lettore-doc risiede fisicamente su E:\lettore-doc\ e contiene tutto il codice degli script, la configurazione delle sorgenti in sources.yml, la documentazione tecnica, le istruzioni per Claude Code in CLAUDE.md, l'ambiente Python isolato in .venv\[^14], e le due cartelle rigenerabili escluse dal controllo di versione: _intermediate\ per i dati di lavoro e vault-output\ per il vault Obsidian privato. Il repository pubblico alesop95/skills risiede su J:\...\skills-repo\ e contiene esclusivamente i file Markdown della tassonomia, il file di configurazione mkdocs.yml, il workflow GitHub Actions per il deploy, e il file CLAUDE.md con le istruzioni operative per le sessioni Claude Code aperte in quella cartella.

La motivazione contro il monorepo è semplice: con .gitignore complessi o con la pubblicazione di una sottocartella tramite GitHub Actions, basta un merge sbagliato o una configurazione errata del workflow per esporre _intermediate/ o il vault. Il costo cognitivo del "ricordarsi sempre cosa si può committare" diventa una superficie di rischio inutile quando la soluzione a due repo lo azzera per costruzione.

## Le variabili di ambiente per i path sensibili

I path assoluti delle cartelle sorgente e del repository pubblico - percorsi come C:\Users\Utente\OneDrive - Azienda\Documenti-IT oppure J:\googleDrive_sync\...\skills-repo - non devono mai essere scritti nei file committati nel repository, nemmeno in quello privato. Un repository Git, anche privato, può essere clonato su macchine diverse, condiviso con collaboratori, esportato come backup, migrato su un nuovo server. In tutti questi casi, un path hardcoded diventa immediatamente un problema di portabilita' e, nel caso di percorsi che includono nomi di organizzazioni o strutture di rete interne, un potenziale vettore di esposizione di informazioni.

La soluzione adottata è l'uso di variabili di ambiente di sistema, scritte nel registro di Windows[^15] tramite il comando PowerShell SetEnvironmentVariable con scope "User". Queste variabili vengono lette dagli script Python tramite la funzione os.path.expandvars() della libreria standard, che sostituisce le occorrenze di ${NOME_VARIABILE} all'interno di un percorso con il valore effettivo registrato nel sistema. Il file sources.yml contiene quindi path nella forma ${LETTERDOC_SOURCE_ONEDRIVE} anzichè il percorso reale, ed è perfettamente committabile senza esporre informazioni sensibili. Il file .env.example, anch'esso committato, documenta quali variabili devono essere settate e le istruzioni per farlo, senza contenere i valori reali. Il file .env locale, che può contenere i valori come promemoria, è escluso dal repository tramite .gitignore. La generazione dello script generate_taxonomy_index.py legge automaticamente il path di skills-repo dalla chiave skills_repo: di sources.yml, con fallback alla variabile di ambiente LETTERDOC_SKILLS_REPO se la chiave non è presente. Questo rende l'invocazione dello script priva di parametri obbligatori nella maggior parte dei casi d'uso.

```
# sources.yml - nessun path reale nei file committati
sources:
  - path: "${LETTERDOC_SOURCE_ONEDRIVE}"
    label: documenti_it
    include_extensions: [.docx, .txt, .md]
    exclude_patterns: ["~$*", "_archive/*"]

  - path: "${LETTERDOC_SOURCE_PORTFOLIO}"
    label: portfolio_it
    include_extensions: [.docx, .txt, .md]
    exclude_patterns: ["~$*"]

skills_repo: "${LETTERDOC_SKILLS_REPO}"

```
Le variabili vengono settate una sola volta per macchina con i seguenti comandi PowerShell. Una volta scritte nel registro, sono disponibili permanentemente in tutte le sessioni future senza necessita' di ripetere l'operazione.

```
[System.Environment]::SetEnvironmentVariable(
    "LETTERDOC_SKILLS_REPO",
    "J:\...\skills-repo",
    "User"
)

[System.Environment]::SetEnvironmentVariable(
    "LETTERDOC_SOURCE_ONEDRIVE",
    "C:\Users\Utente\OneDrive - Azienda\Documenti-IT",
    "User"
)

# Verifica nella stessa sessione (refresh manuale necessario):
$env:LETTERDOC_SKILLS_REPO = [System.Environment]::
    GetEnvironmentVariable("LETTERDOC_SKILLS_REPO", "User")

```

## Lo schema fisso a quattro sezioni per ogni Capability

La tassonomia di competenze pubblicata su skills-repo è organizzata in ventinove pagine Capability distribuite su sette Domain. Ogni pagina è un file Markdown con quattro sezioni H2 in ordine invariato. La prima sezione, Overview, è una prosa di tre-sei righe scritta manualmente che descrive in cosa consiste la Capability e perchè è rilevante: è il testo che legge per primo un recruiter o un interlocutore tecnico, ed è l'unico elemento della pagina che richiede una voce umana consapevole del contesto professionale specifico. La seconda sezione, Technologies & tools, è un elenco delle tecnologie specifiche con versioni precise quando rilevanti e una qualificazione contestuale in poche parole. La terza sezione, Responsibilities & operational scope, elenca le responsabilita' operative coperte dalla Capability. La quarta sezione, Projects & evidence, è quella popolata automaticamente dagli script: contiene un sottotitolo H3 per ogni evidenza progettuale estratta dalla documentazione sorgente, con testo anonimizzato che descrive scopo, architettura e outcome del progetto.

La tassonomia è strutturata correttamente come scheletro - cartelle per Domain, file per Capability, mkdocs.yml ben configurato con tema Material, navigazione esplicita, use_directory_urls lasciato al default che produrrà URL puliti del tipo alesop95.github.io/skills /networking-engineering-security/. Lo scheletro funziona. Quello che c'è dentro le pagine è invece a uno stadio molto preliminare di curazione, e va riconosciuto chiaramente perché determina cosa si può pubblicare subito e cosa no.

Lo schema fisso non è una scelta estetica ma un requisito funzionale per lo script export_to_taxonomy.py. Questo script deve sapere con certezza dove iniettare le evidenze progettuali senza dover inferire la struttura della pagina a ogni esecuzione: cerca il titolo ## Projects & evidence e appende il nuovo contenuto immediatamente prima della fine del file. Se la struttura della pagina fosse variabile, ogni iniezione richiederebbe logica di parsing aggiuntiva e introdurrebbe potenziali errori in caso di pagine formattate in modo non standard. Lo schema fisso rende l'iniezione deterministica e tollerante a qualsiasi contenuto presente nelle altre tre sezioni.

## L'idempotenza come requisito non negoziabile

Qualsiasi script che scrive in un repository deve essere eseguibile piu' volte sullo stesso input senza produrre duplicati. Questa proprieta', chiamata idempotenza, è particolarmente critica in un sistema in cui lo stesso script viene eseguito periodicamente su corpus che si aggiornano incrementalmente: è inevitabile che alcune evidenze progettuali siano gia' presenti nel file Markdown di destinazione quando si rilancia il pipeline su un corpus che include documenti gia' processati in precedenza.

La soluzione adottata usa i commenti HTML, che sono invisibili nel rendering del sito ma conservati nel sorgente Markdown. Ogni H3 iniettato da export_to_taxonomy.py include immediatamente sotto il titolo un commento HTML con un identificatore stabile e univoco:

```
### Proxmox VE Cluster Migration
<!-- graphify-evidence-id: abc123def456 -->

- **Source**: `2026-migration-server.md`
- **Graph community**: Infrastructure & Virtualization

Implementazione di un cluster Proxmox VE a tre nodi per un cliente
del settore manifatturiero, con configurazione High Availability...

```
L'identificatore è il SHA-256[^16] breve, ridotto ai primi dodici caratteri, della concatenazione di node_id e capability_slug. Prima di iniettare qualsiasi nuova evidenza, lo script legge il contenuto attuale del file di destinazione e cerca la presenza dell'identificatore come sottostringa. Se l'identificatore è gia' presente, l'evidenza viene saltata. Se è assente, viene iniettata. Il comando export_to_taxonomy.py --apply può quindi essere eseguito anche dieci volte sullo stesso taxonomy_diff.json senza alterare il risultato rispetto alla prima esecuzione andata a buon fine.

# L'architettura finale

## Il flusso di dati completo

Il flusso di dati tra i componenti del sistema segue una sequenza deterministica in cui ogni fase riceve il suo input dal file prodotto dalla fase precedente, elabora, e scrive il suo output su disco prima che la fase successiva inizi. Questo design, basato su file intermedi in formato JSON leggibili e modificabili a mano, rende il sistema ispezionabile in ogni suo stato: se una fase produce un risultato inatteso, si può aprire il file intermedio corrispondente, verificarne il contenuto, eventualmente correggerlo, e riprendere dall'output corretto senza dover riprocessare le fasi precedenti.

```
Cartelle sorgente (.docx, .txt, .md, .png)
        |
        |  /graphify . (Claude Code, quota Team)
        v
graphify-out/graph.json  +  graph.html  +  GRAPH_REPORT.md
        |
        |  enrich_graph.py (offline, zero token)
        v
_intermediate/enriched_graph.json  +  anonymization_map
        |
        +------------- generate_taxonomy_index.py
        |               (legge skills-repo/mkdocs.yml)
        |                        |
        |              _intermediate/taxonomy_index.json
        |
        |  map_to_taxonomy.py (recall score, soglie 0.15 / 0.08)
        v
_intermediate/taxonomy_diff.md  <--  REVISIONE MANUALE
_intermediate/taxonomy_diff.json
        |
        |  export_to_taxonomy.py --apply (offline, idempotente)
        v
skills-repo/docs/  (Capability .md aggiornati + nuovi file)
        |
        |  git push
        v

GitHub Actions  ->  mkdocs build --strict  ->  _site/
        |
        v
alesop95.github.io/skills/   (~1 minuto dal push)

```
Il punto di revisione manuale posizionato tra map_to_taxonomy.py e export_to_taxonomy.py è deliberato e non eliminabile senza compromettere la qualita' dell'output. Il matching automatico basato su recall[^17] produce inevitabilmente falsi positivi, specialmente quando il testo sorgente di un nodo è scarso (ad esempio un nodo proveniente da un file immagine con solo il titolo come testo estratto). La revisione del file taxonomy_diff.md prima di applicare le modifiche al repository pubblico è il punto in cui l'IT manager esercita il giudizio editoriale: cosa includere, cosa escludere, come nominare una nuova Capability, se un'area di competenza emergente merita una pagina propria o è meglio accorpata a una esistente.

## Gli otto script e i loro ruoli

### parse_docx.py

È il parser principale del corpus documentale. Implementa i tre livelli di disclosure progressiva tramite tre subcomandi distinti: skeleton per la sola struttura gerarchica con conteggi, sections-preview per gli estratti di duecento caratteri iniziali e cento finali per sezione, e full-section per il contenuto integrale di una sezione specifica on demand. Il riconoscimento delle intestazioni è duplice: stile assegnato in Word (Heading 1, Titolo 1 e varianti) oppure, come fallback, un pattern numerico in testa al paragrafo ("1.", "1.1", "1.1.1"). Questo fallback è necessario perchè la maggior parte dei documenti aziendali italiani usa numerazione manuale anzichè gli stili nativi. La parallelizzazione avviene tramite ProcessPoolExecutor[^18] con un numero di worker pari al minimo tra il numero di CPU disponibili e otto. La modalita' incrementale confronta l'hash SHA-256 dei primi duecentocinquantasei kilobyte di ciascun file con quello calcolato al run precedente e processa solo i file il cui hash è cambiato.

### extract_entities.py

Applica dieci categorie di espressioni regolari al testo estratto dai documenti. Le categorie sono: sigle aziendali da due a sette lettere maiuscole filtrate contro una stoplist di acronimi tecnici comuni (PDF, API, CSV, XML e simili); ragioni sociali con suffisso societario italiano ed estero (SpA, Srl, SaS, GmbH, Ltd e varianti); nomi propri di persona o entità; codici progetto in formato alfanumerico con separatore; riferimenti normativi italiani ed europei come D.Lgs, DPR, Regolamento UE; date in formati italiani, ISO e testuale; importi in euro; indirizzi email; URL; e riferimenti espliciti ad altri documenti nella forma "vedi specifica X.docx". Include un meccanismo di merge degli alias societari: "AlphaBeta SpA" e "AlphaBeta S.p.A." vengono ricondotte alla stessa entità tramite normalizzazione e confronto della chiave.

### build_knowledge_graph.py

Calcola il grafo di relazioni tra i documenti del corpus. Il peso di ogni arco è la somma ponderata di cinque componenti: la sovrapposizione di entità misurata con l'indice di Jaccard[^19] sulle categorie ACRONYM, COMPANY, PROPER_NOUN e PROJECT_CODE (peso 0.40); il numero di riferimenti espliciti da un documento all'altro saturato a un massimo di tre (peso 0.30); la vicinanza nella struttura di cartelle, con valore 1.0 per stessa cartella e 0.5 per cartella padre comune (peso 0.10); la vicinanza temporale tra le date di modifica, con 1.0 per date entro sette giorni e decrescita lineare fino a 0 a centottanta giorni (peso 0.10); e la similarita' tra i nomi dei file misurata tramite Jaccard sui token significativi, utile per riconoscere serie temporali come verbali mensili dello stesso progetto (peso 0.10). Ogni arco riceve anche un'etichetta semantica tra sei possibili - riferisce esplicitamente, serie temporale, stesso progetto, condivide entità chiave, topica affine, correlato debole - assegnata in ordine di priorita' decrescente del segnale.

### generate_vault.py

Produce il vault Obsidian privato nella cartella vault-output\. Per ogni documento del corpus genera un file Markdown con frontmatter YAML[^20] gerarchico che include tipologia del documento dedotta dal nome file, hash di origine, conteggi, entità principali, acronimi, riferimenti normativi, e tag gerarchici in stile Obsidian come #progetto/prj-001 o #azienda/alphabeta_spa. Il corpo del file include una sezione con la sintesi narrativa del documento se disponibile, l'indice delle sezioni con conteggio parole, la sezione "Documenti correlati" organizzata per etichetta semantica dell'arco con il peso numerico accanto a ogni link, e gli estratti per sezione con wiki-link inline automatici. La cartella _data\ dentro vault-output\ contiene copie di graph.json e entities.json per i plugin Obsidian come Dataview, che consente query di tipo SQL sul vault.

### enrich_graph.py

È il primo script della pipeline di estrazione skill. Riceve il graph.json prodotto da graphify e lo arricchisce con informazioni che graphify non estrae per la sua natura di strumento generico. Per ogni nodo del grafo risolve il percorso del file sorgente rispetto alla working directory, legge il testo disponibile, applica le stesse dieci categorie di espressioni regolari di extract_entities.py, e aggiunge al nodo i campi italian_entities (dizionario per categoria con valori e conteggi) e text_preview (i primi duecento caratteri del testo estratto). A livello di grafo costruisce poi l'anonymization_map: aggrega tutte le COMPANY e PROPER_NOUN trovate su tutti i nodi, le ordina per frequenza decrescente, e assegna placeholder numerati progressivamente.

### generate_taxonomy_index.py

Legge il file mkdocs.yml di skills-repo e costruisce un indice della tassonomia attuale. Per ogni Capability page elencata nella navigazione, legge il file Markdown corrispondente ed estrae le keyword significative dalle sezioni Technologies & tools e Overview. Il numero tipico di keyword estratte è tra trentasei e sessanta per Capability, a seconda della densita' del contenuto. Include inoltre keyword base per ogni Domain, usate come segnale di fallback quando nessuna Capability specifica supera la soglia di matching. Lo script risolve autonomamente il path di skills-repo leggendo la chiave skills_repo: di sources.yml tramite os.path.expandvars(), con fallback alla variabile di ambiente LETTERDOC_SKILLS_REPO. Il parametro --skills-repo da riga di comando rimane disponibile per override esplicito.

### map_to_taxonomy.py

Classifica ogni nodo del grafo arricchito rispetto alla tassonomia. Il meccanismo di classificazione usa il recall: per ogni coppia nodo-Capability, viene calcolata la proporzione dei token che descrivono il nodo presenti tra le keyword della Capability. I token del community label del nodo vengono aggiunti ai token del label del nodo per aumentare la copertura semantica. Se il recall supera 0.15, il nodo viene classificato come fit per quella Capability. Se nessuna Capability supera 0.15 ma almeno una keyword del Domain di una Capability ha una corrispondenza con recall maggiore di 0.08, il nodo viene proposto come new_capability in quel Domain. Se non c'è corrispondenza con nessun Domain, il nodo viene marcato come new_domain. Lo script produce sia il file taxonomy_diff.md pensato per la revisione umana, con sezioni per fit, new Capability, new Domain e nodi non classificati, sia il file taxonomy_diff.json con la stessa informazione in formato machine-readable per lo script successivo.

### export_to_taxonomy.py

È l'unico script che scrive nel repository pubblico. In modalita' --dry-run (che è il default) stampa l'elenco completo delle operazioni che eseguirebbe senza toccare nessun file: numero di evidenze da iniettare per Capability, nuovi file da creare per le new Capability accettate nella revisione, righe da aggiungere manualmente al mkdocs.yml. In modalita' --apply esegue effettivamente le operazioni. Per ogni fit, apre il file di destinazione, individua la sezione ## Projects & evidence, rimuove l'eventuale placeholder testuale, e inietta il blocco H3 con identificatore di idempotenza e testo anonimizzato tramite l'anonymization_map contenuta nell'enriched_graph.json. Per ogni new Capability accettata nella fase di revisione, crea il file Markdown con le quattro sezioni H2 standard e il testo iniziale di ciascuna. La modifica del mkdocs.yml per aggiungere le nuove pagine alla navigazione del sito non è automatizzata per scelta deliberata: il file di navigazione definisce la struttura pubblica del sito, e la modifica della struttura di navigazione deve essere un atto consapevole.

# Il Knowledge Graph come asset statico del sito

Una delle scoperte piu' interessanti avvenute durante lo sviluppo è che graphify può essere usato non solo per analizzare le cartelle di documentazione privata, ma anche per costruire una visualizzazione interattiva della tassonomia stessa. Lanciando /graphify docs/ all'interno di una sessione Claude Code aperta nella root di skills-repo, graphify legge i file Markdown delle ventinove Capability e costruisce un grafo delle loro relazioni semantiche: le Capability che condividono tecnologie, responsabilita' operative o approcci metodologici risultano connesse, e i cluster che emergono riflettono aree di trasversalita' del profilo professionale che la struttura gerarchica della tassonomia da sola non renderebbe visibili.

Il risultato pratico di questo utilizzo su skills-repo è un grafo di centoquarantuno nodi, centantacinque archi e quattordici community. I god nodes - le Capability con il maggior numero di connessioni in ingresso e uscita - che emergono da questa visualizzazione sono LLMs & Generative AI, Cybersecurity & IT Governance, Backup & Disaster Recovery e Ad-hoc Internal Development. La loro centralita' nel grafo non è una classificazione soggettiva, ma l'esito di un'analisi semantica che rileva oggettivamente quali competenze si manifestano in piu' contesti diversi all'interno del portfolio.

Il meccanismo con cui questo file diventa accessibile al pubblico merita una spiegazione tecnica specifica, perchè non è ovvio. MkDocs, durante la sua operazione di build, copia nella directory di output _site/ tutto il contenuto presente nella cartella docs/, indipendentemente dall'estensione del file. I file Markdown vengono convertiti in HTML con il tema Material applicato. Tutti gli altri file vengono copiati come asset statici[^21]: il server web li serve esattamente come sono su disco, senza nessuna elaborazione. Questo significa che un file docs/graphify-out/graph.html prodotto da graphify, che è un file HTML standalone contenente l'intero grafo interattivo con le sue librerie JavaScript incorporate, viene copiato da MkDocs in _site/graphify-out/graph.html durante la build e diventa accessibile come URL diretto:

| graphify produce docs/graphify-out/graph.html durante la sessione Claude Code. Questo file viene copiato dalla build MkDocs come asset statico durante il deploy automatico via GitHub Actions e diventa accessibile come URL diretto:  alesop95.github.io/skills/graphify-out/graph.html  Non è una pagina nel nav MkDocs (non ha un .md corrispondente), ma è un asset HTML standalone servito staticamente senza elaborazione da parte del generatore di siti. |
|---|
Questo URL è inseribile direttamente nel curriculum vitae come "visualizzazione interattiva delle competenze". Chi lo apre vede un grafo navigabile con nodi cliccabili, filtri per community, ricerca dei nodi, e informazioni di dettaglio per ogni Capability. È un formato di presentazione che trasmette un'informazione qualitativa - la struttura delle relazioni tra competenze - che nessun elenco o tabella potrebbe rappresentare con altrettanta efficacia.

Dal punto di vista operativo, questo utilizzo di graphify su docs/ non va eseguito ad ogni aggiornamento del contenuto delle Capability: va eseguito quando la struttura della tassonomia cambia in modo significativo, cioè quando vengono aggiunte nuove Capability, riorganizzati i Domain, o quando si vuole che il grafo rifletta l'evoluzione del profilo. Il file graph.html prodotto è committato nel repository (insieme a GRAPH_REPORT.md), mentre tutti gli altri file intermedi di graphify (.graphify_*, la cartella converted/, i file .json) sono esclusi dal controllo di versione tramite .gitignore. La build GitHub Actions li ignora perchè non sono presenti nel repository, e il sito pubblicato contiene solo il graph.html che è gia' un file completamente autonomo, senza dipendenze esterne.

# L'implementazione: storia cronologica

## Fase A - Setup del sito pubblico e primo deploy

Il lavoro è iniziato da skills-repo anzichè da lettore-doc, perchè avere il sito online prima di popolarlo consentiva di validare immediatamente ogni modifica tramite l'URL pubblico. La tassonomia esisteva gia' come insieme di file Markdown parzialmente strutturati, ma con qualita' editoriale disomogenea: alcuni file erano completi con sezioni H2 sviluppate, altri contenevano solo uno scheletro con placeholder espliciti, altri erano praticamente vuoti. Il primo intervento è stato applicare lo schema fisso a quattro H2 a tutte le ventinove pagine Capability, rimuovere i placeholder, e uniformare la lingua in inglese. Questo ha richiesto lavoro editoriale manuale, ma è stata un'operazione da fare una sola volta per costruire la base stabile su cui il sistema avrebbe lavorato automaticamente in seguito.

La configurazione del workflow GitHub Actions ha richiesto tre iterazioni per funzionare correttamente. Il problema iniziale era che la fonte di pubblicazione di GitHub Pages era impostata su "Deploy from a branch" nelle Settings del repository, anzichè su "GitHub Actions". Quando si usa un workflow che genera autonomamente il sito tramite mkdocs build e lo pubblica tramite l'action actions/deploy-pages, è necessario che la fonte sia impostata su "GitHub Actions": in caso contrario, GitHub cerca un branch da cui servire i file statici e non trova nessun output, o serve il sorgente Markdown invece dell'HTML generato. Il cambio di impostazione nelle Settings del repository ha risolto immediatamente il problema, e il sito è andato online al successivo push sul branch main.

## Fase B - Anonimizzazione del codice e setup di lettore-doc

Prima di mettere lettore-doc sotto controllo di versione, è stato necessario verificare sistematicamente che nessun file del progetto contenesse riferimenti aziendali che non avrebbero dovuto essere committati nemmeno in un repository privato. La ricerca ha identificato sei file con occorrenze del nome aziendale specifico o del nome originale del progetto: run_pipeline.sh, run_pipeline.ps1, generate_vault.py, lettore-documentazione.md, SKILL.md e enrich_graph.py. Le occorrenze erano nei banner di output del terminale, nei commenti del codice, nei titoli dei template generati dal vault, e nei path di esempio nella documentazione degli script. Tutte sono state sostituite con riferimenti generici. La modifica era chirurgica: nessuna logica applicativa è stata alterata, solo stringhe di testo non significative per il funzionamento del codice.

I quattro nuovi script della pipeline di estrazione skill (enrich_graph.py, generate_taxonomy_index.py, map_to_taxonomy.py, export_to_taxonomy.py) sono stati scritti e integrati nella struttura di lettore-doc. Il requirements.txt è stato aggiornato con pyyaml>=6.0.0 come nuova dipendenza, necessaria per la lettura del mkdocs.yml in generate_taxonomy_index.py. Il file CLAUDE.md è stato scritto per lettore-doc e un secondo per skills-repo: questi file vengono letti automaticamente da Claude Code all'avvio di ogni sessione aperta nella rispettiva cartella, e contengono le regole operative del sistema, i comandi principali, e i vincoli di sicurezza. Grazie a loro, ogni sessione Claude Code parte gia' allineata al contesto corretto senza consumare token per ri-spiegare l'architettura.

Il setup delle variabili di ambiente su Windows ha richiesto un passaggio in piu' rispetto a quanto previsto. Il comando SetEnvironmentVariable scrive correttamente nel registro di Windows, ma le variabili diventano disponibili solo nelle sessioni PowerShell aperte dopo la scrittura: la sessione corrente, aperta prima del set, non le vede. Questo comportamento è corretto e documentato ma controintuitivo. La soluzione per la sessione corrente è un refresh manuale che legge dal registro e popola le variabili nella sessione attiva tramite [System.Environment]::GetEnvironmentVariable() con scope "User". Dalla sessione successiva in poi il problema non si ripresenta.

## Fase C - Installazione di graphify e test della pipeline
graphify si installa tramite pipx install "graphifyy[office]". Il suffisso [office] installa le dipendenze necessarie per elaborare file Office, incluso python-docx per i .docx. La registrazione della skill in Claude Code avviene con graphify install --platform windows: questo comando scrive la definizione della skill nei file di configurazione di Claude Code, rendendo disponibile il comando /graphify in tutte le sessioni successive. Il test condotto su un corpus di trentanove file ha confermato le stime teoriche: il run è completato in poco piu' di un minuto, producendo un grafo di qualita' adeguata per la fase di classificazione.

Prima di eseguire l'installazione, e' stato necessario verificare due condizioni che determinano se graphify funzionera' all'interno della quota Team o se invece addebitera' i token come chiamate API a pagamento. La prima verifica e' stata sull'account Anthropic stesso: collegandosi a claude.ai/settings/billing e' stato confermato che l'utente ha un Premium seat all'interno di un piano Team, condizione necessaria perche' Claude Code possa funzionare con la quota inclusa. La seconda verifica, piu' insidiosa, e' stata sulla variabile di ambiente ANTHROPIC_API_KEY: se questa variabile e' settata nel sistema, Claude Code la usa di default per autenticarsi anziche' usare la subscription, e ogni chiamata viene addebitata sul billing API anche quando l'utente ha un piano Team Premium attivo. Il comando di verifica e' stato echo $env:ANTHROPIC_API_KEY in PowerShell: il valore restituito deve essere vuoto. Se non lo fosse, andrebbe rimossa con [Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", $null, "User") prima di procedere.

Su questa macchina specifica il modello di Claude Code installato era Opus 4.7 con contesto da un milione di token. Per estrazione di entita' e relazioni su un corpus contenuto, Opus e' sovradimensionato e consuma circa cinque volte i token di Sonnet a parita' di lavoro. La scelta operativa e' stata quindi di switchare a Sonnet 4.5 per il test, mantenendo Opus disponibile per operazioni successive che richiedano effettivamente piu' contesto o capacita' di ragionamento.

L'installazione vera e propria di graphify avviene tramite pipx, lo strumento per installare applicazioni Python in ambienti isolati senza inquinare l'interprete di sistema. Il primo passaggio e' stato verificare la disponibilita' di pipx con pipx --version: in caso di assenza, il setup richiede l'installazione preliminare via python -m pip install --user pipx seguita da python -m pipx ensurepath per registrare i binari nel PATH dell'utente. Dopo questa operazione e' necessario chiudere e riaprire il terminale, altrimenti la variabile PATH della sessione corrente non viene aggiornata.

Con pipx funzionante, l'installazione di graphify e' avvenuta con un singolo comando: pipx install "graphifyy[office]". Le virgolette sono obbligatorie su PowerShell perche' le parentesi quadre del suffisso office vengono altrimenti interpretate dalla shell come operatori di array. Il suffisso office aggiunge le dipendenze per il parsing di file Microsoft Office (.docx, .xlsx) tramite python-docx e openpyxl. La registrazione della skill in Claude Code e' avvenuta con graphify install --platform windows: questo comando scrive un file SKILL.md in C:\Users\Utente\.claude\skills\graphify\, che Claude Code legge automaticamente all'avvio di ogni sessione, e da quel momento il comando /graphify diventa riconosciuto e invocabile.

La verifica finale dell'installazione e' stata fatta con pipx list, che ha confermato la presenza del pacchetto graphifyy 0.8.14 installato con Python 3.13.1 nel venv pipx, e con graphify --version, che ha restituito "graphify 0.8.14" come atteso. Dopo questi passaggi graphify era pronto all'uso, ma non e' stato lanciato immediatamente: il primo run reale avrebbe consumato token della quota Team e andava fatto con criterio, su una cartella accuratamente selezionata.

### Identificazione della cartella per il primo run

La selezione della cartella su cui eseguire il primo /graphify e' stata oggetto di riflessione esplicita, perche' il primo run e' un test di validazione della pipeline e non un'operazione di indicizzazione vera e propria. L'obiettivo era confermare che graphify funzionasse correttamente su documenti italiani, che producesse un grafo di qualita' adeguata, e che il consumo di token rientrasse nelle stime preliminari. Lanciarlo direttamente sulla cartella Documenti - IT di OneDrive (la sorgente principale del corpus aziendale, con centinaia di documenti) sarebbe stato prematuro e costoso.

La prima ipotesi era usare la cartella IT-RELATED del portfolio personale sotto Google Drive sync. Una rapida ispezione ha rivelato tre problemi che la rendevano inadatta come primo test. Il primo era di scope: il contenuto della cartella e' principalmente materiale di studio e di riferimento personale (appunti, screenshot, link bookmark, cheat sheet, configurazioni esportate, articoli salvati), non documentazione di realizzazione di progetti. Per la costruzione di una tassonomia di competenze basata su evidenze progettuali questa distinzione e' importante: avere un cheat sheet su una tecnologia non dimostra di averla applicata in produzione, e una tassonomia gonfiata di skill marginali estratte da materiale di studio diventerebbe meno credibile, non piu'.

Il secondo problema era di formato. Sul totale dei file della cartella, solo quattro erano effettivamente .docx; il resto era una mescolanza di .txt, .png, .url, .jpg, .7z, .json, .md, .xlsx, .html. graphify con il suffisso office gestisce correttamente .docx e .xlsx; legge nativamente .txt e .md; analizza .png e .jpg in modalita' vision, ma il costo in token e' elevato; ignora o gestisce male .url e .7z. In un primo test la varieta' di formati introdurrebbe rumore aggiuntivo non necessario.

Il terzo problema era di percorso: il nome della cartella conteneva un'emoji (🪟 in un sottopath dedicato a Windows). graphify e le librerie Python sottostanti generalmente reggono caratteri Unicode nei percorsi sotto Windows, ma il passaggio di un path con emoji attraverso PowerShell, Claude Code e i diversi strati di parsing di graphify introduce piu' superfici potenziali di rottura. Non era un blocker, ma in un test di validazione si vogliono eliminare le ambiguita' e debuggare un problema diverso da quello su cui ci si vuole concentrare.

La cartella scelta come primo test e' stata version-control-copy-prova, una copia in path ASCII puro di una cartella di documentazione tecnica su Git e GitHub contenuta originariamente sotto Ongoing studies/Full-stack development. Il contenuto era ideale per il primo test: trentanove file di documentazione tecnica (sedici .docx con case study e guide, tredici .txt con spiegazioni di comandi e note operative, dieci .png con diagrammi di workflow), per un totale di circa ventun megabyte e centoventiseimila parole. Tutti i documenti erano in italiano, scritti dall'utente come appunti e walkthrough durante l'apprendimento e l'uso quotidiano di Git, e quindi gia' rappresentativi della specie di documentazione che andra' processata in produzione.

### Il primo run di graphify

Il run e' stato eseguito da PowerShell con cd verso la cartella di test, claude per aprire una sessione Claude Code, /model claude-sonnet-4-5 per impostare il modello (importante: Sonnet, non Opus, per contenere il consumo), e infine /graphify .. graphify ha prodotto un piano di esecuzione dettagliato che enumerava i file rilevati, illustrava la strategia di estrazione (semantica con sotto-agenti paralleli, due o tre chunk da venti-venticinque file ciascuno), e stimava il consumo di token (centocinquantamila-duecentocinquantamila in input, trentamila-cinquantamila in output).

L'uscita dalla modalita' di pianificazione si fa con Shift+Tab per ciclare alla modalita' auto, seguito da Invio per confermare l'esecuzione. graphify ha quindi eseguito le sue cinque fasi (rilevamento, estrazione semantica, costruzione del grafo con clustering Louvain, etichettatura delle community, generazione dell'HTML) producendo gli output nella sottocartella graphify-out/ della directory corrente.

Il risultato finale del run e' stato un grafo di settantasei nodi distribuiti in ventun community, sessantatre archi con la distribuzione tra entita' estratte da citazioni esplicite e relazioni inferite dal modello rispettivamente del quarantotto e cinquantadue per cento, e confidence media sulle inferenze di 0.85. Il GRAPH_REPORT.md ha identificato come god nodes - le entita' piu' connesse - le seguenti, in ordine decrescente di archi: GitHub PR Permissions Model con sei archi, SSH Authentication for Git con cinque, Git Push and Multi-Machine Workflow con quattro, Merge Commit con quattro, Git Clone Full Repository Mechanism con quattro, git remote add origin con quattro, Git Remote Configuration con tre, Git Clone Repository con tre, Version Control Workflow Best Practices con tre, Linear History Strategy con tre.

Tra le surprising connections - le relazioni cross-document che graphify ha inferito ma non sono esplicitamente dichiarate nel testo - sono emerse alcune particolarmente significative: gh auth login collegato semanticamente a SSH Authentication for Git (perche' entrambi gestiscono autenticazione verso GitHub ma da angolazioni diverse), GitHub Deploy Keys collegato a SSH Authentication for Git (la chiave SSH usata per l'autenticazione e' tecnicamente lo stesso oggetto della deploy key vista da un altro punto di vista), git stash collegato a git restore Command (entrambi sono strumenti di recupero del working directory, anche se documentati in contesti diversi del corpus).

Il consumo effettivo di token misurato a fine run e' stato di centotredici mila in input e ventinove mila in output, per un totale aggregato di centoquarantadue mila. Questo dato e' fondamentale come riferimento di calibrazione per i run successivi: corrisponde a circa duemilanovecento token in input per file, valore che permette di stimare il consumo su corpus di dimensione diversa. Su una cartella di duecento documenti di analogo profilo, ci si puo' aspettare nell'ordine di cinquecentottanta mila token di input - cifra gestibile dalla quota Team Premium senza addebito API.

L'etichettatura dei nodi in inglese - GitHub PR Permissions Model anziche' Modello delle permessi delle PR su GitHub, SSH Authentication for Git anziche' Autenticazione SSH per Git - non e' un difetto ma una caratteristica delle prompt di graphify, che chiedono al modello di produrre label normalizzati e questo si traduce automaticamente in inglese su corpus italiano. Per il caso d'uso specifico di questo sistema, dove la tassonomia di destinazione e' anch'essa in inglese per ragioni di posizionamento professionale internazionale, questa traduzione automatica e' un vantaggio: elimina il passaggio di traduzione intermedio nella fase di mapping verso le Capability del repository pubblico.

La pipeline offline - i quattro script da enrich_graph.py a export_to_taxonomy.py - è stata testata end-to-end in modalita' --dry-run. Il risultato ha confermato che la classificazione automatica basata su recall produceva match plausibili per le competenze documentate nel corpus di test, con un numero gestibile di falsi positivi da rimuovere manualmente nella fase di revisione.

## Fase D - Post-processing italiano con enrich_graph.py

Dopo la validazione del primo run di graphify, il passo successivo e' stato scrivere il primo dei quattro script della pipeline offline: enrich_graph.py. Lo script ha due responsabilita' distinte ma complementari, entrambe fondate sul principio di composizione tra graphify come motore di estrazione generico e lettore-doc come libreria di euristiche specializzate per l'italiano.

La prima responsabilita' e' l'arricchimento di ciascun nodo del grafo con entita' riconosciute tramite le espressioni regolari italiane gia' esistenti in extract_entities.py. Per ogni nodo, lo script risolve il source_file relativo rispetto al --workdir passato come argomento (la cartella dove era stato lanciato graphify), legge il testo dal file convertito in Markdown nella sottocartella graphify-out/converted/ se si tratta di un .docx originale, oppure direttamente dal file se si tratta di un .txt o .md. Le immagini .png e i file binari vengono saltati. Sul testo letto vengono applicate tutte le dieci categorie di regex: sigle aziendali, ragioni sociali con suffisso societario, nomi propri di persona, codici progetto, riferimenti normativi italiani ed europei, date, importi in euro, indirizzi email, URL, riferimenti espliciti ad altri documenti. Il risultato viene aggiunto al nodo come campo italian_entities, un dizionario per categoria con valori e conteggi, e come campo text_preview, i primi duecento caratteri del testo sorgente come evidenza testuale da iniettare nelle fasi successive.

La seconda responsabilita' e' la costruzione dell'anonymization_map a livello di grafo. Lo script aggrega tutte le COMPANY e tutte le PROPER_NOUN trovate su tutti i nodi del corpus, le ordina per frequenza decrescente, e assegna placeholder numerati progressivamente: [AZIENDA_1] per la ragione sociale piu' citata nel corpus, [AZIENDA_2] per la seconda, e cosi' via; analogamente [PERSONA_1] e successivi per i nomi propri. Questa mappa viene salvata all'interno dell'enriched_graph.json e viene applicata da export_to_taxonomy.py prima che qualsiasi testo venga scritto nel repository pubblico. Il principio architetturale e' che l'anonimizzazione vera avviene quando i frammenti testuali vengono citati nella tassonomia pubblica, non sui label dei nodi che sono gia' stati tradotti in inglese da graphify e non contengono nomi propri italiani.

Il test sul corpus version-control ha confermato il comportamento atteso. Su trentanove file di documentazione puramente tecnica, lo script ha trovato zero ragioni sociali e zero nomi propri di persona: nessun riferimento aziendale e nessuna persona identificabile sono presenti nella documentazione di Git e GitHub. Sono stati invece riconosciuti correttamente acronimi tecnici (SSH, GPG, HTTP, HTTPS, e altri), URL multipli, e qualche riferimento a documenti. L'output del test ha confermato che l'anonymization_map era vuota - non c'era nulla da anonimizzare nel corpus di test - ma che il meccanismo di riconoscimento e di costruzione della mappa funzionava correttamente. La differenza emergera' al primo run su documentazione aziendale reale, dove le ragioni sociali e i nomi propri saranno presenti in quantita' significativa.

## Fase E - Mapping sulla tassonomia con map_to_taxonomy.py

La fase di mapping richiede due input: il grafo arricchito prodotto da enrich_graph.py e un indice della tassonomia attuale pubblicata su skills-repo. Il secondo input e' generato a sua volta da uno script, generate_taxonomy_index.py, che legge il file mkdocs.yml di skills-repo e per ogni Capability page elencata nella navigazione estrae le keyword significative dalle sezioni Technologies & tools e Overview. Il numero tipico di keyword estratte e' tra trentasei e sessanta per Capability, a seconda della densita' editoriale della pagina.

Lo script map_to_taxonomy.py applica un meccanismo di classificazione basato su recall. Per ogni coppia nodo-Capability, viene tokenizzato il norm_label del nodo (la versione normalizzata in inglese prodotta da graphify) insieme ai token del community label del nodo (la categoria tematica assegnata durante il clustering Louvain di graphify), e si misura quanti di questi token compaiono tra le keyword della Capability. Il recall e' il rapporto tra i match e il numero totale di token del nodo. Se supera la soglia di 0.15 il nodo viene classificato come fit per quella Capability e diventera' un'evidenza progettuale nella sezione Projects & evidence della pagina corrispondente. Se nessuna Capability supera 0.15 ma almeno una keyword del Domain ha corrispondenza con recall superiore a 0.08, il nodo viene proposto come new_capability all'interno di quel Domain. Se non c'e' corrispondenza con nessun Domain, il nodo viene proposto come new_domain. Sotto la soglia minima di 0.01 il nodo viene marcato come non classificato e va revisionato manualmente.

Il primo test del mapping ha rivelato un bug significativo nella stoplist delle parole comuni. Le parole git e github erano state inserite nella stoplist con l'idea che fossero "troppo generiche" per essere keyword utili, ma questa scelta ha avuto come conseguenza che nodi come git push si riducessero al solo token {push} dopo la tokenizzazione, fallendo il match con qualsiasi Capability sensata e finendo nella categoria non classificati. Il risultato del primo run era ventun nodi non classificati su settantasei totali - un livello inaccettabile per una pipeline di produzione.

La correzione e' stata rimuovere git e github dalla stoplist. Il rilancio successivo dello script ha prodotto un risultato drasticamente migliore: settanta fit, cinque new capability, zero new domain, un solo nodo non classificato. La verifica qualitativa di un campione dei mapping ha confermato la plausibilita' della classificazione: tutti i nodi git core (git branch, git init, git clone, git checkout, ecc.) sono finiti su Software Engineering / Full-Stack, Docker e' finito su Full-Stack, VS Code e' finito su Full-Stack, le pratiche di workflow GitHub sono finite su Software Engineering. I pochi falsi positivi residui (SSH classificato su M365 Business invece che su System Administration, git merge classificato su Backup) erano dovuti al fatto che il corpus di test usato non aveva il testo reale dei documenti ma solo i placeholder generati dalla conversione, e si sarebbero risolti automaticamente in produzione con il testo integrale disponibile.

L'output del mapping e' duplice: un file taxonomy_diff.md in formato leggibile per la revisione umana, strutturato in sezioni per fit per Capability, new Capability suggerite per Domain, e new Domain proposti; e un file taxonomy_diff.json con la stessa informazione in formato machine-readable, consumato dallo script di applicazione successivo. La presenza del formato Markdown e' deliberata: il diff non e' un output finale ma un punto di revisione editoriale, e va aperto in un editor di testo, letto, e modificato a mano prima di essere applicato.

## Fase F - Applicazione delle modifiche con export_to_taxonomy.py

Lo script export_to_taxonomy.py e' l'unico componente del sistema che scrive nel repository pubblico, e per questo motivo opera secondo regole particolarmente conservative. La modalita' di default e' --dry-run: lo script stampa l'elenco completo delle operazioni che eseguirebbe - per ogni Capability, il numero di evidenze che andrebbero iniettate, il loro contenuto sintetizzato, i nuovi file Markdown che verrebbero creati, le righe da aggiungere al mkdocs.yml - senza toccare nessun file su disco. Solo con il flag esplicito --apply lo script effettua effettivamente le modifiche.

Per ogni nodo classificato come fit, lo script apre il file Markdown della Capability di destinazione, individua la sezione ## Projects & evidence cercando esattamente quel titolo, rimuove l'eventuale placeholder testuale presente sotto il titolo, e inietta immediatamente sotto un blocco H3. Il blocco contiene il label del nodo come titolo H3, immediatamente sotto un commento HTML invisibile con l'ID di idempotenza, e poi le informazioni strutturate sul nodo: il source file, la community di appartenenza nel grafo, e il text_preview anonimizzato applicando l'anonymization_map sui nomi presenti.

L'ID di idempotenza e' lo SHA-256 breve dei primi dodici caratteri della concatenazione di node_id e capability_slug. Prima di iniettare qualsiasi nuova evidenza, lo script legge il contenuto attuale del file di destinazione e cerca la presenza dell'identificatore come sottostringa nel sorgente Markdown. Se l'identificatore e' gia' presente, l'evidenza viene saltata. Se e' assente, viene iniettata. Questo rende lo script idempotente: puo' essere eseguito ripetutamente sullo stesso diff senza produrre duplicati.

La verifica del meccanismo di idempotenza e' stata fatta in modo esplicito sul corpus di test. La prima esecuzione di export_to_taxonomy.py --apply sul diff prodotto ha iniettato settanta evidenze in altrettante posizioni delle Capability pages, e ha creato cinque nuove Capability con la struttura standard a quattro H2. La seconda esecuzione, sullo stesso identico diff senza nessuna modifica intermedia, ha riportato come output "zero iniezioni, settanta evidenze gia' presenti": il meccanismo ha riconosciuto tutti gli ID gia' iniettati nel passaggio precedente e ha saltato correttamente le evidenze duplicate. Il formato del file risultante mantiene il commento HTML come ID stabile, invisibile nel rendering del sito ma conservato nel sorgente Markdown e quindi disponibile per i controlli di idempotenza successivi.

Per le new Capability accettate nella fase di revisione, lo script crea il file Markdown corrispondente con lo schema a quattro H2 standard (Overview, Technologies & tools, Responsibilities & operational scope, Projects & evidence), inserisce un testo iniziale generico in ciascuna sezione che serve come placeholder editoriale, e stampa a video la riga che deve essere aggiunta manualmente al mkdocs.yml. La modifica del mkdocs.yml non e' automatizzata per scelta deliberata: il file di navigazione del sito definisce la struttura pubblica della tassonomia, e ogni modifica deve essere un atto consapevole e revisionato.

## Fase G - Knowledge Graph ortogonale: graphify su skills-repo/docs

L'output complessivo del run di graphify su docs/ e' stato un grafo di centoquarantuno nodi, cententonovantacinque archi, e quattordici community. I god nodes che sono emersi come piu' connessi nel grafo - LLMs & Generative AI, Cybersecurity & IT Governance, Backup & Disaster Recovery, Ad-hoc Internal Development - non sono il risultato di una classificazione soggettiva ma l'esito oggettivo di un'analisi semantica automatica che ha rilevato quali Capability del portfolio si manifestano in piu' contesti diversi all'interno della documentazione. Il fatto che queste quattro specifiche Capability siano emerse come centrali ha un significato preciso: sono le aree di competenza piu' trasversali del profilo professionale, quelle che si intersecano con la maggior parte degli altri ambiti, e quindi rappresentano i punti di forza con maggior potenziale comunicativo verso un interlocutore esterno.

Dal punto di vista operativo, l'utilizzo ortogonale di graphify su docs/ va eseguito non a ogni aggiornamento del contenuto delle Capability ma quando la struttura della tassonomia cambia in modo significativo: l'aggiunta di nuove Capability, la riorganizzazione dei Domain, una revisione editoriale ampia delle pagine. In queste occasioni il rilancio di graphify aggiorna la visualizzazione del Knowledge Graph che riflette la nuova struttura. Tra un aggiornamento e l'altro, il file graph.html committato nel repository continua a essere servito come asset statico senza modifiche.

Il lancio di /graphify docs/ sulla cartella di skills-repo ha prodotto un risultato utile ma con un problema di percorso. graphify ha scritto il suo output nella cartella graphify-out/ nella root del repository, mentre MkDocs serve come asset statici solo i file presenti all'interno della cartella docs/. Il file graph.html era quindi accessibile localmente ma non sarebbe stato pubblicato nel sito. La correzione è stata spostare la cartella con Move-Item graphify-out docs\graphify-out. Al successivo push, la build MkDocs ha copiato docs/graphify-out/graph.html in _site/graphify-out/graph.html, rendendolo accessibile all'URL diretto. Il .gitignore del repository è stato aggiornato per escludere i file intermedi di graphify (.graphify_*, converted/, cost.json, manifest.json) e versionare solo graph.html e GRAPH_REPORT.md.

## Fase H - sources.yml e orchestrazione multi-sorgente

Il sistema fino a questo punto e' validato sui singoli corpora ma non e' ancora orchestrato su tutte le sorgenti previste. L'architettura prevede che le sorgenti di documentazione siano cinque o piu': la cartella Documenti - IT sincronizzata su OneDrive aziendale, la cartella IT-RELATED del portfolio personale su Google Drive sync, e tre o quattro cartelle aggiuntive su unita' SSD esterne con archivi di progetti storici. Il file sources.yml dentro lettore-doc e' il punto di configurazione centrale che elenca tutte queste sorgenti, ciascuna con il proprio path, un'etichetta identificativa, l'elenco delle estensioni di file da includere, e i pattern di esclusione per sottocartelle o file irrilevanti (template, archivi, file temporanei).

I path nel sources.yml usano variabili di ambiente con sintassi ${NOME_VARIABILE} che vengono espanse a runtime tramite os.path.expandvars(). Questa scelta serve a non hardcodare nei file committati i path assoluti delle cartelle sorgente, che possono contenere riferimenti a strutture aziendali o personali non destinati al repository, anche se il repository e' privato. Le variabili vengono settate una sola volta per macchina con SetEnvironmentVariable scope User, scritte nel registro di Windows, e diventano disponibili in tutte le sessioni PowerShell e Claude Code successive.

Lo script orchestratore previsto, run_graphify_all.ps1, dovrebbe ciclare sulle sorgenti elencate in sources.yml e lanciare graphify per ciascuna. Qui emerge un limite tecnico che impone un workflow semi-automatico anziche' completamente automatizzato: graphify richiede una sessione Claude Code interattiva per funzionare con la quota Team Premium, e non puo' essere invocato come sottoprocesso non interattivo da uno script PowerShell senza fornire una chiave API a pagamento. La conseguenza pratica e' che lo script orchestratore prepara l'ambiente per ciascuna sorgente (copia temporanea in path ASCII se necessario, creazione delle cartelle di output, registrazione dei path per il successivo merge), ma il lancio di /graphify deve essere fatto manualmente per ogni sorgente in una sessione Claude Code separata. Dopo che tutti i graph.json sono stati prodotti, lo script orchestratore puo' essere rilanciato con flag -OnlyMap per eseguire la pipeline offline (enrich, mapping, export) in modo completamente automatico.

Per il merging dei grafi prodotti da run separati, graphify offre un comando merge-graphs che fonde piu' graph.json in un unico grafo aggregato. La logica del merge gestisce le entita' che compaiono in sorgenti diverse: se lo stesso concetto viene estratto da due cartelle, i suoi archi vengono uniti e il count viene aggregato. Il grafo risultante e' l'input dell'enrich_graph.py della pipeline offline.

Una decisione operativa esplicita e' stata di non installare i git hook che graphify offre per il rebuild automatico dopo ogni commit. La motivazione e' specifica per il filesystem Google Drive sync su cui vivono il repository pubblico e parte delle sorgenti: i lock file di Git che vengono creati durante i rebuild automatici possono interferire con il client di sincronizzazione cloud, producendo conflitti di file e occasionali corruzioni dell'indice Git. Il workflow manuale - aggiunta di documenti, lancio manuale dello script orchestratore, revisione del diff, commit e push - e' piu' sicuro e mantiene il controllo esplicito sulle modifiche al repository pubblico.

## Fase I - Il server MCP Obsidian Vault

Una delle estensioni operative emerse durante lo sviluppo e' stata la connessione di un server MCP Obsidian Vault all'ambiente Claude. MCP, acronimo di Model Context Protocol, e' il protocollo aperto introdotto da Anthropic che consente a Claude di interagire con servizi esterni o con il filesystem tramite componenti server standardizzati. Il server di filesystem MCP, in particolare, consente di esporre una o piu' cartelle del disco a Claude come tool di lettura e scrittura, abilitando Claude a operare direttamente su file fuori dal proprio ambiente isolato.

Il setup applicato a questo sistema prevede un vault Obsidian privato dedicato a lettore-doc-and-skills, collocato sotto Documents/Obsidian Vault dell'utente, connesso a Claude Desktop tramite il file di configurazione claude_desktop_config.json. La configurazione e' un blocco JSON che dichiara il comando di avvio del server (npx con il pacchetto @modelcontextprotocol/server-filesystem) e gli array di path che il server e' autorizzato a leggere e scrivere. Una volta connesso, una sessione di Claude Desktop puo' chiamare i tool del server - write_file, read_file, list_directory, create_directory, move_file - per operare direttamente sui file del vault.

La distinzione tra il vault Obsidian come concetto e la cartella del filesystem come oggetto fisico e' importante per non confondere i due piani. Il server MCP filesystem da' a Claude il permesso di leggere e scrivere file in una cartella; a Claude non importa se quella cartella e' un vault Obsidian, un repository Git o una cartella generica - per lui sono solo file e sottocartelle. Obsidian, contemporaneamente, apre quella stessa cartella come vault, applicandoci sopra i suoi concetti (note Markdown, wiki-link, plugin, grafi, embedding HTML). Sono due strati che vivono in parallelo sulla stessa cartella senza influenzarsi reciprocamente: se si chiude Obsidian, il server MCP continua a funzionare; se si elimina il vault da Obsidian ma si mantiene la cartella, il server MCP continua a funzionare. L'utente e' la colla che usa i due strumenti contemporaneamente.

Una sottigliezza tecnica riguarda l'ambito di applicazione: la configurazione in claude_desktop_config.json vale esclusivamente per Claude Desktop - l'applicazione grafica - e non per Claude Code, la CLI da terminale. Le due interfacce di Claude hanno modelli di accesso al filesystem radicalmente diversi. Claude Desktop e' progettato per girare in un ambiente isolato e ha bisogno di un MCP esplicito per accedere ai file dell'utente; senza quel ponte non vede nessun file. Claude Code, al contrario, e' progettato per vivere nel terminale all'interno di una cartella specifica: quando viene lanciato con il comando claude, ottiene automaticamente accesso ricorsivo a tutta la cartella corrente e a tutte le sue sottocartelle, senza bisogno di alcun MCP. Lo scope di Claude Code e' la cartella da cui viene lanciato; per lavorare su una cartella diversa basta fare cd in quella cartella prima di invocare claude.

L'uso operativo del server MCP Obsidian in questo sistema e' previsto per due scenari principali. Il primo e' la scrittura diretta nelle Capability pages del repository pubblico da una sessione Claude Desktop, senza passare attraverso lo script export_to_taxonomy.py. Il workflow alternativo sarebbe: /graphify produce il grafo, una sessione Claude Desktop con MCP Obsidian collegato a skills-repo/docs legge il diff e scrive direttamente le evidenze nelle Capability pages, l'utente effettua git commit + git push manualmente. Questo elimina due passaggi rispetto alla pipeline standard, al costo di un compromesso che va riconosciuto esplicitamente.

Il compromesso e' di natura tecnica e riguarda l'idempotenza. Lo script export_to_taxonomy.py implementa il controllo di idempotenza tramite gli ID stabili contenuti nei commenti HTML iniettati sotto ogni evidenza. Le scritture effettuate direttamente da Claude tramite il server MCP non passano attraverso questo controllo: se Claude inietta un'evidenza per un nodo gia' presente nella pagina, il duplicato non viene rilevato automaticamente. La conseguenza pratica e' che se si sceglie di usare il server MCP per le iniezioni dirette anziche' lo script, bisogna tenere traccia manualmente di cosa e' gia' stato scritto, oppure accettare che il diff occasionalmente proponga duplicati che andranno corretti manualmente prima del prossimo apply.

Il secondo scenario d'uso del server MCP, piu' adatto al sistema, e' l'editing manuale delle pagine della tassonomia: correggere testo, aggiungere contesto umano che gli script non possono generare, riorganizzare la prosa della sezione Overview di una Capability. In questo scenario il server MCP funge da estensione di Claude per operazioni di scrittura mirate e revisionate, complementare alla pipeline automatica e non in competizione con essa. La raccomandazione esplicita e' di mantenere export_to_taxonomy.py come l'unica via automatica per popolare la sezione Projects & evidence, e di usare il server MCP per tutto il resto: editing della prosa, aggiunta di sezioni manuali, correzioni stilistiche.

Una nota operativa fondamentale per il setup di skills-repo/docs come vault Obsidian e' l'esclusione preventiva della cartella .obsidian/ dal controllo di versione. Obsidian, all'apertura di un vault, crea una sottocartella .obsidian/ nella radice del vault contenente la configurazione locale, i workspace, lo stato dell'editor, eventuali plugin installati. Questa configurazione e' specifica della macchina e dell'utente e non deve finire nel repository pubblico. L'esclusione si fa aggiungendo .obsidian/ al file .gitignore di skills-repo prima della prima apertura del vault in Obsidian, e committando questa modifica preliminarmente. Il vault va aperto puntando alla cartella docs/ del repository, non alla root: questo limita la vista di Obsidian alle sole pagine Markdown della tassonomia, evitando che il file mkdocs.yml, il workflow .github/, o altre cartelle ausiliarie del repository compaiano nella sidebar di navigazione.

## Caso operativo end-to-end: aggiornamento di una sorgente reale

Per fissare il workflow operativo a regime e i tempi reali coinvolti, si consideri uno scenario concreto. L'utente ha appena completato un progetto di migrazione di un cluster server su tecnologia Proxmox VE, con configurazione High Availability e strategia di backup basata su Veeam. Il lavoro ha prodotto tre documenti Word in una cartella di progetto: un'analisi tecnica preliminare con il design dell'architettura, una procedura di configurazione con i comandi e gli script applicati, un verbale finale con i risultati e gli esiti dei test di failover. I documenti sono in una cartella sotto la sincronizzazione del portfolio personale, e l'obiettivo e' che le competenze dimostrate appaiano sul sito pubblico entro la stessa sera.

Il primo passo, eseguito alle diciotto in punto, e' l'apertura di PowerShell e lo spostamento nella cartella di progetto. Si avvia Claude Code con claude, si imposta il modello con /model claude-sonnet-4-5, e si lancia /graphify .. graphify legge i tre documenti, costruisce il grafo, e produce graphify-out/graph.json nella cartella corrente. Per tre documenti di una decina di pagine ciascuno la stima e' di circa quindicimila token totali e meno di un minuto di esecuzione. La lettura del GRAPH_REPORT.md conferma le aspettative: i god nodes identificati sono Proxmox VE Cluster Migration, SSH Tunnel Configuration, Veeam Backup Strategy.

Alle diciotto e cinque inizia la pipeline offline. Si torna nella cartella di lettore-doc e si lanciano nell'ordine i tre script. generate_taxonomy_index.py riproduce l'indice della tassonomia attuale di skills-repo (operazione di pochi secondi). enrich_graph.py legge il graph.json prodotto da graphify, lo arricchisce con le entita' italiane riconosciute e costruisce l'anonymization_map: per questo corpus aziendale specifico la mappa contiene placeholder per i nomi dei clienti e dei tecnici citati. map_to_taxonomy.py applica il matching basato su recall e produce taxonomy_diff.md.

Alle diciotto e sei inizia la fase di revisione manuale. L'apertura del taxonomy_diff.md in un editor mostra il risultato del mapping. Sotto la Capability Infrastructure & Virtualization compaiono come fit i nodi Proxmox VE Cluster Migration e High Availability Configuration, classificazione corretta. Sotto Backup & Disaster Recovery compare il nodo Veeam Backup Strategy, anch'esso corretto. Sotto System Administration compare SSH Tunnel Configuration, anch'esso pertinente. Un fit ulteriore propone SSH Multi-Account Setup sotto Networking Engineering & Security, ma questo e' un falso positivo: si riferisce alla configurazione SSH del progetto, non alla gestione di account multipli, e va rimosso dal diff prima di applicare. Una proposta di new_capability suggerisce di creare una nuova Capability dal nome "Proxmox Ve Cluster Migration": l'utente la accetta ma la rinomina manualmente nel diff in "Proxmox VE & HA Cluster Operations", con slug proxmox-ha-cluster, perche' il nome originale era troppo specifico al singolo progetto e meno utile come categoria generale del portfolio.

Alle diciotto e dieci si applica il diff. Prima il dry-run conferma le operazioni pianificate: tre iniezioni nelle Capability esistenti, un nuovo file da creare. Tutto coerente. Si rilancia il comando con --apply: lo script inietta le evidenze nelle tre Capability esistenti aggiungendo H3 sotto la sezione Projects & evidence con i commenti HTML di idempotenza, crea il file docs/infrastructure/proxmox-ha-cluster.md con lo schema a quattro H2 standard, e stampa la riga da aggiungere manualmente al mkdocs.yml. L'utente apre il mkdocs.yml, aggiunge la riga sotto la lista delle Capability del Domain Infrastructure, salva il file.

Alle diciotto e dodici si esegue il commit e il push. Lo spostamento nella cartella di skills-repo, git add docs/, git add mkdocs.yml, git commit con un messaggio descrittivo che cita la sorgente del progetto e la nuova Capability creata, git push. Il workflow GitHub Actions parte automaticamente, esegue mkdocs build --strict, e in circa un minuto il sito e' aggiornato. L'URL della nuova pagina Capability - alesop95.github.io/skills/infrastructure/proxmox-ha-cluster/ - e' ora stabile e inseribile nel curriculum vitae. Chiunque lo apra vede la pagina con la struttura standard a quattro sezioni, lo stack tecnologico citato, le responsabilita' operative documentate, e l'evidenza del progetto anonimizzata nella sezione Projects & evidence.

Il tempo totale dall'apertura di Claude Code al sito pubblicato e' di tredici minuti, di cui la maggior parte spesi nella revisione manuale del diff. Su corpora piu' grandi - venti, cinquanta, duecento documenti - il tempo di esecuzione di graphify cresce ma resta sotto la decina di minuti, mentre il tempo di revisione del diff puo' allungarsi a venti-trenta minuti per corpus complessi. Il ciclo completo rimane gestibile nell'ordine di mezz'ora-un'ora di lavoro umano per aggiornamenti mensili anche su corpora di centinaia di documenti, con la confidenza che ogni evidenza pubblicata e' stata revisionata individualmente prima di apparire online.

## Stato attuale del sistema e cosa rimane da fare

A questo punto della cronologia il sistema e' funzionante end-to-end nei suoi componenti principali, ed e' stato validato su un corpus di test reale. I componenti completati sono: il sito pubblico online con ventinove pagine Capability su sette Domain e il workflow di deploy automatico via GitHub Actions; il repository privato lettore-doc su GitHub con i quattro script della pipeline di estrazione skill committati; graphify installato e registrato come skill in Claude Code; la pipeline end-to-end testata sul corpus version-control con generazione di un grafo, arricchimento italiano, mapping sulla tassonomia, applicazione delle evidenze, verifica del meccanismo di idempotenza; il Knowledge Graph del portfolio prodotto come asset statico del sito pubblico tramite l'utilizzo ortogonale di graphify; il server MCP Obsidian connesso a Claude Desktop e pronto per l'editing assistito; due file CLAUDE.md in entrambi i repository per istruire Claude Code sull'architettura ad ogni nuova sessione.

Tre elementi concreti restano da completare prima di considerare il sistema in stato di produzione stabile. Il primo e' la finalizzazione del sources.yml. Le variabili di ambiente per le sorgenti OneDrive e Portfolio sono state settate, ma le tre o quattro cartelle aggiuntive su SSD esterno con archivi di progetti storici non sono ancora state aggiunte: vanno definite le variabili di ambiente mancanti, popolato sources.yml con le entry corrispondenti, e verificato che i percorsi siano accessibili e contengano il materiale atteso. Il secondo e' l'esecuzione del primo run reale su una sorgente di produzione, tipicamente la cartella Documenti - IT di OneDrive: tutti i test fino a questo punto sono stati condotti sul corpus version-control che e' documentazione tecnica priva di dati aziendali, e il sistema deve essere ancora validato sulla documentazione di progetto reale con clienti, codici progetto e nomi propri da anonimizzare. Il terzo elemento e' la produzione delle sintesi narrative nel vault Obsidian privato tramite il subagente lettore-documentazione, attivata da una sessione Claude Code mirata sul vault: questo non e' bloccante per la pipeline pubblica, ma e' parte del valore d'uso del vault privato come ambiente di navigazione personale della documentazione aziendale.

Con questi tre elementi completati, il sistema sara' nella condizione di mantenimento stabile in cui l'utente puo' aggiungere documenti alle cartelle sorgente, lanciare mensilmente il ciclo di aggiornamento, e vedere la tassonomia pubblica evolvere in modo coerente con il lavoro effettivamente svolto, senza mai esporre dati sensibili e con la confidenza che ogni evidenza pubblicata e' stata revisionata manualmente prima di andare online.

# Il sistema a regime

## Ciclo operativo mensile

Il ciclo tipico per aggiornare la tassonomia con le evidenze progettuali dei documenti aggiunti o modificati nell'ultimo mese si articola in sei passi che possono essere completati in meno di venti minuti per corpus di dimensione media, o fino a un'ora per corpus di duecento o piu' documenti.

Il primo passo è il lancio di graphify sulla cartella sorgente. Si apre PowerShell, ci si posiziona nella cartella, si avvia una sessione Claude Code e si lancia /graphify . --update per processare solo i file modificati dall'ultimo run. Questo passo consuma token della quota Team ma non ha costi aggiuntivi per l'utente del piano. Il secondo passo è la generazione dell'indice della tassonomia tramite generate_taxonomy_index.py. Il terzo è l'arricchimento del grafo con enrich_graph.py, che punta al graph.json prodotto da graphify nella cartella sorgente. Il quarto è la classificazione con map_to_taxonomy.py. Questi tre passi sono completamente offline e vengono eseguiti in pochi secondi anche su corpus grandi.

Il quinto passo è la revisione manuale del file taxonomy_diff.md: aprirlo in un editor di testo, verificare i fit proposti, eliminare i falsi positivi, accettare o rinominare le new Capability suggerite. Il sesto passo è l'esecuzione di export_to_taxonomy.py prima in modalita' --dry-run per confermare visivamente le operazioni pianificate, poi in modalita' --apply per applicarle. A questo punto i file Markdown di skills-repo sono stati aggiornati localmente. Il commit e il push verso GitHub completano il ciclo: il workflow GitHub Actions parte automaticamente, esegue mkdocs build --strict, e pubblica il sito aggiornato su GitHub Pages in circa un minuto.

| Il flag --strict di mkdocs build fa fallire la build se sono presenti link rotti o riferimenti a file non esistenti nel repository. È un controllo di integrita' voluto: un errore nel Markdown viene catturato immediatamente invece di produrre silenziosamente un sito con pagine rotte. Se il workflow GitHub Actions fallisce, controllare prima di tutto i link interni tra le pagine della tassonomia e le entry nel mkdocs.yml. |
|---|

## I tre output per tre contesti d'uso distinti

Il sistema produce tre output indipendenti che servono contesti d'uso radicalmente diversi. Il vault Obsidian privato, nella cartella vault-output\, è un ambiente di navigazione personale della documentazione aziendale con grafo di relazioni, sintesi narrative, e wiki-link automatici tra documenti correlati. È generato dal pipeline originale di lettore-doc tramite run_pipeline.ps1 e aggiornato quando si vuole esplorare il corpus in modo strutturato o quando vengono aggiunte nuove sintesi narrative. Non è mai visibile all'esterno.

Il sito MkDocs pubblico, accessibile all'URL alesop95.github.io/skills/, è la tassonomia di competenze navigabile da chiunque: recruiter, clienti, interlocutori tecnici, chiunque abbia il link dal curriculum vitae. È aggiornato automaticamente ad ogni push sul branch main di skills-repo e riflette in circa un minuto qualsiasi modifica apportata ai file Markdown della tassonomia. Il Knowledge Graph interattivo, all'URL alesop95.github.io/skills/graphify-out/graph.html, è un asset statico HTML aggiornato periodicamente, non ad ogni push, e offre una visualizzazione della struttura relazionale della tassonomia che integra la navigazione testuale del sito principale.

# Appendice A - Setup iniziale e prerequisiti

Questa appendice raccoglie tutto quanto serve per portare il sistema in stato operativo su una nuova macchina o per ricostruirlo dopo un cambio di ambiente. E' organizzata in sezioni che seguono l'ordine in cui le operazioni vanno eseguite la prima volta. Una volta completate, il sistema rimane funzionante senza richiedere altri interventi di setup, e l'utente puo' passare direttamente all'uso operativo descritto nell'Appendice B.

## A.1 Prerequisiti software

Il sistema richiede quattro componenti software preinstallati sulla macchina prima di poter procedere con il setup specifico di lettore-doc. Il primo e' Python in versione 3.10 o superiore. Su Windows si scarica dal sito python.org spuntando l'opzione "Add Python to PATH" durante l'installazione, altrimenti il comando python non sara' invocabile da PowerShell senza percorso completo. La verifica si fa lanciando python --version da una nuova sessione PowerShell, che deve restituire una versione superiore a 3.10.

Il secondo componente e' Claude Code, l'interfaccia a riga di comando di Anthropic che ospita la skill graphify. L'installazione segue le istruzioni ufficiali pubblicate sul sito docs.claude.com; dopo l'installazione e' necessario autenticarsi con il proprio account Anthropic, idealmente un account inserito in un piano Team Premium per evitare addebiti API durante l'uso di graphify.

Il terzo componente e' graphify, distribuito come pacchetto Python e installabile tramite pipx. L'installazione richiede che pipx sia gia' presente; se non lo e', va installato preliminarmente con python -m pip install --user pipx seguito da python -m pipx ensurepath e dalla chiusura/riapertura del terminale per aggiornare il PATH. Una volta disponibile pipx, l'installazione di graphify avviene con un singolo comando.

```
pipx install "graphifyy[office]"
graphify install --platform windows
graphify --version       # atteso: graphify 0.8.x

```
Le virgolette nel primo comando sono obbligatorie su PowerShell perche' le parentesi quadre del suffisso office vengono altrimenti interpretate dalla shell. Il suffisso aggiunge il supporto per i formati Microsoft Office (.docx, .xlsx) tramite python-docx e openpyxl. Il secondo comando registra graphify come skill in Claude Code, scrivendo un file di definizione che Claude Code legge automaticamente all'avvio di ogni sessione.

Il quarto componente e' Git, scaricabile da git-scm.com. Dopo l'installazione vanno configurate username ed email con git config --global user.name e git config --global user.email per identificarsi correttamente nei commit.

## A.2 Struttura del filesystem di lettore-doc

Il repository lettore-doc, una volta clonato, ha una struttura interna ben definita che riflette la separazione tra script, configurazione, dati di lavoro e output. La conoscenza di questa struttura e' utile per orientarsi durante l'uso quotidiano e per sapere dove cercare i file quando qualcosa non funziona come atteso.

```
E:\lettore-doc\
├── .claude\
│   ├── agents\lettore-documentazione.md      subagente Claude Code
│   └── skills\
│       ├── grafo-conoscenza\SKILL.md
│       └── parsing-docx\SKILL.md
├── scripts\
│   ├── parse_docx.py                         parsing token-efficient
│   ├── extract_entities.py                   regex italiane
│   ├── build_knowledge_graph.py              grafo dei documenti
│   ├── generate_vault.py                     vault Obsidian privato
│   ├── enrich_graph.py                       post-processing italiano
│   ├── generate_taxonomy_index.py            indicizza mkdocs.yml
│   ├── map_to_taxonomy.py                    classifica fit/new_cap
│   └── export_to_taxonomy.py                 inietta in skills-repo
├── _intermediate\                            dati di lavoro (gitignored)
├── vault-output\                             vault Obsidian (gitignored)
├── .venv\                                    ambiente Python (gitignored)
├── sources.yml                               configurazione sorgenti
├── requirements.txt
├── setup.ps1 / setup.sh
├── run_pipeline.ps1 / run_pipeline.sh        pipeline vault privato
├── README.md                                 reference operativo
├── GUIDA-TECNICA.md                          architettura completa
├── case-study-operativi.md                   8 casi pratici
└── diario-tecnico-progetto.docx              questo documento

```
Le tre cartelle marcate gitignored - .venv, _intermediate, vault-output - non vengono mai committate nel repository Git. La prima contiene l'ambiente Python isolato del progetto, la seconda i file intermedi prodotti dalla pipeline (rigenerabili in qualsiasi momento), la terza il vault Obsidian privato (anch'esso rigenerabile). Questa esclusione e' fondamentale per la portabilita': chi clona il repository ricostruisce queste tre cartelle eseguendo localmente i comandi di setup e di pipeline, senza ricevere dati di lavoro vecchi o riferimenti a path della macchina di origine.

## A.3 Procedura di setup primo avvio

Il setup del progetto avviene tramite lo script setup.ps1 su Windows (o setup.sh su macOS/Linux), che si occupa di creare l'ambiente Python isolato, aggiornare pip al suo interno, e installare le dipendenze elencate in requirements.txt. Lo script va eseguito una sola volta sulla macchina, e la sua esecuzione e' idempotente: rilanciarlo non produce effetti collaterali.

```
# Windows
cd E:\lettore-doc
.\setup.ps1

# macOS / Linux
cd ~/lettore-doc
./setup.sh

```
Lo script crea la cartella .venv/ all'interno del progetto - una scelta deliberata che mantiene l'ambiente Python locale al progetto e non lo installa a livello di sistema. La conseguenza pratica e' che lettore-doc non interferisce con altri progetti Python sulla stessa macchina, e che la sua disinstallazione si riduce alla cancellazione della sua cartella. La durata dell'operazione e' di circa quindici secondi su una connessione internet ragionevole.

Se in futuro si rende necessario ricreare l'ambiente da zero - tipicamente dopo l'aggiornamento di Python di sistema o dopo modifiche al requirements.txt - lo script accetta un flag che rimuove la .venv esistente prima di crearne una nuova.

```
.\setup.ps1 -Force     # Windows
./setup.sh --force      # macOS / Linux

```

## A.4 Configurazione delle sorgenti in sources.yml

Il file sources.yml contiene l'elenco delle cartelle del filesystem da cui la pipeline legge i documenti. Va editato manualmente la prima volta, aggiungendo una voce per ogni cartella sorgente che si vuole elaborare. La sintassi e' YAML standard e ogni voce ha quattro campi: il path della cartella, una label identificativa univoca, l'elenco delle estensioni di file da includere, e i pattern di esclusione per sottocartelle o file da ignorare. Un esempio concreto con due sorgenti tipiche per illustrare la sintassi.

```
sources:
  - path: "C:/Users/Utente/OneDrive - Azienda/Documenti-IT"
    label: documenti_it
    include_extensions: [.docx, .txt, .md]
    exclude_patterns: ["~$*", "_archive/*", "template/*"]

  - path: "J:/googleDrive_sync/Portfolio/IT-RELATED"
    label: portfolio_it
    include_extensions: [.docx, .txt, .md, .png]
    exclude_patterns: ["~$*"]
```
I path possono usare variabili di ambiente con sintassi ${NOME_VARIABILE}, che vengono espanse a runtime dagli script Python tramite os.path.expandvars(). Questa scelta serve a evitare di hardcodare nei file committati i percorsi assoluti delle cartelle, che possono contenere riferimenti a strutture aziendali o personali. Le variabili tipiche sono LETTERDOC_SOURCE_ONEDRIVE, LETTERDOC_SOURCE_PORTFOLIO, LETTERDOC_SKILLS_REPO, e si settano una sola volta per macchina con SetEnvironmentVariable scope User da PowerShell.

## A.5 Problemi noti al primo utilizzo

Alcuni problemi si presentano con regolarita' al primo utilizzo del sistema e meritano di essere conosciuti in anticipo per non perdere tempo a debuggarli. Il primo riguarda OneDrive in modalita' "solo cloud": se la cartella sorgente sincronizzata via OneDrive ha l'icona a nuvola accanto ai file, significa che i file non sono fisicamente presenti sul disco locale ma vengono scaricati on-demand. python-docx non riesce a leggere file in questa modalita' e produce errori al primo parsing. La soluzione e' clic destro sulla cartella sorgente da Esplora File e selezionare "Mantieni sempre su questo dispositivo", forzando OneDrive a tenere i file localmente.

Il secondo problema riguarda i file .doc legacy: il sistema elabora esclusivamente file .docx e ignora i .doc. Eventuali documenti nel vecchio formato vanno convertiti aprendoli in Word e salvandoli come .docx. Il terzo problema sono i documenti scansionati senza riconoscimento ottico dei caratteri: il parser li segnala con text_length pari a zero perche' non contengono testo estraibile. Per processarli serve un passaggio OCR preliminare con uno strumento esterno (tesseract o servizio cloud) per generare la versione testuale del documento.

Il quarto problema si manifesta al primo lancio di setup.ps1 su Windows con un errore di "execution policy". La PowerShell di Windows blocca per default l'esecuzione di script non firmati come misura di sicurezza. La soluzione una-tantum e' lanciare PowerShell come amministratore e impostare la policy a livello utente.

```
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

```
Il quinto problema riguarda i permessi degli script .sh su macOS e Linux. Dopo il primo clone, i file .sh potrebbero non avere il flag di eseguibilita' e produrre l'errore "Permission denied". La soluzione e' un chmod +x sui file di script.

```
chmod +x setup.sh run_pipeline.sh

```
Il sesto problema si manifesta quando il repository pubblico skills-repo vive su un filesystem non NTFS, tipicamente una cartella sincronizzata via Google Drive con file system FAT32 o exFAT. Git rileva l'inconsistenza dei permessi e rifiuta operazioni con l'errore "dubious ownership". La soluzione e' marcare la directory come sicura nelle configurazioni globali di Git.

```
git config --global --add safe.directory '<percorso-completo-repo>'

```

# Appendice B - Casi operativi

Questa appendice contiene gli otto casi d'uso reali del sistema, con i comandi precisi da eseguire in PowerShell. Il Caso 3, il piu' frequente nella pratica, e' gia' descritto nel corpo principale del diario sotto "Caso operativo end-to-end: aggiornamento di una sorgente reale" e non viene ripetuto qui. I rimanenti sette casi coprono il resto delle situazioni operative: il primo avvio del sistema, gli aggiornamenti incrementali periodici, l'elaborazione di piu' sorgenti in sequenza, la generazione del vault Obsidian privato, la produzione delle sintesi narrative, l'aggiunta manuale di una Capability, e l'utilizzo ortogonale di graphify sulla tassonomia stessa.

Tutti i comandi assumono che le variabili di ambiente LETTERDOC_SKILLS_REPO, LETTERDOC_SOURCE_ONEDRIVE e LETTERDOC_SOURCE_PORTFOLIO siano gia' state settate sulla macchina come descritto in Appendice A. Le variabili in PowerShell si referenziano con la sintassi $env:NOME.

## Caso 1 - Primo run assoluto su una cartella sorgente

Questo e' il caso da seguire la prima volta che il sistema viene utilizzato su una macchina nuova o quando si processa per la prima volta una sorgente che non era mai stata indicizzata. Si apre una sessione Claude Code direttamente nella cartella sorgente e si lancia graphify in modalita' completa (senza il flag --update, perche' non c'e' un run precedente da incrementare).

```
cd $env:LETTERDOC_SOURCE_ONEDRIVE
claude

# Dentro Claude Code:
/model claude-sonnet-4-5
/graphify .

```
L'attesa varia in base alla dimensione del corpus: da una decina di minuti per un corpus medio a una mezz'ora per un corpus grande con duecento o piu' documenti. A fine run si legge graphify-out/GRAPH_REPORT.md per verificare che i god nodes identificati siano coerenti con le aspettative. Si esce da Claude Code e si lancia la pipeline offline.

```
cd E:\lettore-doc

.\.venv\Scripts\python.exe scripts\generate_taxonomy_index.py `
    --output _intermediate\taxonomy_index.json

.\.venv\Scripts\python.exe scripts\enrich_graph.py `
    --graph   "$env:LETTERDOC_SOURCE_ONEDRIVE\graphify-out\graph.json" `
    --workdir "$env:LETTERDOC_SOURCE_ONEDRIVE" `
    --output  _intermediate\enriched_graph.json

.\.venv\Scripts\python.exe scripts\map_to_taxonomy.py `
    --enriched-graph _intermediate\enriched_graph.json `
    --taxonomy       _intermediate\taxonomy_index.json `
    --output-md      _intermediate\taxonomy_diff.md `
    --output-json    _intermediate\taxonomy_diff.json

```
A questo punto si apre il taxonomy_diff.md in un editor, si rimuovono i falsi positivi dalla sezione Fit, si accettano e si rinominano le new Capability proposte, si valutano i new Domain caso per caso. Quando il diff e' ripulito, si applica.

```
notepad _intermediate\taxonomy_diff.md

.\.venv\Scripts\python.exe scripts\export_to_taxonomy.py `
    --diff-json _intermediate\taxonomy_diff.json `
    --skills-repo $env:LETTERDOC_SKILLS_REPO --dry-run

.\.venv\Scripts\python.exe scripts\export_to_taxonomy.py `
    --diff-json _intermediate\taxonomy_diff.json `
    --skills-repo $env:LETTERDOC_SKILLS_REPO --apply

cd $env:LETTERDOC_SKILLS_REPO
git add docs\
git commit -m "Initial taxonomy population from documenti-it"
git push

```
Il workflow GitHub Actions del repository pubblico si attiva automaticamente, esegue mkdocs build --strict, e pubblica il sito su GitHub Pages in circa un minuto. L'URL alesop95.github.io/skills/ riflette il nuovo stato della tassonomia con tutte le evidenze appena iniettate.

## Caso 2 - Aggiornamento mensile su corpus in prevalenza invariato

Questo e' il caso piu' frequente a regime: e' passato un mese dall'ultimo aggiornamento, sono stati aggiunti pochi nuovi documenti alla cartella sorgente, la maggior parte del corpus e' invariata. Il flag --update di graphify processa solo i file il cui hash e' cambiato rispetto al manifest dell'ultimo run, riducendo drasticamente il consumo di token.

```
cd $env:LETTERDOC_SOURCE_ONEDRIVE
claude

# Dentro Claude Code:
/model claude-sonnet-4-5
/graphify . --update

```
Il resto della pipeline e' identico al Caso 1. Il risparmio di token e' proporzionale alla percentuale di file invariati: su un corpus di duecento documenti di cui dieci modificati, il risparmio e' nell'ordine del 95 per cento rispetto a un run completo.

## Caso 4 - Elaborare piu' sorgenti in sequenza

Quando si vogliono processare piu' sorgenti distinte - tipicamente OneDrive aziendale e Portfolio personale su Google Drive - graphify va lanciato separatamente su ciascuna, perche' lo strumento accetta un solo path per invocazione. I file enriched_graph che produce ciascuna sorgente possono poi essere applicati in sequenza sullo stesso repository pubblico, con il meccanismo di idempotenza che garantisce che nessun duplicato venga iniettato.

```
# Sorgente 1: OneDrive
cd $env:LETTERDOC_SOURCE_ONEDRIVE
claude

# /graphify . --update  (poi esci)

# Sorgente 2: Portfolio Google Drive
cd $env:LETTERDOC_SOURCE_PORTFOLIO
claude

# /graphify . --update  (poi esci)

cd E:\lettore-doc

.\.venv\Scripts\python.exe scripts\enrich_graph.py `
    --graph   "$env:LETTERDOC_SOURCE_ONEDRIVE\graphify-out\graph.json" `
    --workdir "$env:LETTERDOC_SOURCE_ONEDRIVE" `
    --output  _intermediate\enriched_graph_onedrive.json

.\.venv\Scripts\python.exe scripts\enrich_graph.py `
    --graph   "$env:LETTERDOC_SOURCE_PORTFOLIO\graphify-out\graph.json" `
    --workdir "$env:LETTERDOC_SOURCE_PORTFOLIO" `
    --output  _intermediate\enriched_graph_portfolio.json

```
A questo punto generate_taxonomy_index.py va eseguito una sola volta (l'indice della tassonomia e' lo stesso per tutte le sorgenti), mentre map_to_taxonomy.py va lanciato due volte, una per ciascun enriched_graph, producendo due diff distinti che vanno revisionati separatamente prima dell'applicazione.

```
.\.venv\Scripts\python.exe scripts\generate_taxonomy_index.py `
    --output _intermediate\taxonomy_index.json

.\.venv\Scripts\python.exe scripts\map_to_taxonomy.py `
    --enriched-graph _intermediate\enriched_graph_onedrive.json `
    --taxonomy       _intermediate\taxonomy_index.json `
    --output-md      _intermediate\taxonomy_diff_onedrive.md `
    --output-json    _intermediate\taxonomy_diff_onedrive.json

.\.venv\Scripts\python.exe scripts\map_to_taxonomy.py `
    --enriched-graph _intermediate\enriched_graph_portfolio.json `
    --taxonomy       _intermediate\taxonomy_index.json `
    --output-md      _intermediate\taxonomy_diff_portfolio.md `
    --output-json    _intermediate\taxonomy_diff_portfolio.json

notepad _intermediate\taxonomy_diff_onedrive.md
notepad _intermediate\taxonomy_diff_portfolio.md

.\.venv\Scripts\python.exe scripts\export_to_taxonomy.py `
    --diff-json _intermediate\taxonomy_diff_onedrive.json `
    --skills-repo $env:LETTERDOC_SKILLS_REPO --apply

.\.venv\Scripts\python.exe scripts\export_to_taxonomy.py `
    --diff-json _intermediate\taxonomy_diff_portfolio.json `
    --skills-repo $env:LETTERDOC_SKILLS_REPO --apply

```
Il commit finale e' un solo git push che pubblica le modifiche di entrambe le sorgenti in un unico aggiornamento del sito.

## Caso 5 - Generazione del vault Obsidian privato

Il vault Obsidian privato e' un output completamente separato dalla pipeline che alimenta il sito pubblico. Serve come strumento di navigazione personale del corpus documentale aziendale e non passa mai per graphify o per skills-repo. Il suo generatore e' lo script run_pipeline.ps1 che orchestra la sequenza parse_docx, extract_entities, build_knowledge_graph, generate_vault.

```
cd E:\lettore-doc
.\run_pipeline.ps1 -SourceFolder $env:LETTERDOC_SOURCE_ONEDRIVE

```
Lo script accetta due flag opzionali che servono in situazioni specifiche. Il flag -Incremental confronta gli hash dei file con quelli del run precedente e processa solo quelli modificati, riducendo il tempo di esecuzione per corpus in prevalenza invariati. Il flag -OnlyVault salta le fasi di parsing, estrazione e grafo, e rigenera solo i file Markdown del vault: e' utile quando si vogliono incorporare nuove sintesi narrative senza riprocessare il corpus dall'inizio.

```
.\run_pipeline.ps1 -SourceFolder $env:LETTERDOC_SOURCE_ONEDRIVE -Incremental
.\run_pipeline.ps1 -SourceFolder $env:LETTERDOC_SOURCE_ONEDRIVE -OnlyVault

```
A fine pipeline il vault si apre in Obsidian con File, Open folder as vault, selezionando E:\lettore-doc\vault-output\. Il file di partenza per la navigazione e' index.md, la Mappa della Conoscenza, che elenca tutti i documenti raggruppati per tipologia, gli hub piu' connessi, i cluster tematici e i documenti isolati. La visualizzazione del grafo si attiva con Ctrl+G in Obsidian.

## Caso 6 - Sintesi narrative dei documenti con il subagente

Le sintesi narrative dei documenti del vault non sono prodotte dagli script Python ma da Claude tramite il subagente lettore-documentazione, definito in .claude/agents/. Si tratta dell'unica parte del sistema che richiede ragionamento linguistico vero, perche' una sintesi narrativa scritta da un essere umano e' qualitativamente diversa da una sequenza di estratti automatici. Le sintesi sono opzionali: se non si generano, le pagine del vault contengono un placeholder al posto della sintesi.

Per generarle, si apre una sessione Claude Code nella cartella del progetto e si chiede al subagente di operare a lotti. Il prompt e' calibrato per produrre sintesi di una lunghezza utile (150-200 parole) in inglese, focalizzate su scopo, tecnologie, output e contesto operativo, senza nomi di clienti. Il prompt esatto da incollare e' il seguente.

```
cd E:\lettore-doc
claude

# Dentro Claude Code, incolla:
Usa il subagente lettore-documentazione.

Genera le sintesi narrative di tutti i documenti in
_intermediate/structure.json che NON hanno gia' un file
in _intermediate/summaries/.

Per ogni documento: leggi sections/<safe-stem>.json, scrivi una
sintesi in INGLESE di 150-200 parole (scopo, tecnologie, output,
contesto operativo, nessun nome di cliente).

Salva in _intermediate/summaries/<safe-stem>.md.

Procedi a lotti di 5. Dopo ogni lotto elenca i file elaborati
e quanti restano.

```
Quando il subagente ha completato le sintesi, si rilancia la pipeline del vault con il flag -OnlyVault per incorporarle nei file Markdown finali senza riprocessare il corpus.

```
.\run_pipeline.ps1 -SourceFolder $env:LETTERDOC_SOURCE_ONEDRIVE -OnlyVault

```

## Caso 7 - Aggiunta manuale di una Capability senza graphify

A volte si vuole aggiungere una Capability alla tassonomia per un'area di competenza nuova senza aspettare il prossimo run di graphify, oppure si vuole creare una Capability che non emergera' mai automaticamente perche' non c'e' ancora documentazione di progetto a supporto. In questi casi si scrive direttamente un nuovo file Markdown nella cartella docs/ del repository pubblico, seguendo lo schema fisso a quattro sezioni H2 che gli script si aspettano.

Il file va creato nel Domain appropriato (sottocartella di docs/) con uno slug significativo nel nome. Il template Markdown da copiare e' il seguente.

```
# Nome Capability

## Overview

Tre-sei righe che descrivono la Capability:
in cosa consiste, perche' e' rilevante, in
quali contesti viene esercitata.

## Technologies & tools

- **Tool 1** (versione) - qualificazione
- **Tool 2** - qualificazione

## Responsibilities & operational scope

- Responsabilita' 1
- Responsabilita' 2

## Projects & evidence

*Project entries are populated automatically from
anonymized project documentation. None yet.*
```
Dopo la creazione del file, va aggiunta manualmente la riga corrispondente nel file mkdocs.yml sotto la sezione del Domain di appartenenza, perche' MkDocs non scopre automaticamente i nuovi file ma li include solo se elencati nella navigazione. Infine commit e push pubblicano la nuova pagina sul sito.

```
cd $env:LETTERDOC_SKILLS_REPO

# Editare mkdocs.yml: aggiungere la riga

# - Nome Capability: <domain>/<slug>.md

git add docs\<domain>\<slug>.md mkdocs.yml
git commit -m "Add capability: Nome Capability"
git push

```
La sezione Projects & evidence del file appena creato resta con il placeholder fino a quando un futuro run di graphify produrra' nodi che il mapping classifichera' come fit per questa nuova Capability, momento in cui export_to_taxonomy.py iniettera' le evidenze sotto il titolo della sezione.

## Caso 8 - Knowledge Graph del portfolio (utilizzo ortogonale di graphify)

Questo caso e' descritto in modo approfondito nel corpo principale del diario sotto Fase G. In sintesi operativa: graphify viene lanciato sulla cartella docs/ del repository pubblico anziche' sulle sorgenti aziendali, e produce un grafo della tassonomia stessa che viene servito come asset statico dal sito MkDocs. L'operazione va eseguita non a ogni aggiornamento del contenuto ma solo quando la struttura della tassonomia cambia significativamente: aggiunta di nuove Capability, riorganizzazione dei Domain, o revisione editoriale ampia.

```
cd $env:LETTERDOC_SKILLS_REPO
claude
/model claude-sonnet-4-5
/graphify docs/
```
Al primo run assoluto su skills-repo, graphify scrive l'output nella root del repository anziche' dentro docs/, e va spostato manualmente perche' MkDocs serve come asset statici solo i file presenti dentro docs/. Dopo lo spostamento iniziale, i run successivi possono scrivere direttamente nella posizione corretta. I file intermedi di graphify (graph.json, manifest.json, cost.json, cartella converted/) vanno esclusi dal controllo di versione per non gonfiare il repository, mentre i due file principali graph.html e GRAPH_REPORT.md vanno committati e pubblicati.

```
# Solo al primo run (poi non serve piu'):
Move-Item graphify-out docs\graphify-out

# Sempre dopo ogni run:
git add docs\graphify-out\graph.html
git add docs\graphify-out\GRAPH_REPORT.md
git commit -m "Update Skills Knowledge Graph"
git push

```

## Tabella di riepilogo dei casi

Per orientarsi rapidamente tra i casi operativi quando si presenta una situazione concreta, la tabella seguente riepiloga il quando-usare-cosa, indicando lo scenario di riferimento, il caso applicabile, e una stima del consumo di token.

| Situazione | Caso | Token |
|---|---|---|
| Primo setup del sistema su sorgente nuova | Caso 1 | Alti (corpus intero) |
| Aggiornamento mensile a regime | Caso 2 | Bassi (solo file modificati) |
| Nuovo progetto appena completato | Caso 3 (corpo) | Bassi (3-10 file) |
| Piu' sorgenti da processare insieme | Caso 4 | Medi (per sorgente) |
| Navigazione locale dei documenti | Caso 5 | Zero |
| Aggiunta di sintesi narrative al vault | Caso 6 | Medi |
| Nuova area di competenza da aggiungere | Caso 7 | Zero |
| Aggiornamento del Knowledge Graph | Caso 8 | Bassi (~45k) |

# Appendice C - Manutenzione, tuning, migrazione

Questa appendice raccoglie le informazioni di tuning e di manutenzione di lungo periodo del sistema. Sono i parametri che probabilmente non andranno mai modificati nei primi mesi d'uso, ma di cui e' utile conoscere l'esistenza per quando emergeranno situazioni che richiedono aggiustamenti. La sezione finale documenta la procedura di migrazione su una macchina nuova, garantendo la continuita' del lavoro indipendentemente dall'hardware sottostante.

## C.1 Soglie di classificazione in map_to_taxonomy.py

Lo script map_to_taxonomy.py classifica i nodi del grafo nelle categorie fit, new_capability, new_domain o non classificato in base a tre soglie numeriche definite in testa al file. La regola operativa per intervenire e' semplice e ben definita: se il diff prodotto contiene troppi falsi positivi tra i fit, va alzata la soglia THRESHOLD_FIT; se le new Capability proposte sono troppo poche rispetto alle aspettative, va abbassata THRESHOLD_DOMAIN; se ci sono molti nodi che finiscono come non classificati nonostante siano riconoscibilmente legati a qualche area di competenza, va abbassata MIN_SCORE_REPORT.

```
# In testa a scripts/map_to_taxonomy.py

THRESHOLD_FIT    = 0.15   # recall minimo per classificare fit
                         # alzare a 0.20 se troppi falsi positivi

THRESHOLD_DOMAIN = 0.08   # recall minimo per new_capability
                         # abbassare a 0.06 se pochi new_capability

MIN_SCORE_REPORT = 0.01   # sotto questa -> non classificato

```
Dopo aver modificato le soglie, e' sufficiente rilanciare map_to_taxonomy.py per produrre un nuovo diff con la classificazione aggiornata. Non e' necessario rilanciare ne' graphify ne' enrich_graph.py perche' l'enriched_graph.json prodotto in precedenza rimane valido.

## C.2 Pesi del grafo in build_knowledge_graph.py

La formula del peso degli archi nel grafo dei documenti del vault privato e' composta da cinque componenti, ciascuna con un peso assegnato. Modificare questi pesi cambia il modo in cui il grafo connette i documenti tra loro. I valori di default sono il risultato di una calibrazione empirica e funzionano bene per documentazione aziendale generica, ma possono essere aggiustati in funzione delle caratteristiche specifiche del proprio corpus.

```
# In testa a scripts/build_knowledge_graph.py

W_JACCARD       = 0.40   # sovrapposizione entita' (Jaccard)
                         # alzare se documenti molto simili in forma
                         # ma diversi in contenuto

W_EXPLICIT_REF  = 0.30   # riferimenti espliciti (vedi X.docx)
                         # saturazione a 3 riferimenti

W_FOLDER        = 0.10   # vicinanza struttura cartelle

W_TEMPORAL      = 0.10   # vicinanza date di modifica
                         # 1.0 a 7gg, 0.0 a 180gg, lineare

W_TITLE_SIM     = 0.10   # similarita' nomi file
                         # alzare per serie ben strutturate v1/v2/v3

MIN_EDGE_WEIGHT = 0.15   # soglia visualizzazione arco
                         # alzare per grafo piu' rado
                         # abbassare per piu' connessioni

MAX_LINKS_PER_DOC = 8    # max vicini mostrati nel vault

```
Dopo la modifica dei pesi, vanno rilanciati build_knowledge_graph.py e generate_vault.py per ricalcolare il grafo e rigenerare il vault con la nuova struttura. graphify non va rilanciato perche' i pesi del grafo influenzano solo il vault privato e non la pipeline di estrazione skill.

## C.3 Regex italiane in extract_entities.py

Lo script extract_entities.py applica dieci categorie di espressioni regolari per riconoscere entita' specifiche della documentazione italiana formale. Le regole calibrate sui pattern piu' comuni funzionano bene per la maggior parte dei casi, ma alcune categorie potrebbero richiedere personalizzazione per documentazione che usa formati non standard. Le tre regex piu' frequentemente personalizzate sono PROJECT_CODE_RE per i codici progetto, la stoplist degli acronimi per filtrare quelli che generano rumore nel proprio dominio, e il pattern delle ragioni sociali che e' gia' completo ma puo' essere esteso.

Se l'azienda usa codici progetto in un formato proprietario come INT2026-08 senza separatore tra prefisso alfabetico e numero, va modificato PROJECT_CODE_RE per catturarlo. Se compaiono molti acronimi tecnici settoriali che il sistema riconosce come entita' ma che in realta' sono troppo comuni per essere distintivi nel proprio contesto, vanno aggiunti a ACRONYM_STOPLIST per essere filtrati. Il pattern COMPANY_SUFFIX_RE copre gia' SpA, Srl, SaS, GmbH, Ltd, Inc e le loro varianti italiane ed estere, ma puo' essere esteso se compaiono forme societarie specifiche di altri ordinamenti giuridici.

Dopo aver modificato le regex, va rilanciato enrich_graph.py partendo dal graph.json gia' prodotto da graphify. Non serve ripetere il run di graphify, che e' la parte computazionalmente piu' costosa della pipeline.

## C.4 Arricchimento delle keyword della tassonomia

La qualita' del matching tra i nodi del grafo e le Capability della tassonomia dipende direttamente dalla ricchezza delle keyword estratte da ciascuna Capability page. Le keyword sono ricavate automaticamente da generate_taxonomy_index.py leggendo le sezioni Technologies & tools e Overview di ogni Capability. Se una Capability ha poche keyword, il matching su quella categoria sara' meno efficace e i nodi rilevanti potrebbero finire come non classificati o nel Domain sbagliato.

La soluzione e' arricchire manualmente le sezioni Technologies & tools e Overview delle Capability che mostrano scarsi risultati nel matching. L'aggiunta di terminologia tecnica precisa, nomi di prodotti specifici, acronimi del settore e frasi che descrivono attivita' operative tipiche aumenta la copertura semantica della Capability e rende piu' probabile che i nodi corrispondenti vengano classificati correttamente. Dopo la modifica delle pagine, va rilanciato generate_taxonomy_index.py per rigenerare l'indice della tassonomia con le nuove keyword. Il file delle DOMAIN_BASE_KEYWORDS in testa allo script contiene invece le keyword di fallback associate a ciascun Domain, usate quando nessuna Capability specifica supera la soglia di matching.

## C.5 Tempi tipici di esecuzione

I tempi di esecuzione della pipeline di estrazione skill scalano con la dimensione del corpus, con la componente piu' variabile rappresentata da graphify che dipende sia dal numero di file che dalla loro lunghezza. La pipeline offline (enrich, mapping, export) ha tempi sostanzialmente costanti perche' opera su rappresentazioni gia' compatte. La revisione manuale del diff e' una funzione lineare del numero di nodi classificati come fit o new_capability. La tabella seguente fornisce una stima realistica delle tempistiche per tre profili di corpus tipici.

| Corpus | graphify | Offline | Revisione | Totale |
|---|---|---|---|---|
| 20-30 file | 2-5 min | 1 min | 5 min | circa 15 min |
| 100-150 file | 10-15 min | 3 min | 15 min | circa 35 min |
| 200+ file | 20-30 min | 5 min | 25 min | circa 55 min |
I valori del tempo di graphify presumono un piano Team Premium con quota disponibile e una velocita' di risposta normale dell'API di Claude. In condizioni di carico elevato sull'infrastruttura Anthropic i tempi possono aumentare. La parte offline non dipende dalla rete e ha tempi sostanzialmente prevedibili sulla stessa macchina.

## C.6 Migrazione del sistema su una nuova macchina

Il sistema e' progettato per essere portatile tra macchine diverse, mantenendo continuita' di lavoro e accesso allo storico. La portabilita' poggia su tre principi: il codice sorgente vive su repository Git, i dati di lavoro sono ricostruibili dal codice e dalle sorgenti, le sorgenti documentali vivono su cartelle sincronizzate cloud accessibili da qualsiasi macchina dopo l'autenticazione al servizio di sincronizzazione.

La procedura di migrazione completa su una macchina nuova si articola in quattro fasi sequenziali. La prima e' l'installazione dei prerequisiti software descritti in Appendice A.1: Python, Claude Code con autenticazione, graphify via pipx, Git con configurazione di username ed email. La seconda fase e' la sincronizzazione delle cartelle cloud: installazione del client Google Drive e/o OneDrive, autenticazione, attesa che le cartelle attese siano sincronizzate fisicamente sulla macchina, configurazione delle eventuali cartelle in modalita' "Mantieni sempre su questo dispositivo" se ci sono file in modalita' solo-cloud.

La terza fase e' il clone dei due repository Git. Il repository privato lettore-doc va clonato su un disco locale, tipicamente sotto E:\ o un percorso equivalente, perche' deve essere sempre disponibile rapidamente per l'esecuzione degli script. Il repository pubblico skills-repo conviene invece clonarlo direttamente sotto la cartella sincronizzata cloud (Google Drive nel setup di riferimento), perche' in questo modo le modifiche fatte sulla macchina si sincronizzano automaticamente verso le altre macchine che hanno lo stesso account.

```
# Repository privato (codice degli script)
cd E:\
git clone git@github.com:alesop95/lettore-doc.git

# Repository pubblico (tassonomia, su cartella cloud sync)
cd "J:\googleDrive_sync\Portfolio\Skills (EN)"
git clone git@github.com:alesop95/skills.git skills-repo

# Su filesystem non NTFS (Google Drive sync, exFAT, FAT32):
git config --global --add safe.directory '<percorso-completo>'

```
La quarta fase e' la configurazione locale del sistema sulla nuova macchina. Si setta una sola volta l'insieme delle variabili di ambiente di sistema con SetEnvironmentVariable scope User da PowerShell, indicando i path locali delle sorgenti, del repository pubblico e del vault. Si lancia setup.ps1 dentro lettore-doc per creare l'ambiente Python isolato e installare le dipendenze. Si edita sources.yml verificando che i path puntino correttamente alle sorgenti previste.

```
[System.Environment]::SetEnvironmentVariable(
    "LETTERDOC_SKILLS_REPO",
    "J:\googleDrive_sync\Portfolio\Skills (EN)\skills-repo",
    "User"
)

[System.Environment]::SetEnvironmentVariable(
    "LETTERDOC_SOURCE_ONEDRIVE",
    "C:\Users\Utente\OneDrive - Azienda\Documenti-IT",
    "User"
)

# Setup ambiente Python isolato
cd E:\lettore-doc
.\setup.ps1

```
Una volta completate le quattro fasi, il sistema sulla nuova macchina e' funzionalmente equivalente a quello della macchina di origine. I file _intermediate/ e vault-output/ non vengono trasferiti perche' sono rigenerabili: si ricostruiscono lanciando un primo run su una sorgente. Il primo run sara' completo (non incrementale) perche' il manifest di graphify del run precedente sulla vecchia macchina non e' presente; a partire dal secondo run, la modalita' --update funzionera' normalmente confrontando con il manifest del primo run sulla nuova macchina.

## C.7 Continuita' di sviluppo come base per un secondo ciclo

Il sistema, una volta completata l'esecuzione dei tre elementi residui descritti nella sezione Stato attuale - finalizzazione del sources.yml con le sorgenti SSD esterno, primo run reale su LETTERDOC_SOURCE_ONEDRIVE, generazione delle sintesi narrative del vault privato - sara' in stato di mantenimento stabile. Da quel punto in poi, il valore aggiunto del sistema cresce proporzionalmente all'uso continuativo: ogni nuovo documento di progetto aggiunto alle cartelle sorgente, processato attraverso il ciclo operativo mensile, va ad arricchire la tassonomia pubblica con evidenze tracciabili e revisionate.

Per un eventuale secondo ciclo di sviluppo, alcuni filoni di estensione sono gia' identificabili. Il primo e' l'integrazione di embedding semantici per migliorare il matching della pipeline di estrazione skill: il recall basato su keyword e' robusto ma non cattura relazioni semantiche tra termini non lessicalmente identici, dove un sistema basato su embedding riconoscerebbe la corrispondenza. Il secondo filone e' la connessione di sorgenti remote tramite altri server MCP - Google Drive nativo, Notion, Confluence - estendendo la pipeline a documentazione che vive fuori dal filesystem locale. Il terzo filone e' l'automazione del passo graphify attraverso un'API key dedicata che consenta l'invocazione non interattiva da script PowerShell, eliminando l'attuale workflow semi-automatico per le sorgenti multiple. Il quarto filone, piu' speculativo, e' l'uso del Knowledge Graph del portfolio come superficie di interazione per query semantiche complesse via natural language, sfruttando il server MCP di graphify che e' gia' incluso nello strumento.

In tutti questi sviluppi futuri, il vincolo architetturale del confine tra dominio privato e dominio pubblico rimane non negoziabile, e qualsiasi nuovo strumento o sorgente va integrato preservando la sanitizzazione obbligatoria al passaggio del confine. Il sistema attuale e' stato costruito intorno a questo vincolo, e le sue estensioni future dovranno rispettarlo per mantenere la sicurezza strutturale che lo caratterizza.

## C.8 Primo run reale - pilot Helpdesk_PC formatting (2026-05-28)

Il primo ciclo di ingest end-to-end su una sorgente reale è stato eseguito sulla subfolder

OneDrive\Documenti - IT\Helpdesk_PC formatting
scelta come pilot per tre motivi: dimensione adatta (24 file di testo + 41 immagini), tema coerente con una Capability già presente ma vuota (
formatting-machines-os.md
), e contenuto tecnico privo di nomi cliente sensibili, utile per validare la pipeline senza vincoli di privacy elevati.

## Infrastruttura aggiunta in questo ciclo

Prima di lanciare il pilot è stato costruito lo state tracking degli ingest, che mantiene
_intermediate\ingest_state.json
con un snapshot sha256+mtime per ogni file di testo di ciascuna subfolder già ingerita, insieme alla data dell’ultimo ingest e al commit del skills-repo associato.

Nuovi script:
scripts\ingest_state.py — CLI con tre comandi (status, track, untrack).
scripts\session_resume.ps1 — wrapper PowerShell che stampa il digest dei delta a ogni apertura di sessione.
scripts\start_graphify.ps1 — launcher dedicato per graphify che forza --model claude-opus-4-7 sulla subfolder sorgente (il default di progetto non si propaga alle sessioni aperte fuori dalla root del repository).

È stato configurato claude-opus-4-7 come modello di default di progetto in .claude\settings.json con un hook SessionStart che lancia automaticamente session_resume.ps1 a ogni nuova sessione. Aggiunta una nuova REGOLA OPERATIVA in CLAUDE.md (“State tracking ingest”) e una sezione “Riprendere il lavoro” in README.md.

## Esecuzione del ciclo

Pre-snapshot: ingest_state.py track ha registrato 24 file di testo (.docx/.txt/.md) come baseline.

Graphify (/graphify . con Opus 4.7) ha prodotto in Helpdesk_PC formatting\graphify-out\ un grafo di 89 nodi, 0 archi nativi, 9 hyperedge calcolati. Costo: circa 183k token in input, 12k token in output, una sola run.

Vault pipeline (run_pipeline.ps1) ha generato un vault Obsidian con 2 nodi (i soli .docx della subfolder; tutti gli altri sono .txt o .md che parse_docx.py non parsa per design).

Skill export pipeline (taxonomy_index + enrich + map + apply): 44 nodi classificati come fit su 8 Capability esistenti, di cui 31 forti su formatting-machines-os. Zero new_capability proposte, 8 new_domain (tutti rumore da descrizioni screenshot/chat, scartati in blocco). Commit risultante sul skills-repo: 19a4ba7.

Re-track: ingest_state.py track --commit 19a4ba7 ha rinfrescato lo snapshot finale (27 file ora, perché graphify ha generato 3 .md in graphify-out\converted\ come byproduct).

## Bug emersi e patchati

### 1. generate_taxonomy_index.py — SyntaxError

I messaggi di errore a riga 195–203 erano stringhe spezzate su più righe senza \n escape né triple-quote. Lo script crashava prima di scrivere taxonomy_index.json e bloccava map_to_taxonomy a cascata. Patchato unificando le stringhe con \n.

### 2. extract_entities.py PROPER_NOUN_RE — falsi positivi CamelCase

La regex non richiedeva spazio obbligatorio tra le due parole capitalizzate, quindi token singoli CamelCase tipo WindowsApp, PowerShell, BitLocker, MicrosoftCorporation venivano matchati come “nomi di persona italiana” e finivano nella anonymization_map come [PERSONA_1..138]. Patch: aggiunto \s+ obbligatorio tra le due capitalizzate + introdotto TECH_BRAND_STOPWORDS (vendor, OS, tool, framework) usato come filtro nel matcher. Risultato dopo patch: 115 voci ancora, ma sono frasi tecniche a due parole tipo “Restore Point”, “Media Feature Pack”, “Object Name”, “Minimum Runtime” — rumore di sfondo che una stop-list manuale non risolve.

### 3. Conclusione sull’anonimizzazione

L’euristica regex+stoplist non scalerà. Per il pilot ho usato --no-anonymize (i preview sono stati iniettati verbatim), valutando manualmente che il contenuto della subfolder non contenesse riferimenti sensibili. Per i prossimi cicli su subfolder con contenuto più formale (ENIVIPA, Cybersec & IT Governance) servierà un modello NER vero (es. spaCy it_core_news_lg) o passaggio a embedding-based classification. Apertura task per la prossima fase di tuning.

## Stato attuale dopo il ciclo C.8
skills-repo: 8 Capability popolate o aggiornate; in particolare formatting-machines-os.md passa da 94 byte (placeholder) a ~14 kB con 31 voci di evidence. Pubblicato su https://alesop95.github.io/skills/formatting-machines-os/ (commit 19a4ba7).
lettore-doc: nuovi script di state tracking, hook SessionStart attivo, default modello Opus 4.7. Commit ab88238.
ingest_state.json: tracciata 1 subfolder (Helpdesk_PC formatting), altre 26 subfolder OneDrive + 14 Portfolio in attesa.

## Prossimi cicli proposti

Subfolder candidate per il prossimo ciclo (criteri: dimensione media, mapping pulito a Capability esistente, contenuto tecnico):
ARCHITETTURA SERVER-CLOUD-LINEE (23 doc, 4 img) — Capability target: infrastructure-virtualization, cloud-platforms.

Helpdesk_RWS-Groupshare-Studio (16 doc, 114 img) — Capability target: software-license-management, advanced-helpdesk.

Miscellaneous procedure e utilities (27 doc, 89 img) — Capability target: system-administration, advanced-helpdesk.

Da fare PRIMA di processare subfolder grandi (ENIVIPA, eGetrad, SCENIA): risolvere il problema anonimizzazione.

## C.9 Anonimizzazione robusta e primo ciclo infrastrutturale (2026-07-14)

Il secondo ciclo di ingest ha preso la subfolder ARCHITETTURA SERVER-CLOUD-LINEE, venti file testuali, ed è servito soprattutto a scoprire che la catena di anonimizzazione costruita fino a quel momento non reggeva un corpus davvero infrastrutturale. Il dry-run iniziale sul grafo grezzo ha mostrato leak sistematici: indirizzi IP interni, hostname, email aziendali, il dominio e persino la sede fisica, non nascosti in fondo a un preview ma direttamente nei label dei nodi. La causa era doppia. La anonymization_map veniva costruita da enrich_graph.py ma non attraversava il confine fra map_to_taxonomy.py e export_to_taxonomy.py, quindi arrivava all'export vuota; e comunque copriva solo le categorie COMPANY e PROPER_NOUN, cioè ragioni sociali e nomi di persona, non le entità di rete.

Il refactor ha toccato quattro punti della catena. extract_entities.py ha imparato a estrarre IP_ADDR, nella forma dotted-quad con CIDR[^22] opzionale, e HOSTNAME, riconosciuto dai prefissi ricorrenti del parco macchine (WIN, SRV, PC-, NAS, USG, VM) e dalla forma dashed uppercase, con una stoplist a contenere i falsi positivi. enrich_graph.py ha esteso la mappa con i placeholder [EMAIL_N], [IP_N] e [HOSTNAME_N]. map_to_taxonomy.py ha cominciato a propagare la mappa dentro il taxonomy_diff.json, chiudendo il buco di trasporto. E export_to_taxonomy.py ha iniziato ad applicarla non solo al preview del body ma anche al label H3 dell'evidenza, al name H1 delle nuove Capability e al label della community.

Due dettagli di quel commit meritano di essere ricordati perché non erano ovvi. Il primo è che lo slug e quindi il nome del file di una nuova Capability va rigenerato dopo l'anonimizzazione e non prima: generandolo dal name originale si otteneva un file pubblicato il cui nome conteneva l'IP che il corpo della pagina aveva diligentemente mascherato. Il secondo è la preservazione del line-ending. Lo script legge ora in binario ogni file esistente per rilevare se usa CRLF o LF e riscrive con lo stesso terminatore, campionando il line-ending del docs-dir per i file creati da zero. Senza questo accorgimento un run su Windows convertiva in CRLF decine di file nati LF, e il diff su GitHub diventava illeggibile: centinaia di righe cambiate di cui nessuna con una modifica reale.

Sopra tutto questo è stato costruito sanitize_taxonomy_diff.py, un gate obbligatorio fra la classificazione e l'export. La logica è la difesa in profondità: la mappa è la prima linea, il gate è la seconda, e presuppone che la prima abbia fallito. Il gate scarta le entries che dopo anonimizzazione restano insignificanti, misurate sui soli caratteri alfanumerici al netto dei placeholder con soglia a dieci, e quelle in cui sopravvive un pattern residuo che la mappa non ha catturato, tipicamente per un mismatch di maiuscole. Per le nuove Capability filtra anche i nodi interni e scarta l'intera proposta se non ne sopravvive nessuno.

L'esito del ciclo è stato di cinquantasei evidenze iniettate su undici pagine Capability, con un diff di +551 / -6 linee dove le sei rimozioni sono i placeholder "None yet" delle pagine fino ad allora vuote. Due nuove Capability sono state suggerite ma non pubblicate, sia perché i titoli conservavano un placeholder residuo [IP_7], sia perché la semantica era di basso livello: "Winsrv2019 Vm" e "Windows Acl QTS" descrivono configurazioni, non competenze. Commit del repository pubblico bbd361e. Nella stessa sessione è stato installato nel virtualenv il modello NER[^23] italiano it_core_news_lg, che risultava assente lasciando attivo il fallback a regex e stoplist, ed è stato aggiunto il parametro -Account a start_graphify.ps1 per scegliere l'account Claude su una macchina che ne ha più di uno.

Una nota di metodo che vale oltre il ciclo: la selezione del workspace sanitizzato è stata manuale, e tre sottocartelle sono state escluse a priori perché contenevano configurazioni di firewall Zyxel e report SECUREPORTER, identificate con un grep su credenziali, PSK[^24] e indirizzi IP prima ancora di lanciare la pipeline. Il gate automatico esiste, ma non sostituisce lo sguardo su cosa si dà in pasto al sistema.

## C.10 Nav MkDocs a tre livelli e il confine graphify (2026-07-15)

Due interventi piccoli e indipendenti, entrambi nati da un vincolo implicito che si era irrigidito senza che nessuno lo avesse deciso.

Il primo riguarda generate_taxonomy_index.py. La funzione parse_nav assumeva che il nav di MkDocs fosse piatto, cioè Domain seguito direttamente dalle Capability foglia. Quando il sito pubblico ha introdotto un livello intermedio di sotto-area, l'indice si è semplicemente svuotato per quei rami. La funzione è stata riscritta con due helper, _collect_leaves che scende ricorsivamente fino alle foglie e _build_domain che costruisce il dizionario del domain, così da reggere sia la forma a due livelli sia quella a tre. Il domain_dir viene calcolato in stile POSIX per non produrre indici diversi a seconda del sistema operativo. Il contratto verso il resto della pipeline non cambia: il taxonomy_index.json conserva la stessa struttura domains[*].capabilities[*], e nessuno script a valle si accorge della differenza.

Il secondo è la versionatura di .graphifyignore. Il file esisteva ed era operativo da tempo, usato in tutte le sessioni graphify, ma non era tracciato da git: una lista di esclusione critica che viveva solo su disco, invisibile a qualsiasi review. È una copia intenzionale di .gitignore con una sola differenza deliberata, l'assenza di _intermediate/, perché graphify deve poter indicizzare i sorgenti sanitizzati in _intermediate/src/ che invece git esclude per riservatezza. La divergenza fra due liste quasi identiche è però esattamente il tipo di errore che non si nota, quindi insieme al file è stata scritta in CLAUDE.md una regola operativa che vincola l'allineamento manuale delle due e dichiara _intermediate/ come unica differenza ammessa. Ora, quando una lista viene toccata e l'altra no, il fatto compare nel diff.

## C.11 Ciclo Cybersec governance baseline (2026-07-16)

Il terzo ciclo ha affrontato il segmento Cybersecurity & IT Governance, ed è stato impostato deliberatamente come test piccolo su un corpus grande. La subfolder OneDrive di riferimento contiene quattrocentoquarantasette file testuali distribuiti su diciotto sottodirectory tematicamente eterogenee, dalla cifratura at-rest alla business continuity ai questionari fornitori. Mescolarle in un unico grafo avrebbe prodotto una community detection incoerente e una review manuale ingestibile, quindi la selezione è stata fatta per coesione semantica e non per volume: tre subfolder che insieme formano un blocco governance e policy compatto, e dentro quelle una scelta manuale di cinque documenti di policy generale.

Le esclusioni sono più istruttive delle inclusioni. Sono rimasti fuori Registro_accettazione.docx perché contiene firme di dipendenti, Data Branch-bando.docx perché è un caso specifico e non una procedura, il duplicato più vecchio di Configurazione-PC-Password.docx, tutti i .pdf che la pipeline non processa, e il Registro_Data_Breach.xlsx che è insieme non processabile e pieno di dati personali per definizione.

I numeri del ciclo. Graphify ha prodotto settantacinque nodi, centodue link e cinque community. La mappa di anonimizzazione si è fermata a cinque voci, ed è un dato interessante di per sé: zero aziende, zero IP, zero hostname, una email pubblica di supporto Microsoft e quattro voci PERSONA, di cui tre falsi positivi del NER su testo di intestazione e una sola vera, il ruolo "Amministratore di Sistema". Un corpus di policy interne, a differenza di uno infrastrutturale, quasi non contiene entità da mascherare. La classificazione ha dato trentasei fit, una nuova Capability proposta, cinque nuovi Domain e venticinque nodi non classificati. Il gate di sanitizzazione ne ha tenuti trentaquattro, scartando "Amministratore di Sistema" e "Area IT" perché dopo anonimizzazione restavano sotto la soglia dei dieci caratteri alfanumerici. L'export ha prodotto trenta iniezioni su cinque Capability, +298 / -2 linee, e il commit 5f2af1c sul repository pubblico.

La review manuale è però stata pesante, ed è il vero risultato del ciclo. Diciotto fit su trentaquattro sono stati spostati a mano da quality-certification a cybersecurity-it-governance, e altri quattro sono stati rimossi perché palesemente fuori posto: gpedit.msc finito in Ad-hoc Internal Development, un sistema di filtri di categorie di siti in IT Administration & Billing, il server aziendale e il backup dati in Cloud Platforms. Tutti i nuovi Domain e la nuova Capability sono stati scartati per punteggio troppo basso, nodo singolo o label di community rumorosa. Metà delle evidenze pubblicate, in altre parole, è passata da una correzione umana. Un ciclo che richiede quel livello di intervento non è ripetibile, ed è da qui che nascono le due scoperte descritte in C.12.

## C.12 Chiusura del debito e correzione delle due scoperte (2026-07-27)

Questa sezione chiude un debito documentale di circa due mesi: l'ultimo allineamento del diario risaliva al 2026-05-28, mentre nel frattempo erano entrati i tre cicli descritti in C.9, C.10 e C.11. La sessione ha aggredito le due scoperte lasciate aperte dal ciclo Cybersec, e in un caso ha dovuto correggere la diagnosi che ne era stata data a caldo.

### Il filtro dei nomi di graphify

La prima scoperta era che graphify 0.8.14 scarta i file il cui nome contiene password, credential, secret, token o private_key, oltre alle estensioni di materiale crittografico e ai file sotto directory di segreti note. È una protezione ragionevole sul caso d'uso generale e diventa un falso positivo sistematico sul nostro: una policy IT aziendale si chiama per forza di cose "Configurazione-password-Windows", ed è esattamente il documento da indicizzare. Il punto grave non è lo scarto ma la sua invisibilità. Il campo diagnostico skipped_sensitive esiste, ma nel ciclo Cybersec è risultato vuoto, perché si popola in un loop a valle di un pre-detect che aveva già concluso total_files: 0; la sessione ha quindi deciso needs_graph: false senza eseguire nulla, e tre documenti su cinque sono spariti senza lasciare traccia.

Il workaround adottato allora era stato una cartella parallela con i file rinominati a mano e convertiti in Markdown. Ora quel passo è uno script, scripts/prepare_graphify_source.py. In modalità di sola verifica, che è il default, elenca quali file graphify scarterebbe e con quale nome verrebbero sostituiti, senza scrivere nulla. Con --apply genera la cartella <nome>-sanitized/ con i documenti convertiti in Markdown riusando parse_docx.py, i nomi neutralizzati secondo una mappa esplicita in italiano, e il frontmatter di tracciabilità che registra il file di origine, la subfolder e la data. Il filtro di graphify è replicato e non importato, perché graphify vive in un virtualenv pipx separato e perché un cambiamento delle sue regole deve rompere qui in modo visibile invece di alterare in silenzio il comportamento della pipeline.

Due scelte di merito. La prima è che si neutralizza il nome, mai il contenuto: il corpo del documento continua a dire "password" ovunque, e la protezione contro la fuga di dati resta interamente affidata alla catena di anonimizzazione e al gate residue, che questo passo non sostituisce né indebolisce. Il problema risolto è di indicizzabilità, non di riservatezza. La seconda è che i file di vero materiale crittografico, riconosciuti per estensione, non vengono rinominati affatto: lì il filtro di graphify ha ragione e restano fuori dal corpus. Come verifica di ritorno lo script rilegge l'output e rilancia il filtro sui nomi appena scritti, uscendo con codice due se un file lo attiva ancora, così la mappa di sostituzione non può fallire in silenzio. La validazione è stata fatta contro la cartella prodotta a mano il 16 luglio: i cinque nomi generati coincidono esattamente con quelli scelti allora.

### Il misrouting delle evidenze GDPR, e perché la diagnosi era sbagliata

La seconda scoperta era stata annotata come una keyword certification troppo generica nel vocabolario di Quality Certification, che catturerebbe come falsi positivi i nodi che parlano di certificazione, Regolamento, WP250 e Provvedimento. L'indagine di oggi mostra che questa spiegazione non regge: certification compare nel vocabolario di entrambe le pagine e non ha mai deciso un solo match. La causa vera è duplice.

Il primo fattore è un bug reale in generate_taxonomy_index.py. Le keyword di una Capability venivano estratte concatenando la sezione Technologies and tools e la sezione Overview, e la lista risultante veniva poi tagliata alle prime sessanta voci. Su una pagina con una sezione tecnica lunga il taglio non toglieva la coda di entrambe le sezioni: eliminava per intero il contributo della seconda, cioè proprio l'Overview, che è la sezione dove una pagina dichiara il proprio perimetro. Sulla pagina Cybersecurity & IT Governance il taglio faceva sparire gdpr, penetration, testing e malware, ovvero i termini che la distinguono dalle vicine. Cinque Capability su trentuno erano in questa condizione. La correzione fonde le due sezioni alternandole a giro invece di concatenarle, così il taglio non può azzerare nessuna delle due, e stampa un avviso su standard error che elenca le pagine troncate e di quanti token, perché il troncamento silenzioso è precisamente ciò che ha reso il problema invisibile per tre cicli.

Il secondo fattore, e quello davvero decisivo, non era un bug affatto. Il token che decideva il match era breach, presente nel vocabolario di Quality Certification e assente da quello di Cybersecurity & IT Governance, per il semplice motivo che la prima pagina dichiarava nel proprio Overview "GDPR data-breach handling" e nelle Technologies "GDPR + Italian Legislative Decree 51/2018, data breach register", mentre la seconda si limitava a "regulatory compliance (GDPR, ISO/IEC 27001 implementation path)" senza nominare mai il data breach. Lo scoring stava leggendo correttamente due pagine che si contendevano lo stesso perimetro, e assegnava le evidenze a quella che rivendicava il termine specifico. Non c'era niente da correggere nel codice: c'era una decisione di proprietà da prendere nella tassonomia.

La decisione presa è che il perimetro GDPR e data breach appartiene a Cybersecurity & IT Governance. Le due pagine pubbliche sono state riscritte di conseguenza, spostando il vocabolario di risposta al data breach, cioè registro, notifica al Garante entro settantadue ore, articoli 33 e 34, comunicazione agli interessati, nell'Overview e nelle Technologies della pagina di sicurezza. Su Quality Certification la rivendicazione è stata rimossa dalle due sezioni che alimentano il matching, ma il contributo reale resta documentato nella sezione Responsibilities, che non concorre alle keyword, con un rimando esplicito alla pagina che ora possiede il processo. La pagina continua quindi a dire il vero su cosa è stato fatto, senza più attrarre le evidenze.

Il risultato è verificabile sul corpus del ciclo chiuso. Prima, la classificazione automatica mandava diciotto evidenze a Quality Certification e una sola a Cybersecurity & IT Governance, e serviva la correzione manuale di diciotto fit per ottenere il risultato giusto. Dopo, l'automatismo ne manda venti a Cybersecurity & IT Governance e zero a Quality Certification, riproducendo da solo ciò che l'essere umano aveva dovuto imporre a mano. Vale la pena notare che il pubblicato era già corretto: la revisione manuale obbligatoria del taxonomy_diff.md aveva fatto il suo lavoro. Il costo che questa correzione elimina non è un errore sul sito, è la necessità di rifare quella stessa correzione a ogni ciclo futuro.

Un terzo intervento minore è nato per contraccolpo. Rendendo equo il taglio a sessanta keyword, la pagina di sicurezza cominciava a perdere nessus, esxi e vcenter, cioè vocabolario tecnico legittimo. Uno sweep del tetto a sessanta, novanta, centoventi e senza tetto sullo stesso corpus ha prodotto la stessa identica classificazione in tutti e quattro i casi: il tetto non è un parametro di tuning con effetto osservabile, è solo una guardia contro una pagina patologicamente lunga, che avrebbe punteggi alti per sola cardinalità del proprio vocabolario. È stato quindi portato a novanta, valore che sul nav attuale lascia intatte tutte le pagine tranne System Administration, che ne perde quattro.

### Un residuo di amplificazione, non risolto

Resta sul tavolo un terzo meccanismo, individuato ma non affrontato. classify_nodes unisce ai token del nodo anche i token del nome della sua community, e nel ciclo Cybersec questo significava iniettare allegato, breach, comunicazione, data, interna e modulo in ogni singolo nodo di quella community. Su un nodo il cui label produce tre o quattro token, sei token vengono quindi dalla community e non dal nodo: l'effetto è che l'intera community si muove in blocco verso la stessa destinazione invece che essere valutata nodo per nodo. È il motivo per cui l'errore, quando si verifica, non riguarda mai una evidenza sola ma diciotto insieme. Se sia un difetto o un comportamento voluto dipende da quanto si crede alla community detection, e la valutazione è rimandata a un ciclo in cui il fenomeno produca un errore osservabile.

### Tooling del diario

Infine, la procedura di aggiornamento di questo documento è diventata due script. scripts/open_diary.ps1 apre il .docx in Word ed elenca i draft più recenti presenti nello scratchpad di sessione, così che chi edita sappia cosa incollare. scripts/finalize_diary.ps1 chiude il ciclo: rigenera il .md invocando sync_diary_md.py, mostra il diff del solo .md come review testuale che un binario non consente, e stampa i comandi git nel doppio blocco PowerShell e bash. Nessuno dei due esegue git, che resta manuale per politica di progetto. In CLAUDE.md sono stati aggiunti tre momenti in cui l'agente ricorda da solo di aggiornare il diario: a fine ciclo di ingest, all'apertura di sessione quando il ritardo supera i sette giorni, e a valle di un refactor architetturale. Il debito che questa sezione chiude è esattamente ciò che quei promemoria esistono per prevenire.

## C.13 Ciclo Cybersec endpoint governance, e la fuga dai nomi dei file (2026-07-28)

Il quarto ciclo di ingest è nato con un obiettivo dichiarato oltre a quello ordinario: verificare sul campo se le correzioni al routing fatte il giorno prima reggessero su un corpus nuovo. La risposta è sì, ma il ciclo ha scoperto tre difetti che nessuna delle verifiche precedenti aveva intercettato, e uno dei tre era una fuga di dati vera nel repository pubblico.

### La selezione, e cosa è stato tenuto fuori

Il segmento Cybersecurity & IT Governance della sorgente OneDrive conta quattrocentocinquanta file testuali, dei quali nove erano stati lavorati nel ciclo di luglio. La selezione di questo ciclo prende _Bitdefender (endpoint security) per intero, sei documenti su migrazione da ESET a Bitdefender, protezione LAN ed eccezioni endpoint, e vi aggiunge tre documenti di governance non problematici pescati dal blocco GDPR e ISO27001: la politica PSGSI di sicurezza delle informazioni, un template ISO27001 e un brief su DORA.

Le esclusioni raccontano più delle inclusioni, e sono state fatte leggendo i nomi dei file prima di aprirli. Sono rimasti fuori un accordo di non divulgazione intestato a una persona nominata, due deleghe che portano cognomi nel nome del file, e soprattutto un documento su dati sanitari e donazione riferito a una persona identificabile, che è categoria particolare ai sensi dell'articolo 9 del Regolamento e non ha alcuna collocazione in una tassonomia pubblica di competenze. Sono rimasti fuori anche i report di rischio prodotti da due fornitori sull'infrastruttura reale, con domini e indirizzi IP: pubblicare l'esito di un vulnerability assessment significa divulgare le debolezze di un'organizzazione reale, e la sostituzione con placeholder non rende quel materiale accettabile, perché il problema non è l'identificabilità ma il contenuto. Fuori anche i centoventisei questionari fornitori, che sono dati commerciali di terzi, e la polizza assicurativa post-disaster.

Due file avevano nomi che, staccati dal loro albero di cartelle, perdevano ogni significato: 09092025.docx e primo accesso.docx. Sono stati prefissati con il tema della sottocartella di origine, perché un nome così diventa una label incomprensibile nel grafo e quindi un'evidenza inutile nella pagina pubblica.

### Il collaudo del routing

Il pre-flight introdotto il giorno prima ha riportato nove documenti su nove che passano il filtro sui nomi di graphify: su questo corpus quel filtro non morde, ma la cartella sanitizzata serve comunque per la conversione in Markdown. graphify ha prodotto trentacinque nodi, cinquantatré collegamenti e sette community, con il sistema di gestione della sicurezza delle informazioni come nodo più connesso del grafo, nove archi, e una distribuzione di confidenza del sessantotto per cento estratto contro trentadue per cento inferito.

Il risultato che interessava è che la classificazione automatica ha mandato ventitré evidenze su ventiquattro a Cybersecurity & IT Governance e nessuna a Quality Certification. Lo spostamento di proprietà del perimetro GDPR fatto il giorno prima tiene, e non è stato necessario alcun intervento su quel fronte.

La revisione manuale ha comunque trovato cinque assegnazioni da correggere su ventotto, contro le diciotto su trentaquattro del ciclo precedente. La causa però è diversa, e vale registrarla perché è la prossima da affrontare: token generici come IP e firewall pesano più del contesto, e trascinano verso Networking Engineering and Security nodi che parlano di eccezioni antivirus e di hardening degli endpoint. Il caso più netto è il sistema di gestione della sicurezza delle informazioni finito in IT Administration and Billing, cioè il nodo più connesso dell'intero grafo assegnato alla pagina sbagliata. L'unica assegnazione fuori dalla pagina di sicurezza che è stata confermata è il problema di connessione RDP sulla rete locale, che è davvero troubleshooting di rete.

### La fuga, e perché il riepilogo non l'aveva vista

L'export ha dichiarato ventotto iniezioni, zero salti, zero file mancanti, e il controllo con git diff -w --numstat ha mostrato solo aggiunte, duecentosessantasette righe su una pagina e dieci sull'altra. Tutti i segnali erano verdi. Cercando però le stringhe sensibili dentro il diff, prima di committare, sono comparse quattordici occorrenze della ragione sociale e una dell'hostname di una postazione.

Il vettore non era il testo delle evidenze, che la catena di anonimizzazione tratta da luglio, ma i nomi dei file. Un documento aziendale si chiama per forza di cose "Protezione avanzata (LAN) Intrawelt.docx" oppure "advancedIPscanner eccezione su PC-ALESSIO.docx", e quel nome arrivava nel repository pubblico per due strade indipendenti. La prima è la riga - **Source**: di ogni blocco di evidenza, che export_to_taxonomy.py scriveva verbatim senza farla passare per la funzione di sostituzione, a differenza del label, del titolo e del preview. La seconda è più insidiosa: il preview del corpo erano i primi duecento caratteri del file sanitizzato, e quel file apre con il frontmatter di tracciabilità, che contiene un campo source_file con il nome del documento di partenza. La fuga entrava quindi anche nel corpo, aggirando la mappa dall'interno.

La correzione è distribuita su tre livelli, coerentemente con la difesa in profondità del resto della catena. enrich_graph.py salta il frontmatter prima di costruire il preview, e questo come effetto secondario migliora ogni evidenza futura, perché i duecento caratteri diventano contenuto invece che metadato. export_to_taxonomy.py fa passare il nome del file per la sostituzione come qualsiasi altro testo. E sanitize_taxonomy_diff.py, che ispezionava soltanto il label, ispeziona ora anche il nome file e il preview: su questi due campi però scruba, sostituendo il residuo con un marcatore e tenendone il conto nel report, invece di scartare l'evidenza. La distinzione è deliberata. Un label che contiene un residuo, una volta scrubato, rischia di non voler dire più nulla, e allora tanto vale scartare la voce; una ragione sociale nel nome di un documento non rende l'evidenza inutile, la rende soltanto non pubblicabile in quella forma. Con lo scarto si sarebbero perse venti evidenze buone.

Va detto che il difetto era preesistente e non nasce con questo ciclo: le evidenze pubblicate il sedici luglio hanno tutte un preview che comincia dal frontmatter. Per fortuna quei nomi di file non contenevano ragione sociale, quindi non c'è stata divulgazione, ma la qualità di quelle voci era già compromessa.

La lezione di metodo conta più delle tre patch. Il riepilogo di uno script che dichiara successo non è una verifica di riservatezza, e nemmeno il conteggio delle righe aggiunte: dicono che l'operazione ha funzionato, non che ciò che ha scritto sia pubblicabile. La verifica che ha funzionato è stata cercare esplicitamente nel diff i cognomi noti, il dominio aziendale, la ragione sociale nuda, gli indirizzi interni e gli hostname del parco macchine, e in parallelo contare quante sostituzioni fossero state effettivamente applicate, perché zero mascherature su un corpus aziendale è un dato più sospetto di molte. Il momento giusto per farlo è con l'--apply già eseguito e nulla ancora committato, cioè nella finestra in cui un git checkout annulla tutto. Questo passo è ora scritto fra i controlli obbligatori del progetto.

### Due falsi positivi che danneggiavano l'evidenza

Gli altri due difetti riguardano l'estrazione delle entità, e hanno in comune una caratteristica interessante: non erano fughe, erano sovra-protezioni che rovinavano il risultato. Il primo è che la parola WINDOWS veniva riconosciuta come hostname e mascherata, in un corpus di sicurezza degli endpoint dove quella parola è dappertutto. La causa non era una regola mancante, ed è questo il punto interessante: Windows era già presente nella lista dei marchi da ignorare, ma il confronto su quel percorso era sensibile alle maiuscole, mentre le due espressioni regolari che riconoscono gli hostname per costruzione catturano solo testo maiuscolo. Il filtro esisteva e non era mai scattato. Il confronto avviene ora su una versione minuscola precalcolata della lista, che protegge per la stessa ragione anche LINUX, UBUNTU e simili.

Il secondo è che il riconoscitore di entità nominate produceva porzioni di testo che attraversavano le interruzioni di riga, e così una voce della mappa partiva da "Bitdefender Gravityzone" e proseguiva per tre righe inglobando residui di un template. Mascherare quella stringa avrebbe significato nascondere il prodotto centrale del corpus, cioè esattamente la competenza che la pagina pubblica deve dichiarare. Il vincolo aggiunto è banale nella forma e solido nella sostanza: un nome di persona non attraversa un'interruzione di paragrafo. Alla lista dei marchi sono stati aggiunti i fornitori di sicurezza, che nel dominio di questo progetto ricorrono continuamente e sono l'ultima cosa da offuscare.

### Il limite che nessuna correzione lessicale supera

Un nodo del grafo è rimasto non classificato con punteggio esattamente zero: la politica PSGSI di sicurezza delle informazioni, che è il documento di governance più importante dei nove selezionati. Il motivo non è una soglia troppo alta né una parola chiave mancante. Il corpus è in italiano e il vocabolario della tassonomia è in inglese, quindi una etichetta come Politica Sicurezza Informazioni non ha un solo token in comune con security, policy o compliance, e prende zero a prescindere da quanto sia pertinente. È lo stesso limite di fondo del misrouting risolto il giorno prima, il match puramente lessicale, ma in una forma che curare il vocabolario delle pagine non tocca nemmeno. Finché la funzione di punteggio resta un rapporto di token condivisi, questa classe di casi va recuperata a mano in revisione, e l'unica soluzione strutturale è il passaggio a una rappresentazione semantica, cioè la voce sugli embedding che era in lista fra le estensioni possibili e che questo ciclo promuove da idea a necessità.

### Chiusura

Ventotto evidenze iniettate su due pagine Capability, ventisette sulla sicurezza e una sulla rete, solo aggiunte, build del sito verde. Lo stato di ingest è stato aggiornato sulla sola sottocartella Bitdefender, non su quella di governance: di quest'ultima sono stati lavorati tre documenti su tredici, e registrarla per intero l'avrebbe fatta sparire dai riepiloghi futuri con delta zero, nascondendo i dieci non lavorati. Lo stato serve a sapere cosa resta da fare, e va tenuto onesto anche quando questo significa vedere una sottocartella ricomparire a ogni apertura di sessione.

# Lezioni apprese

Prima di costruire qualcosa di nuovo, vale sempre la pena verificare se la funzionalita' necessaria esiste gia' nel codice esistente. Il piano a quattro script sarebbe risultato in meno di duecento righe di codice che replicavano una versione notevolmente piu' povera di cio' che parse_docx.py e extract_entities.py gia' facevano. Il tempo investito nell'analisi del sistema esistente prima di progettare il nuovo ha eliminato mesi di lavoro ridondante.

La separazione fisica tra due repository è piu' robusta di qualsiasi .gitignore complesso. Il costo cognitivo del ricordare cosa si può committare e cosa no in un monorepo non è trascurabile, ed è una superficie di rischio reale in un sistema che gestisce dati sensibili. Con due repository fisicamente distinti, il confine tra privato e pubblico è eliminato per costruzione: il repository pubblico non può fisicamente contenere file che non siano stati esplicitamente scritti dallo script ponte.

I filename delle pagine Capability sono URL permanenti. Nel momento in cui un link viene inserito in un curriculum vitae stampato o in una versione PDF inviata a terzi, quel filename diventa immutabile: rinominarlo rompe il link. La decisione va presa con attenzione prima della prima distribuzione del CV, e non modificata successivamente se non in casi straordinari e con consapevolezza delle conseguenze.

Il problema del volume della documentazione rispetto alla finestra di contesto si risolve non con il chunking del testo, ma con livelli di astrazione progressivi. Il corpus intero in forma di scheletro entra in meno di trentamila token. Le sezioni-preview dei documenti rilevanti entrano in venti-trentamila token. La sezione specifica di interesse entra in poche migliaia di token. Questo cambia il costo dell'operazione di un ordine di grandezza rispetto all'approccio naive di caricare i documenti integrali.

MkDocs serve come asset statici tutti i file nella cartella docs/, non solo i file Markdown. Questa caratteristica, non immediatamente ovvia dalla documentazione, rende possibile includere nel sito file HTML arbitrari, visualizzazioni interattive, o qualsiasi altro contenuto web standalone, senza nessuna configurazione aggiuntiva. Il file graph.html prodotto da graphify ne è l'applicazione diretta: un file HTML con grafo interattivo, librerie JavaScript incorporate, e funzionamento completamente offline, che diventa una pagina pubblica del sito semplicemente posizionandolo nella cartella docs/.

Qualsiasi script che scrive in un repository deve essere idempotente. Il meccanismo dei commenti HTML invisibili con hash breve come identificatore stabile risolve questo problema in modo semplice, non invasivo per il rendering, e compatibile con qualsiasi strumento che elabori Markdown standard. È una tecnica applicabile a qualsiasi scenario in cui si voglia iniettare contenuto generato automaticamente in file curati manualmente senza rischio di duplicazione.

---

## Note

[^1]: MkDocs Material e' un generatore di siti statici costruito sopra MkDocs, lo strumento open source per la documentazione tecnica in Python. Il tema Material, sviluppato e mantenuto da Martin Donath, aggiunge ricerca full-text, navigazione a sidebar, dark mode, syntax highlighting per blocchi di codice, responsive design e URL puliti con use_directory_urls. La build si avvia con mkdocs build e produce una cartella _site/ con HTML, CSS e JavaScript statici pronti per qualsiasi server o CDN.

[^2]: GitHub Pages e' il servizio di hosting statico gratuito offerto da GitHub. Puo' pubblicare il contenuto di un branch o di una GitHub Action. Per i repository pubblici e' disponibile nel piano gratuito senza limitazioni di banda significative. L'URL generato segue il pattern username.github.io/nomerepo per i project site, oppure username.github.io per lo user site (creato da un repository con nome uguale a username.github.io).

[^3]: GitHub Actions e' la piattaforma di CI/CD integrata nativamente in GitHub. Ogni workflow e' definito da un file YAML nella cartella .github/workflows/ del repository e si attiva su eventi configurabili, come un push su un branch specifico. Nel progetto skills-repo, il workflow deploy.yml esegue la build MkDocs e pubblica il risultato su GitHub Pages ad ogni push sul branch main. Il tempo medio di completamento e' di circa un minuto dall'invio del commit.

[^4]: Per token si intende l'unita' atomica di elaborazione di un LLM. Un token corrisponde approssimativamente a quattro caratteri di testo inglese o italiano; una parola comune conta come un token singolo, mentre una parola rara o una sequenza numerica puo' generarne piu' di uno. La finestra di contesto di un modello Sonnet e' di circa 200.000 token, equivalenti a circa 150.000 parole o 500 pagine di testo denso.

[^5]: LLM, acronimo di Large Language Model, indica una classe di modelli di intelligenza artificiale addestrati su corpus testuali di grandissime dimensioni. Questi modelli producono testo statisticamente coerente con l'input ricevuto e sono in grado di svolgere compiti come estrazione di informazioni, sintesi, classificazione, generazione di codice e ragionamento strutturato senza essere stati addestrati specificamente su ciascuno di questi compiti.

[^6]: Claude Code e' un'interfaccia a riga di comando sviluppata da Anthropic che consente al modello Claude di operare direttamente sul filesystem locale, eseguire comandi shell, leggere e scrivere file, e lanciare script. Si distingue da Claude.ai (l'interfaccia web) perche' ha accesso agli strumenti del sistema operativo e puo' essere dotato di istruzioni persistenti tramite un file CLAUDE.md posizionato nella root del progetto, che viene letto automaticamente all'avvio di ogni sessione.

[^7]: Con API, acronimo di Application Programming Interface, si intende un insieme di endpoint esposti da un servizio software che consentono ad altri programmi di interagire con esso in modo standardizzato. Nel contesto di questo documento, 'chiamare l'API Anthropic' significa inviare una richiesta HTTP al servizio di inferenza di Anthropic passando il testo da analizzare, ricevendo in risposta il testo generato dal modello. Questo servizio ha un costo per token elaborato.

[^8]: JSON, acronimo di JavaScript Object Notation, e' un formato di serializzazione testuale dei dati strutturati basato sulla sintassi degli oggetti JavaScript. E' ampiamente usato per lo scambio di dati tra applicazioni per la sua leggibilita' umana e la facilita' di parsing in tutti i principali linguaggi di programmazione. Nel pipeline descritto, tutti i file intermedi tra gli script sono in formato JSON.

[^9]: Le espressioni regolari, comunemente abbreviate come regex, sono sequenze di caratteri che definiscono un pattern di ricerca testuale. In Python sono implementate nel modulo re della libreria standard. Una regex come [A-Z]{2,7} corrisponde a qualsiasi sequenza di due-sette lettere maiuscole consecutive. Nell'estrattore di entita', ogni categoria di entita' e' definita da una o piu' espressioni regolari calibrate sulle strutture linguistiche tipiche dell'italiano formale aziendale.

[^10]: NER, acronimo di Named Entity Recognition, e' il processo automatico di identificazione e classificazione di riferimenti a entita' del mondo reale in un testo: persone, organizzazioni, luoghi, date, importi. I sistemi NER tradizionali usano modelli di machine learning addestrati su corpus annotati. Il sistema descritto usa invece un approccio a espressioni regolari con euristica linguistica, che e' piu' rapido, deterministico e non richiede dipendenze ML, a scapito di una minore generalizzazione.

[^11]: graphify e' uno strumento proprietario sviluppato da Safwan Shamsi che si integra come skill registrata all'interno di Claude Code. Riceve una cartella come input, converte i file .docx in Markdown tramite la libreria python-docx, analizza le immagini in modalita' vision, e usa il modello Claude attivo nella sessione per costruire un grafo semantico dei concetti e delle relazioni presenti nei documenti. L'output principale e' un file graph.json strutturato con nodi, archi, community e punteggi di confidence, piu' un file graph.html per la visualizzazione interattiva. Si installa con pipx install "graphifyy[office]" e si registra con graphify install --platform windows.

[^12]: Un algoritmo force-directed e' una tecnica di layout per grafi che simula un sistema fisico in cui i nodi si respingono come cariche elettriche e gli archi li attraggono come molle. L'equilibrio del sistema posiziona automaticamente i nodi in modo da minimizzare le sovrapposizioni e avvicinare i nodi connessi. Il risultato e' una visualizzazione che rivela visivamente la struttura topologica del grafo, con cluster di nodi strettamente connessi e hub centrali chiaramente identificabili.

[^13]: Il .gitignore e' un file di configurazione riconosciuto da Git che specifica quali file e cartelle devono essere ignorati dal controllo di versione. Le righe che contengono pattern come .venv/ o _intermediate/ impediscono che queste directory vengano incluse nei commit, anche se esistono fisicamente su disco. Questo consente di mantenere nel repository solo il codice sorgente e la configurazione, escludendo automaticamente i dati generati, le dipendenze e i file sensibili.

[^14]: Un virtual environment, abbreviato venv in Python, e' una directory che contiene una copia isolata dell'interprete Python e di tutti i pacchetti installati per un progetto specifico. Questa isolazione impedisce che le dipendenze di progetti diversi interferiscano tra loro e che le installazioni globali sul sistema vengano modificate. Si crea con il comando python -m venv .venv e si usa richiamando direttamente il Python al suo interno: .venv\Scripts\python.exe su Windows, .venv/bin/python su Linux e macOS.

[^15]: Il registro di Windows, o Windows Registry, e' un database gerarchico che il sistema operativo usa per memorizzare configurazioni applicative e di sistema. Le variabili di ambiente per l'utente corrente sono memorizzate nella chiave HKCU\Environment (HKCU e' l'abbreviazione di HKEY_CURRENT_USER). Quando si esegue SetEnvironmentVariable con scope "User", il valore viene scritto in questa chiave e diventa disponibile in tutte le sessioni aperte dopo la scrittura, incluse le future sessioni di PowerShell, prompt dei comandi e Claude Code.

[^16]: SHA-256, acronimo di Secure Hash Algorithm 256, e' una funzione di hash crittografico che produce un digest di 256 bit a partire da un input di dimensione arbitraria. La caratteristica fondamentale e' la determinismo: lo stesso input produce sempre lo stesso hash, e una modifica minima all'input produce un hash completamente diverso. Questo la rende adatta al rilevamento delle modifiche ai file: confrontare l'hash attuale di un file con quello calcolato alla precedente esecuzione e' sufficiente per stabilire se il file e' cambiato.

[^17]: Il recall, nel contesto dell'information retrieval, misura la proporzione degli elementi rilevanti effettivamente recuperati rispetto al totale degli elementi rilevanti esistenti. In questo sistema viene usato in modo adattato: dati i token che descrivono un nodo del grafo e le keyword associate a una Capability della tassonomia, il recall misura quanti token del nodo sono presenti tra le keyword della Capability. Un recall pari a 0.20 significa che il 20% dei token descrittivi del nodo ha corrispondenza nelle keyword della Capability.

[^18]: ProcessPoolExecutor e' una classe del modulo concurrent.futures della libreria standard di Python che consente di eseguire funzioni in parallelo su processi separati, aggirando il GIL (Global Interpreter Lock) che limita il parallelismo dei thread in CPython. Il numero di worker puo' essere configurato; il sistema sceglie automaticamente il numero di CPU disponibili se non specificato. E' particolarmente efficace per carichi di lavoro CPU-bound come il parsing di file binari.

[^19]: L'indice di Jaccard misura la similarita' tra due insiemi calcolando il rapporto tra la loro intersezione e la loro unione. Se due documenti condividono 4 entita' su un totale di 16 distinte tra i due, il loro indice di Jaccard e' 4/16 = 0.25. Il valore oscilla tra 0 (nessuna sovrapposizione) e 1 (insiemi identici). Nel contesto del grafo di conoscenza, viene usato per stimare la somiglianza semantica tra documenti sulla base delle entita' che citano.

[^20]: YAML, acronimo di YAML Ain't Markup Language, e' un formato di serializzazione dei dati progettato per essere leggibile dall'essere umano. In MkDocs e in Obsidian, il frontmatter YAML e' un blocco delimitato da tre trattini in cima al file Markdown che contiene metadati strutturati come titolo, data, tag, e valori arbitrari. Obsidian li espone come Properties nell'interfaccia di modifica; MkDocs li usa per la configurazione della pagina nel sito generato.

[^21]: Un asset statico e', in senso tecnico, un file che il server web serve esattamente com'e' su disco, senza elaborazione server-side. In MkDocs, qualsiasi file nella cartella docs/ che non sia un file .md viene copiato nella directory di output _site/ durante la build, mantenendo il percorso relativo. Un file docs/graphify-out/graph.html diventa quindi accessibile all'URL /graphify-out/graph.html del sito pubblicato, senza che MkDocs lo elabori o lo trasformi.

[^22]: CIDR, Classless Inter-Domain Routing - notazione che esprime una sottorete come indirizzo seguito dal numero di bit di prefisso, ad esempio 192.168.1.0/24.

[^23]: NER, Named Entity Recognition - riconoscimento automatico di entità nominate in un testo, qui usato per individuare i nomi di persona da mascherare.

[^24]: PSK, Pre-Shared Key - chiave condivisa in anticipo fra due estremi di un tunnel VPN, che compare in chiaro nei file di configurazione dei firewall.

