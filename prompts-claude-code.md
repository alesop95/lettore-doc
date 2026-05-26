# Prompt template - operazioni ricorrenti con Claude Code

Usare questi prompt copia-incollando direttamente nel terminale Claude Code.
Ogni prompt è ottimizzato per minimizzare i token consumati e massimizzare
la precisione dell'output.

---

## 1. Sintesi narrative batch (vault Obsidian privato)

**Contesto**: dopo aver lanciato `run_pipeline.ps1`, genera le sintesi narrative
dei documenti. Usare in `E:\lettore-doc` con il subagente lettore-documentazione.

```
Usa il subagente lettore-documentazione.

Genera le sintesi narrative di tutti i documenti in _intermediate/structure.json
che NON hanno già un file corrispondente in _intermediate/summaries/.

Per ogni documento:
1. Leggi sections/<safe-stem>.json
2. Scrivi una sintesi in INGLESE di 150-200 parole che cattura: scopo del
   documento, tecnologie o strumenti coinvolti, output o deliverable,
   contesto operativo (senza citare nomi di clienti o aziende)
3. Salva in _intermediate/summaries/<safe-stem>.md

Procedi a lotti di 5 documenti per volta. Dopo ogni lotto, elenca i file
elaborati e quanti ne restano. Se il budget token si avvicina al limite,
fermati e dimmi da dove riprendere.
```

**Per riprendere una sessione interrotta:**

```
Continua la generazione delle sintesi narrative.
Verifica quali file .md esistono già in _intermediate/summaries/ e procedi
solo con i documenti mancanti. Stessa logica della sessione precedente:
lotti di 5, inglese, 150-200 parole, nessun nome di cliente.
```

---

## 2. Ispezione rapida di un corpus prima di graphify

**Contesto**: valuta quanto è grande una cartella sorgente prima di lanciarci
graphify, per stimare il consumo token.

```
Conta i file .docx, .txt e .md nella cartella
"<percorso-sorgente>"
suddivisi per estensione e per sottocartella di primo livello.
Non leggere il contenuto dei file, solo l'elenco.
Poi stima il token budget necessario per graphify basandoti su:
- .docx: ~4.000 token/file
- .txt/.md: ~1.500 token/file
- .png: ~2.500 token/file (vision)
Dimmi se è ragionevole lanciare graphify in un singolo run o se
conviene suddividere per sottocartella.
```

---

## 3. Revisione assistita del taxonomy_diff.md

**Contesto**: dopo `map_to_taxonomy.py`, ti aiuta a revisionare il diff.
Usare in `E:\lettore-doc`.

```
Leggi _intermediate/taxonomy_diff.md e _intermediate/taxonomy_index.json.

Per la sezione "Fit":
- Identifica i nodi con score < 0.2 che potrebbero essere falsi positivi
- Per ciascuno, leggi il text_preview in _intermediate/enriched_graph.json
  e dimmi se la Capability assegnata è plausibile
- Proponi quali righe eliminare dal diff

Per la sezione "New Capabilities":
- Raggruppa le proposte per Domain
- Per quelle con ≥3 nodi suggeriti, proponi un nome Capability in inglese
  coerente con lo stile del resto della tassonomia (vedi taxonomy_index.json
  per i nomi esistenti)
- Per quelle con 1-2 nodi, dimmi se è meglio accorparle a una Capability
  esistente o ignorarle

Non modificare nessun file: solo analisi e proposte.
```

---

## 4. Aggiornamento manuale di una Capability page

**Contesto**: arricchisci manualmente Overview, Technologies & tools o
Responsibilities di una Capability specifica. Usare in `J:\...\skills-repo`.

```
Leggi il file docs/<domain>/<capability>.md.

Aggiorna le sezioni come segue:
- "## Overview": [descrizione delle modifiche o del testo da inserire]
- "## Technologies & tools": aggiungi [tecnologia] con la notazione:
  - **<Nome>** (<versione>) - <breve qualificazione>
- "## Responsibilities & operational scope": aggiungi il punto:
  - <nuova responsabilità>

NON toccare "## Projects & evidence" né i commenti HTML
<!-- graphify-evidence-id: ... --> al suo interno.

Mostrami la diff prima di scrivere. Scrivi solo dopo mia conferma.
```

---

## 5. Aggiunta di un progetto manuale a una Capability

**Contesto**: aggiungi un progetto scritto da te (non estratto da graphify)
a una Capability page. Usare in `J:\...\skills-repo`.

