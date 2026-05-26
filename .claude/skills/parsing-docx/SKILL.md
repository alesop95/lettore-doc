---
name: parsing-docx
description: Strategie per estrarre contenuto da file .docx italiani lunghi minimizzando il consumo di token. Da usare quando devi processare uno o più .docx, soprattutto se grandi (>20 pagine), e vuoi mantenere il budget di contesto basso. Spiega come usare gli script Python del progetto e come decidere quali sezioni caricare effettivamente in contesto.
---

# Parsing .docx ottimizzato per token

## Principio guida

Un .docx di 50 pagine può facilmente contare 25.000-40.000 token. Caricarlo intero in contesto è quasi sempre uno spreco: l'80% del documento serve come riferimento ricercabile, non come materiale di ragionamento attivo.

**Regola d'oro**: lavora a **tre livelli di dettaglio**, salendo solo quando serve.

### Livello 1 — Scheletro (~50-200 token per documento)
Solo: titolo, gerarchia di heading, numero di sezioni, conteggio parole totale, prime righe del documento.

Generato da: `parse_docx.py --mode skeleton`

Usalo per: decidere cosa leggere, costruire la tassonomia, generare il primo index.md.

### Livello 2 — Sezioni con estratto (~500-2000 token per documento)
Per ogni sezione: titolo, parole, primi 200 caratteri, ultimi 100 caratteri, eventuali entità presenti.

Generato da: `parse_docx.py --mode sections-preview`

Usalo per: scrivere le sintesi, mappare le entità, trovare candidate per relazioni.

### Livello 3 — Sezione completa (~variabile)
Solo quando vuoi davvero approfondire una sezione specifica.

Generato da: `parse_docx.py --mode full-section --file X.docx --section "Capitolo 3"`

Usalo per: rispondere a domande puntuali dell'utente, citare passaggi precisi, debug di entità ambigue.

## Workflow consigliato

```
1. Scheletro di tutta la cartella → un solo file structure.json (~5-10 KB anche per 100 docx)
2. Leggi structure.json → decidi raggruppamento e priorità
3. Per ogni cluster prioritario: genera sezioni-preview
4. Per le sezioni con anomalie/incertezze: zoom su livello 3
```

## Convenzioni di parsing dei .docx italiani

I .docx aziendali italiani tendono ad avere queste caratteristiche; sfruttale:

- **Heading Style**: Spesso usano `Titolo 1`, `Titolo 2` invece di `Heading 1`. Lo script normalizza automaticamente, ma se vedi sezioni piatte controlla i nomi degli stili.
- **Numerazione gerarchica**: "1.", "1.1", "1.1.1" è frequente. Anche se gli heading style mancano, lo script ricostruisce la gerarchia dai pattern numerici.
- **Tabelle**: Spesso contengono dati chiave (tariffari, anagrafiche, scadenze). Lo script le estrae come array di dizionari in `structure.json` → campo `tables`.
- **Header/Footer**: Spesso contengono codice documento, revisione, data emissione → metadata preziosi.
- **Acronimi tutto-maiuscolo**: Comuni (es. RTI, DURC, SAL, DGUE). Lo script li raccoglie automaticamente come entità candidate.
- **Riferimenti normativi**: "D.Lgs 50/2016", "art. 80", "Reg. UE 679/2016" → pattern regex specifici nello script entities.

## Quando intervenire manualmente

Il parsing automatico fallisce in questi casi:

1. **.docx con solo immagini scansionate** → lo script lo segnala come `text_length: 0`. Suggerisci all'utente OCR (tesseract o servizio cloud) prima di reindicizzare.
2. **Documento senza heading** (solo prosa continua) → lo script crea un'unica sezione "Documento completo". Avvisa l'utente che la sintesi sarà meno granulare.
3. **Documenti molto simili** (es. 12 verbali mensili) → potrebbe non valere la pena trattarli singolarmente. Proponi un raggruppamento per serie con un solo .md "indice di serie".

## Comandi rapidi

```bash
# Inventario veloce di una cartella
python scripts/parse_docx.py --input "<cartella>" --mode skeleton --output ./_intermediate/structure.json

# Preview con estratti per tutti
python scripts/parse_docx.py --input "<cartella>" --mode sections-preview --output-dir ./_intermediate/sections/

# Zoom su una sezione specifica
python scripts/parse_docx.py --file "<cartella>/documento.docx" --mode full-section --section "3.2 Procedura operativa"

# Solo conteggio token stimato (per pianificazione)
python scripts/parse_docx.py --input "<cartella>" --mode token-estimate
```

Lo script gestisce automaticamente percorsi Windows con spazi e accenti (compresi i path OneDrive). Su Windows usa i doppi apici nel percorso.
