# Runbook: bonifica del repository pubblico (2026-08-03)

Documento operativo per l'incidente di divulgazione trovato il 2026-08-03
dall'audit del repository pubblico `alesop95/skills`. Vive in `lettore-doc`, che
non viene mai pubblicato. **Non contiene i valori delle credenziali**: sono
riferiti per pagina, non per valore, perche' un runbook che li trascrive
riproduce il problema che descrive.

---

## 1. Cosa e' stato trovato

L'audit ha analizzato l'albero di lavoro e tutti i ventidue commit della storia.
Le categorie con riscontri reali erano quattro.

Quattro credenziali in chiaro dentro il testo di anteprima delle evidenze, su
`infrastructure-virtualization.md` (una password di root su SSH),
`backup-disaster-recovery.md` (una casella di posta),
`llms-generative-ai.md` (il file di backup credenziali del NAS) e
`cybersecurity-it-governance.md` (un account applicativo). Sulla stessa pagina
c'erano anche i codici di backup di un secondo fattore.

Un hostname contenente un nome di persona, su due pagine. Tre nomi propri di
colleghi in tre pagine. Il nome di un cliente terzo. Tre sottodomini di un
provider di hosting, da cui si ricostruisce l'infrastruttura.

Due preview appiattiti diventati vere intestazioni di secondo livello, che oltre
al danno di lettura avevano rotto i confini dei blocchi e reso quel contenuto non
piu' modificabile dalla pipeline.

---

## 2. Prima di tutto: rotazione, non rimozione

**La rimozione da Git non annulla la divulgazione.** Un repository pubblico puo'
essere gia' stato clonato, GitHub conserva gli oggetti non piu' raggiungibili per
un tempo non garantito e accessibili per SHA via API, i fork non vengono
riscritti da una riscrittura della storia, e le pagine possono essere in cache su
motori di ricerca e su Internet Archive.

Le quattro credenziali vanno cambiate, in questo ordine di urgenza: la password
di root su SSH per prima, perche' e' accesso amministrativo a una macchina; poi
l'account applicativo, la casella di posta, e la password del file di backup
credenziali del NAS, che protegge a sua volta altre credenziali. I codici di
backup del secondo fattore vanno rigenerati.

Dove esistono log di accesso, conviene guardarli per il periodo di esposizione,
che parte dal commit in cui l'evidenza e' stata pubblicata.

---

## 3. Bonifica dei contenuti, gia' eseguita

L'albero di lavoro e' stato bonificato interamente tramite la pipeline, senza
alcun intervento a mano sulle sezioni delle evidenze, che per regola sono di
competenza esclusiva di `export_to_taxonomy.py`. I cinque cicli pubblicati sono
stati rigenerati con le regole nuove e riscritti in blocco, con rimozione dei
collocamenti non piu' previsti e riparazione delle due pagine corrotte.

Lo stato si verifica in qualsiasi momento con il verificatore, che deve uscire
pulito prima di ogni commit sul repository pubblico.

```
.\.venv\Scripts\python.exe scripts\verify_public_repo.py
.\.venv\Scripts\python.exe scripts\verify_public_repo.py --history
```

Il contenuto scritto a mano e' stato preservato: le due voci di progetto redatte
a mano e la sezione `## Capability gaps acknowledged` sono intatte.

---

## 4. Riscrittura della storia

Il sito si pubblica con `actions/upload-pages-artifact`, quindi non esiste un
branch `gh-pages` con una storia parallela: c'e' solo `main`. Questo semplifica
la riscrittura.

### Opzione consigliata: storia nuova in un solo commit

E' la sola che garantisce che nessun blob vecchio resti sul branch. Il costo e'
perdere la narrazione dei ventidue commit, che pero' e' conservata nel diario
tecnico di `lettore-doc`, dove sta la storia vera del progetto.

Da eseguire nella cartella del repository pubblico, dopo aver verificato che il
verificatore esca pulito e che `git status` mostri le sole modifiche attese.

```powershell
git checkout --orphan storia-pulita
git add -A
git commit -m "Tassonomia delle competenze: contenuto bonificato"
git branch -D main
git branch -m main
git push --force origin main
```

