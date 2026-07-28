---
generated-from-commit: 979d674
generated-from-branch: main
generated-date: 2026-06-17
covers-paths:
  - scripts/**
last-verified-commit: 21e11b3
source-doc: GUIDA-TECNICA.md
---

# Roadmap

Estensioni candidate (da `GUIDA-TECNICA.md` sezione 9), da valutare caso per caso solo se il valore giustifica la dipendenza:

- Automazione multi-sorgente completa: oggi il passaggio graphify resta semi-interattivo; serve un flag headless o una API key dedicata.
- Embeddings semantici al posto del recall su keyword in `map_to_taxonomy.py`: cambia solo la funzione di scoring, il resto della pipeline resta invariato. Il ciclo Cybersec ha dato un argomento concreto a favore: con `recall_score` il match si decide su singoli token presenti o assenti dal testo di una pagina, quindi `breach` scritto in una Overview e non nell'altra sposta diciotto evidenze, e mantenere il routing corretto significa curare il vocabolario delle pagine invece della semantica.
- Token della community iniettati nei token del nodo in `classify_nodes`: oggi ogni nodo eredita i token del nome della propria community, quindi su un label da tre o quattro token la maggioranza del segnale non viene dal nodo. L'effetto e' che una community si sposta in blocco e un errore di routing non riguarda mai una evidenza sola. Da decidere se pesare i due contributi in modo diverso o rimuovere l'ereditarieta'; serve prima un ciclo in cui il fenomeno produca un errore osservabile e isolabile.
- Lingua del corpus contro lingua della tassonomia: il ciclo Cybersec endpoint ha lasciato `PSGSI Politica Sicurezza Informazioni` non classificata con punteggio *esattamente zero*, perche' il label e' italiano e le keyword delle Capability sono inglesi, quindi non esiste un solo token in comune con `security`, `policy` o `compliance`. Nessun intervento sul vocabolario risolve questa classe di casi: e' il match lessicale in se'. E' l'argomento piu' forte a favore della voce sugli embeddings qui sopra, e nel frattempo si mitiga solo recuperando a mano in review i nodi a punteggio zero.
- Qualita' del preview delle evidenze: sono i primi duecento caratteri del file, quindi partono dall'H1 (che ripete il nome del documento) e spesso finiscono dentro frammenti di tabella Markdown. L'evidenza pubblicata informa poco. Da valutare un preview costruito sulla prima frase utile invece che sul primo taglio a lunghezza fissa, saltando intestazioni e righe di tabella.
- Capability senza keyword: `Soft Skills` produce zero keyword e non puo' quindi ricevere alcuna evidenza. Da verificare se la pagina abbia le due sezioni H2 da cui `generate_taxonomy_index.py` estrae, e se il caso vada gestito con un avviso esplicito come gia' fatto per il troncamento.
- Connettori MCP per sorgenti remote (Google Drive, Notion, Confluence) che producono lo stesso formato `graph.json`.
- Clustering gerarchico nel vault al posto dell'approccio naive a singolo seed.
