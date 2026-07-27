---
generated-from-commit: 979d674
generated-from-branch: main
generated-date: 2026-06-17
covers-paths:
  - scripts/**
  - run_pipeline.ps1
  - run_pipeline.sh
  - setup.ps1
  - setup.sh
last-verified-commit: 397c0a8
source-doc: GUIDA-TECNICA.md
---

# Dev e testing

La pipeline e deterministica: rilanciare gli script da lo stesso output. Controlli chiave: `--dry-run` obbligatorio prima di `export_to_taxonomy.py --apply`; revisione manuale di `taxonomy_diff.md`; `sanitize_taxonomy_diff.py` come gate obbligatorio fra `map_to_taxonomy` e `export_to_taxonomy` (produce il `.sanitized.json` che poi va in dry-run/apply); `mkdocs build --strict` come safety net sui link del sito pubblico. La modalita `--incremental` confronta hash SHA256 e processa solo i file cambiati. Il tuning avviene su soglie e pesi (`THRESHOLD_FIT`, `W_JACCARD`, ecc.) documentati in `GUIDA-TECNICA.md` sezione 8. Ambiente ricreabile con `setup.ps1/.sh`; per l'estrazione NER serve `it_core_news_lg` scaricato via `python -m spacy download it_core_news_lg` (senza il modello si attiva un fallback regex+stoplist sub-ottimale). Sanity check post-`--apply` sullo skills-repo: `git diff -w --numstat` deve mostrare solo aggiunte (con eventuali `-2` legittimi dovuti alla rimozione del placeholder "None yet" dalle sezioni "Projects & evidence" preesistenti).

A monte della pipeline il controllo e' `prepare_graphify_source.py` in modalita' di sola verifica, che va eseguito su ogni subfolder prima di lanciare graphify. Il default e' non scrivere nulla: riporta quanti documenti passano il filtro, quanti verrebbero scartati per il nome, e per ciascuno il nome neutralizzato che verrebbe prodotto. Con `--apply` scrive la cartella e chiude con una verifica di ritorno che rilegge l'output e rilancia il filtro sui nomi appena scritti, uscendo con codice 2 se un file attiva ancora il match: la mappa di sostituzione non puo' quindi fallire in silenzio. Una singola conversione fallita non interrompe il ciclo, viene raccolta e riportata in coda. La validazione dello script e' stata fatta contro la cartella prodotta a mano nel ciclo Cybersec del 2026-07-16: i cinque nomi generati coincidono esattamente con quelli scelti manualmente allora.

Un secondo controllo riguarda `generate_taxonomy_index.py`, che avvisa su standard error quando una Capability supera `MAX_KEYWORDS` e viene troncata, elencando quali e di quanti token. Il troncamento silenzioso e' stato la causa reale di un misrouting, quindi il messaggio va letto: una Capability troncata perde vocabolario discriminante e viene battuta nel matching da pagine piu' povere che quel vocabolario conservano.

Il diario tecnico ha un controllo analogo, dove il rischio non e' la fuga di dati ma il disallineamento silenzioso fra il `.docx` sorgente e il `.md` derivato. `scripts/finalize_diary.ps1` e' il gate: fallisce presto se mancano il Python del venv, il convertitore o il `.docx`, propaga l'exit code di `sync_diary_md.py` invece di proseguire su una rigenerazione fallita, e mostra il diff del `.md` come unica review leggibile di un cambiamento nato in un binario. Lo stesso comando serve da verifica di allineamento a freddo, per esempio dopo un `git pull` su un'altra macchina: si rigenera e si guarda `git status`, e se il `.md` risulta modificato allora era il file su disco a essere disallineato. Il flag `-NoDiff` salta la sola review, non i controlli.