```bash
git checkout --orphan storia-pulita
git add -A
git commit -m "Tassonomia delle competenze: contenuto bonificato"
git branch -D main
git branch -m main
git push --force origin main
```

### Alternativa: conservare i commit redigendo le stringhe

Richiede `git filter-repo` installato e un file di sostituzioni che elenca ogni
stringa da redigere. Conserva la storia ma garantisce solo cio' che si e'
ricordato di elencare, quindi va usata solo se la storia serve davvero.

```bash
pipx install git-filter-repo
git filter-repo --replace-text sostituzioni.txt
git push --force origin main
```

Il file `sostituzioni.txt` va scritto fuori dal repository e cancellato dopo
l'uso, perche' contiene in chiaro esattamente cio' che si sta rimuovendo.

---

## 5. Cosa resta da fare lato GitHub, dopo il push forzato

Il push forzato sposta il riferimento del branch ma non cancella nulla dai
server. I passi seguenti sono manuali sull'interfaccia web.

Eliminare gli artifact e i log delle esecuzioni passate del workflow, sotto
Actions: gli artifact di Pages contengono il sito costruito, quindi anche le
pagine con le credenziali, e i log possono contenere estratti.

Verificare l'esistenza di fork del repository. Un fork e' un repository distinto
e la riscrittura non lo tocca: se ne esistono, va chiesta la rimozione a chi li
possiede, oppure si valuta che la sola rotazione delle credenziali sia la
mitigazione effettiva.

Chiedere al supporto GitHub la rimozione delle viste in cache e degli oggetti non
piu' raggiungibili, indicando gli SHA dei commit rimossi. E' l'unico modo di
renderli non piu' recuperabili per SHA.

Forzare una nuova pubblicazione delle Pages, cosi' che il sito servito
corrisponda al contenuto bonificato.

Chiedere la rimozione dalla cache dei motori di ricerca per le pagine coinvolte,
e verificare Internet Archive per le stesse.

---

## 6. Perche' non e' stato intercettato prima, e cosa e' cambiato

Il gate di riservatezza copriva indirizzi di rete, indirizzi di posta, hostname,
dominio aziendale, fornitori e sedi, e non aveva **nessuna regola sui segreti**.
Il filtro di graphify che scarta i file dal nome sospetto guarda soltanto il nome
e mai il contenuto, ed e' per di piu' aggirato di proposito da
`prepare_graphify_source.py`, che serve a recuperare le policy IT scartate a
torto: il filtro sui nomi non e' un filtro sui contenuti, e nessuno dei due
guardava dentro.

Gli strati aggiunti il 2026-08-03 sono quattro. Una categoria di pattern per i
segreti che **scarta** l'evidenza invece di mascherarla, perche' una credenziale
in chiaro dice che quel punto del documento e' un deposito di credenziali e
mascherare il valore lascerebbe pubblicato a quale sistema appartiene. La
dichiarazione da parte del gate dei nodi che ha scartato, senza la quale una
regola nuova poteva impedire una pubblicazione futura ma non annullarne una
vecchia, perche' cio' che il gate scarta sparisce dal diff e diventa invisibile
alla rimozione. La neutralizzazione dei marcatori Markdown nel preview, che
impedisce a un testo di diventare struttura della pagina. E soprattutto
`verify_public_repo.py`, che rende il controllo eseguibile e ripetibile invece di
affidarlo al ricordarsi di farlo: la sola fuga trovata prima di questo audit era
stata vista a mano, e le quattro password sono rimaste mesi perche' quel controllo
manuale non sapeva cosa cercare.

Il verificatore importa i pattern dal gate invece di duplicarli, cosi' i due non
possono divergere: un verificatore con una propria copia delle regole al primo
aggiornamento dichiara pulito qualcosa che il gate impedisce, o viceversa.

---

## 7. Regola operativa che ne consegue

Nessun commit sul repository pubblico senza che
`scripts\verify_public_repo.py` sia uscito pulito. La forma `--staged` e' adatta
a un hook di pre-commit nel repository pubblico, ed e' il modo di rendere il
cancello non aggirabile per distrazione.
