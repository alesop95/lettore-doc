---
name: grafo-conoscenza
description: Euristica per identificare relazioni tra documenti e costruire un grafo di conoscenza in stile Obsidian. Da usare ogni volta che si vogliono creare wiki-link, MOC (Maps of Content), o strutture di knowledge management cross-documento. Spiega come pesare le relazioni, come decidere quali link mostrare, e come generare il file index.md (mappa generale).
---

# Costruzione del grafo di conoscenza

## Modello dati

Ogni nodo del grafo è un documento. Ogni arco è una **relazione pesata** tra due documenti, calcolata sommando contributi da diverse fonti:

```
peso(A, B) = w1 * jaccard(entità_A, entità_B)
           + w2 * conta_riferimenti_espliciti(A → B)
           + w3 * vicinanza_cartella(A, B)
           + w4 * vicinanza_temporale(A, B)
           + w5 * similarità_titolo(A, B)
```

Pesi di default (modificabili in `build_knowledge_graph.py`):
- `w1 = 0.40` — sovrapposizione entità (segnale più forte)
- `w2 = 0.30` — riferimenti espliciti ("vedi X.docx")
- `w3 = 0.10` — stessa cartella o sottocartella
- `w4 = 0.10` — date documento contigue
- `w5 = 0.10` — titoli con radice comune (es. "Verbale 2024-Q1", "Verbale 2024-Q2")

## Tipologie di relazione

Lo script etichetta ogni arco con un'**etichetta semantica**, in ordine di priorità:

| Etichetta | Quando si applica | Esempio |
|---|---|---|
| `riferisce_esplicitamente` | A contiene nome o codice di B | "Come da specifica TECH-2024-08.docx" |
| `serie_temporale` | Stesso template, date sequenziali | Verbali mensili |
| `stesso_progetto` | Codice progetto in comune in titolo o frontmatter | PRJ-001 in A e B |
| `condivide_entita_chiave` | ≥5 entità in comune | Stesso cliente, stesso fornitore |
| `topica_affine` | Jaccard entità >0.15 ma <0.30 | Procedure dello stesso ambito |
| `correlato_debole` | Tutto il resto sopra soglia minima | Connessione lasca |

## Soglie e filtri

**Non tutti gli archi vanno mostrati** nel vault, altrimenti il grafo diventa illeggibile.

- Soglia minima per visualizzare un arco: `peso ≥ 0.15`
- Massimo 8 link "Documenti correlati" per pagina (i top per peso)
- Se un nodo ha >20 archi, è un "hub": vale la pena creare un MOC dedicato (Map of Content) raggruppato per tipologia di relazione.

## Generazione dei wiki-link inline

Oltre alla sezione "Documenti correlati", lo script inserisce wiki-link **nel corpo della sintesi** quando incontra nomi di entità che corrispondono a un altro documento:

- Se il documento `Cliente-AlphaBeta.docx` esiste nel vault e la sintesi di un altro documento menziona "AlphaBeta", la menzione diventa `[[Cliente-AlphaBeta]]`.
- Per evitare rumore: solo prima occorrenza per documento, e solo se il match è esatto (case-insensitive ma intero, non substring).

## Generazione dell'index.md

L'`index.md` è la mappa generale del vault. Struttura:

```markdown
# Mappa della Conoscenza — Documenti IT Intrawelt

> Aggiornato: {data}
> Documenti totali: {N}
> Relazioni mappate: {M}

## Per tipologia

### Procedure ({n_procedure})
- [[Documento 1]] — {sintesi breve, 1 riga}
- [[Documento 2]] — {sintesi breve}

### Contratti ({n_contratti})
...

## Hub (documenti più connessi)
1. [[Doc-X]] — 23 relazioni — {motivazione}
2. [[Doc-Y]] — 18 relazioni — {motivazione}

## Cluster tematici
### Cluster: Cliente AlphaBeta ({n_doc})
- [[...]]

### Cluster: Procedure HR ({n_doc})
- [[...]]

## Documenti isolati (nessuna relazione forte)
- [[...]] — potrebbero essere candidati per archiviazione o classificazione manuale
```

I cluster tematici sono calcolati con clustering gerarchico sulle entità (HCLUST sul vettore di entità di ogni documento). Lo script usa scipy se disponibile, altrimenti fallback su raggruppamento per entità più frequente.

## Compatibilità Obsidian

I file generati funzionano nativamente in Obsidian:

- Wiki-link `[[Nome File]]` (senza estensione)
- Frontmatter YAML letto da Obsidian Properties
- Tag inline `#procedura` e `#cliente/alphabeta` (gerarchici)
- Grafo visualizzabile da Obsidian → "Graph view"
- Per visualizzazioni più ricche: plugin "Dataview" (gli archi sono già in YAML), "Breadcrumbs" (per gerarchia), "Excalidraw" (per mappe manuali)

## Aggiornamenti incrementali

Quando l'utente aggiunge nuovi .docx alla cartella sorgente, non rifare tutto da zero:

```bash
python scripts/build_knowledge_graph.py --incremental --since "2026-05-01"
```

Lo script:
1. Identifica i .docx nuovi o modificati (mtime > since)
2. Riparsa solo quelli
3. Ricalcola gli archi solo per i nodi nuovi/modificati e i loro vicini
4. Aggiorna i .md interessati senza toccare gli altri
5. Rigenera l'index.md completo

## Validazione manuale

Dopo la prima generazione, Claude (l'agente) deve fare uno spot check:

1. Apri 2-3 .md a caso del vault generato
2. Verifica che la sintesi sia sensata
3. Verifica che i "Documenti correlati" abbiano senso (chiedi all'utente conferma per 3-5 archi)
4. Se l'utente segnala falsi positivi → alza la soglia minima a 0.20 e rigenera
5. Se segnala falsi negativi (relazioni mancanti) → abbassa a 0.10 e rigenera