```
In docs/<domain>/<capability>.md, aggiungi sotto "## Projects & evidence"
il seguente progetto:

### <Titolo del progetto>
<!-- graphify-evidence-id: manual-<YYYYMMDD>-<slug> -->

<Testo del progetto: 2-3 paragrafi con scopo, architettura/approccio,
outcome. Nessun nome di cliente. Aziende riferite come "un cliente del
settore X">.

*Technology stack: <lista tecnologie>.*

Mostrami il blocco risultante prima di scriverlo.
```

---

## 6. Query esplorativa sul vault Obsidian privato

**Contesto**: esplora relazioni non ovvie nella documentazione.
Usare in `E:\lettore-doc` con il subagente lettore-documentazione.

```
Usa il subagente lettore-documentazione.

Leggi _intermediate/graph.json e _intermediate/entities.json.

Domanda: [una delle seguenti, o personalizzata]

- Quali sono i 10 documenti con più relazioni? Perché sono diventati hub?
  Cosa hanno in comune?

- Trova documenti che parlano dello stesso argomento tecnico ma provengono
  da cartelle sorgente diverse. Potrebbero essere versioni dello stesso
  documento o duplicati da consolidare?

- Quali acronimi compaiono in più di 5 documenti distinti? Ci sono acronimi
  ambigui (stessa sigla, significati diversi in contesti diversi)?

- Per il cluster [nome entità o progetto], elenca i documenti in ordine
  cronologico e descrivi l'evoluzione del tema nel tempo.

Usa solo i JSON intermedi, non leggere i .docx originali.
```

---

## 7. Generazione MOC tematica nel vault privato

**Contesto**: crea una Map of Content manuale per un cluster specifico.
Usare in `E:\lettore-doc` con il subagente lettore-documentazione.

```
Usa il subagente lettore-documentazione.

Crea un file vault-output/<nome-moc>.md che funzioni come MOC (Map of Content)
per il cluster "[tema o entità]".

Il file deve:
1. Avere frontmatter YAML con tags: [moc, <tema>]
2. Aprire con un paragrafo che descrive il cluster
3. Elencare i documenti correlati in ordine di rilevanza (usa graph.json per
   i pesi), con wiki-link [[Nome Documento]] e una riga di descrizione per
   ciascuno
4. Avere una sezione "Timeline" se i documenti hanno date rilevabili
5. Chiudere con "Connessioni esterne" (documenti di altri cluster che
   hanno archi verso questo)

Usa _intermediate/graph.json per i dati di relazione.
Non leggere i .docx originali: usa solo le sezioni-preview in _intermediate/sections/.
```

---

## 8. Debug della pipeline

**Contesto**: diagnostica un errore nella pipeline.
Usare in `E:\lettore-doc`.

```
La pipeline ha prodotto questo errore:
[incolla il testo dell'errore]

Controlla:
1. Che il file di input esista nel path atteso
2. Che il formato JSON sia valido (se l'errore è di parsing)
3. Che il venv abbia le dipendenze installate:
   .\.venv\Scripts\python.exe -c "import docx, yaml; print('OK')"
4. Che il .docx in questione non sia un file temporaneo (~$...) o un
   documento scansionato senza testo (text_length: 0 in structure.json)

Proponi il fix minimale senza toccare la logica degli script.
```

---

## 9. Stima costo token prima di un run graphify

**Contesto**: valuta il budget prima di lanciare graphify su una cartella
grande. Usare prima di avviare Claude Code sulla cartella sorgente.

```
Conta i file nella cartella "<percorso-sorgente>" con:
Get-ChildItem -Recurse "<percorso-sorgente>" |
  Where-Object { $_.Extension -in '.docx','.txt','.md','.png','.jpg' } |
  Group-Object Extension |
  Select-Object Name, Count

Poi calcola la stima token con:
  .docx: Count × 4000
  .txt/.md: Count × 1500
  .png/.jpg: Count × 2500
  
Somma, dividi per 1000 per avere kToken di input.
Il modello Sonnet 4.5 costa ~$3/MTok input.
Dimmi se conviene suddividere per sottocartella.
```

---

## 10. Verifica integrità di skills-repo prima del push

**Contesto**: verifica che il sito non abbia link rotti prima di pushare.
Usare in `J:\...\skills-repo`.

```
Verifica che tutti i file elencati nel nav: di mkdocs.yml esistano
effettivamente in docs/.

Per ogni entry del nav, controlla:
1. Che il file .md esista
2. Che contenga i quattro H2: "Overview", "Technologies & tools",
   "Responsibilities & operational scope", "Projects & evidence"
3. Che non contenga placeholder come "To be populated" o "Capability stub"
   nella sezione Overview (queste andrebbero riempite prima di pubblicare)

Elenca i file con problemi e proponi le correzioni minime.
Non modificare nulla: solo report.
```
