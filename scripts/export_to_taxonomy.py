#!/usr/bin/env python3
"""
export_to_taxonomy.py - Applica taxonomy_diff.json alle Capability pages di skills-repo.

Modalità --dry-run (default): mostra cosa verrebbe modificato senza toccare nulla.
Modalità --apply:             scrive effettivamente i file in skills-repo.

Per ogni entry "fit" nel diff:
  - Aggiunge un H3 sotto ## Projects & evidence della Capability page corrispondente
  - Usa un commento HTML invisibile come ID stabile per garantire idempotenza
  - Non duplica entrate già presenti

Per ogni entry "new_capability" nel diff:
  - Crea il file .md della nuova Capability con lo schema a 4 H2 standard
  - Stampa la riga da aggiungere manualmente a mkdocs.yml (non la aggiunge in automatico)

Su ogni esecuzione, anche in dry-run e senza flag aggiuntivi:
  - Cerca i collocamenti obsoleti, cioe' i blocchi di evidenza appartenenti a
    nodi del corpus corrente che stanno su una pagina dove il diff non li
    colloca piu', e li elenca. Con --prune-moved li rimuove; con
    --prune-unexpected rimuove anche quelli dei nodi scesi sotto soglia.

Uso:
  # Revisiona prima senza modifiche
  python scripts/export_to_taxonomy.py \\
    --diff-json  _intermediate/taxonomy_diff.json \\
    --skills-repo "J:\\...\\skills-repo" \\
    --dry-run

  # Applica dopo revisione
  python scripts/export_to_taxonomy.py \\
    --diff-json  _intermediate/taxonomy_diff.json \\
    --skills-repo "J:\\...\\skills-repo" \\
    --apply
"""

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

EVIDENCE_ANCHOR = "<!-- graphify-evidence-id: {stable_id} -->"
EVIDENCE_ANCHOR_RE = re.compile(r"<!-- graphify-evidence-id: ([a-f0-9]+) -->")
PLACEHOLDER_TEXT = (
    "*Project entries are populated automatically from anonymized project\n"
    "documentation. None yet.*"
)
PROJECTS_SECTION_HEADER = "## Projects & evidence"


# ---------------------------------------------------------------------------
# Generazione ID stabile per idempotenza
# ---------------------------------------------------------------------------

def stable_id(node_id: str, cap_slug: str) -> str:
    """SHA256 breve di node_id + cap_slug → 12 char hex."""
    raw = f"{node_id}::{cap_slug}".encode()
    return hashlib.sha256(raw).hexdigest()[:12]


def node_key(node: dict) -> str:
    """
    Identificativo del nodo usato come primo termine dell'ID stabile.

    Esiste come funzione perche' lo stesso criterio va applicato identico
    dall'iniezione e dalla ricerca dei collocamenti obsoleti: se le due
    divergessero, la seconda non riconoscerebbe i blocchi scritti dalla prima.
    """
    return node.get("id", node.get("label", ""))


# ---------------------------------------------------------------------------
# Anonimizzazione testi in uscita
# ---------------------------------------------------------------------------

def apply_anon(text: str, anon_map: dict | None) -> str:
    """
    Sostituisce le occorrenze di anon_map nel testo. Ordina per lunghezza
    decrescente cosi' i match piu' specifici (es. hostname completo)
    prevalgono sui prefissi corti.

    Vale per QUALUNQUE testo che finisce nel repo pubblico: label H3, name
    H1 di nuove Capability, community label, preview del body.
    """
    if not text or not anon_map:
        return text
    for original in sorted(anon_map, key=len, reverse=True):
        placeholder = anon_map[original]
        text = re.sub(re.escape(original), placeholder, text)
    return text


# ---------------------------------------------------------------------------
# Generazione blocco H3 da iniettare
# ---------------------------------------------------------------------------

def build_evidence_block(
    node: dict,
    cap_slug: str,
    community_label: str | None = None,
    anon_map: dict | None = None,
) -> str:
    """
    Produce il blocco Markdown da inserire sotto ## Projects & evidence.

    Il blocco inizia con ### {label}, contiene un commento HTML invisibile
    come ID di idempotenza, e il testo di evidenza anonimizzato.
    """
    sid      = stable_id(node_key(node), cap_slug)
    label    = apply_anon(node.get("label", "Untitled"), anon_map)
    src_file = node.get("source_file", "")
    preview  = apply_anon(node.get("text_preview", "").strip(), anon_map)

    # Anche il nome del file va anonimizzato: e' testo che finisce nel repo
    # pubblico esattamente come il label e il preview, e i nomi dei documenti
    # aziendali contengono regolarmente ragione sociale ("Protezione avanzata
    # (LAN) Intrawelt.docx") o hostname ("... eccezione su PC-ALESSIO.docx").
    src_basename = apply_anon(Path(src_file).name, anon_map) if src_file else "-"
    community_line = (
        f"- **Graph community**: {apply_anon(community_label, anon_map)}\n"
        if community_label
        else ""
    )

    if preview:
        body = preview[:300].replace("\n", " ").strip()
        if len(preview) > 300:
            body += "…"
        body_block = f"\n{body}\n"
    else:
        body_block = (
            "\n*Evidence text to be enriched from source document.*\n"
        )

    block = (
        f"### {label}\n"
        f"{EVIDENCE_ANCHOR.format(stable_id=sid)}\n"
        f"\n"
        f"- **Source**: `{src_basename}`\n"
        f"{community_line}"
        f"{body_block}"
        f"\n"
        f"*Technology stack: to be enriched from source document.*\n"
    )
    return block


# ---------------------------------------------------------------------------
# Lettura e scrittura sicura della sezione Projects & evidence
# ---------------------------------------------------------------------------

def already_injected(md_text: str, sid: str) -> bool:
    return sid in md_text


def block_span(md_text: str, sid: str) -> tuple[int, int] | None:
    """
    Delimita il blocco di evidenza identificato da `sid`, restituendo l'intervallo
    di caratteri che lo contiene, oppure None se l'ancora non c'e'.

    Il blocco si delimita risalendo dall'ancora all'`###` che la precede e
    scendendo fino alla prossima intestazione di pari o superiore livello. La
    stessa delimitazione serve sia alla riscrittura (`--refresh`) sia alla
    rimozione (`--prune-*`): sono due operazioni diverse sullo stesso perimetro.
    """
    anchor = EVIDENCE_ANCHOR.format(stable_id=sid)
    pos = md_text.find(anchor)
    if pos == -1:
        return None

    start = md_text.rfind("\n### ", 0, pos)
    if start == -1:
        return None
    start += 1  # si tiene il newline precedente come separatore

    after = pos + len(anchor)
    next_h3 = md_text.find("\n### ", after)
    next_h2 = md_text.find("\n## ", after)
    candidates = [p for p in (next_h3, next_h2) if p != -1]
    end = min(candidates) + 1 if candidates else len(md_text)

    return start, end


def replace_block(md_text: str, sid: str, new_block: str) -> str | None:
    """
    Sostituisce in blocco l'evidenza identificata da `sid`, restituendo None se
    non la trova.

    Serve alla modalita' `--refresh`. L'idempotenza per ID protegge dai
    duplicati ma rende anche impossibile correggere un'evidenza gia' pubblicata:
    quando un difetto della pipeline ha prodotto blocchi sbagliati, come i
    quarantaquattro preview identici del ciclo ARCHITETTURA, l'unico modo di
    ripararli era riscrivere a mano il repo pubblico, che le regole del progetto
    vietano.
    """
    span = block_span(md_text, sid)
    if span is None:
        return None
    start, end = span
    return md_text[:start] + new_block.rstrip() + "\n\n" + md_text[end:]


def remove_block(md_text: str, sid: str) -> str | None:
    """
    Cancella il blocco di evidenza identificato da `sid`, restituendo None se
    non lo trova.

    Se il blocco era l'ultimo contenuto del file la coda viene ripulita, cosi'
    da non lasciare righe vuote in fondo alla pagina.
    """
    span = block_span(md_text, sid)
    if span is None:
        return None
    start, end = span
    head, tail = md_text[:start], md_text[end:]
    if not tail.strip():
        return head.rstrip() + "\n"
    return head + tail


def restore_placeholder_if_empty(md_text: str) -> str:
    """
    Rimette il testo segnaposto sotto `## Projects & evidence` se la sezione e'
    rimasta senza alcun blocco `###`.

    Una pagina Capability con la sezione vuota resterebbe conforme al contratto
    delle quattro H2 ma perderebbe la riga che dichiara al lettore come quella
    sezione viene popolata: il segnaposto e' lo stato iniziale della pagina, ed
    e' lo stato corretto in cui riportarla quando la si svuota.
    """
    sec_start = md_text.find(PROJECTS_SECTION_HEADER)
    if sec_start == -1:
        return md_text

    body_start = sec_start + len(PROJECTS_SECTION_HEADER)
    next_h2    = md_text.find("\n## ", body_start)
    body_end   = next_h2 if next_h2 != -1 else len(md_text)
    body       = md_text[body_start:body_end]

    if "### " in body or PLACEHOLDER_TEXT in body:
        return md_text

    return (
        md_text[:body_start]
        + "\n\n"
        + PLACEHOLDER_TEXT
        + "\n"
        + md_text[body_end:]
    )


def inject_into_section(md_text: str, block: str) -> str:
    """
    Inserisce 'block' prima della fine della sezione ## Projects & evidence.
    Se la sezione non esiste, la aggiunge in fondo.

    Strategia: trova l'ultimo H2 (o EOF) dopo ## Projects & evidence
    e inserisce il blocco appena prima.
    """
    # Trova l'inizio della sezione
    sec_start = md_text.find(PROJECTS_SECTION_HEADER)
    if sec_start == -1:
        # La sezione non esiste: aggiungila in fondo
        return md_text.rstrip() + f"\n\n{PROJECTS_SECTION_HEADER}\n\n{block}\n"

    # Cerca il prossimo H2 dopo la sezione
    after_sec = md_text.find("\n## ", sec_start + len(PROJECTS_SECTION_HEADER))

    if after_sec == -1:
        # La sezione è l'ultima: inserisci prima della fine del file
        # Rimuovi il placeholder se presente
        content_after = md_text[sec_start + len(PROJECTS_SECTION_HEADER):]
        content_after_clean = content_after.replace(PLACEHOLDER_TEXT, "").rstrip()
        return (
            md_text[:sec_start + len(PROJECTS_SECTION_HEADER)]
            + content_after_clean
            + "\n\n"
            + block.rstrip()
            + "\n"
        )
    else:
        # Inserisci subito prima del prossimo H2
        before_next_h2 = md_text[:after_sec].rstrip()
        # Rimuovi il placeholder
        before_next_h2 = before_next_h2.replace(PLACEHOLDER_TEXT, "").rstrip()
        return (
            before_next_h2
            + "\n\n"
            + block.rstrip()
            + "\n"
            + md_text[after_sec:]
        )


# ---------------------------------------------------------------------------
# Collocamenti obsoleti: individuazione delle evidenze da rimuovere
# ---------------------------------------------------------------------------

def collect_placements(diff: dict) -> tuple[dict[str, set[str]], set[str]]:
    """
    Estrae dal diff due insiemi: dove ciascun nodo e' atteso, e quali nodi il
    diff conosce.

    Il primo, `expected`, mappa la chiave di nodo sull'insieme degli slug di
    Capability su cui il diff lo colloca. Il secondo, `known`, contiene ogni
    nodo che il diff nomina a qualsiasi titolo, quindi anche i non classificati
    e quelli raccolti nelle proposte di nuova Capability o nuovo Dominio.

    La distinzione e' quella che rende sicura la rimozione. Confrontare gli ID
    presenti nel repo pubblico con i soli ID attesi dal diff corrente
    cancellerebbe tutte le evidenze dei cicli precedenti, i cui nodi non
    compaiono in questo diff semplicemente perche' venivano da un altro corpus.
    Un collocamento si puo' dichiarare obsoleto solo per un nodo che il diff
    corrente conosce, e quindi per cui e' in grado di dire dove va.
    """
    expected: dict[str, set[str]] = defaultdict(set)
    known: set[str] = set()

    for item in diff.get("fit", []):
        nk = node_key(item.get("node", {}))
        if not nk:
            continue
        cap  = item.get("capability", {})
        slug = cap.get("slug") or Path(cap.get("file", "")).stem
        if slug:
            expected[nk].add(slug)
        known.add(nk)

    for item in diff.get("unclassified", []):
        nk = node_key(item.get("node", {}))
        if nk:
            known.add(nk)

    for bucket in ("new_capability", "new_domain"):
        for group in diff.get(bucket, []):
            for n in group.get("nodes", []):
                nk = node_key(n)
                if nk:
                    known.add(nk)

    return expected, known


def find_stale_placements(
    docs_dir: Path,
    expected: dict[str, set[str]],
    known: set[str],
) -> list[dict]:
    """
    Cerca nel repo pubblico i blocchi di evidenza che appartengono a nodi del
    corpus corrente ma stanno su una pagina dove il diff non li colloca piu'.

    La ricerca e' per costruzione e non per confronto: per ogni nodo conosciuto
    e per ogni pagina candidata si calcola l'ID stabile che quel nodo avrebbe su
    quella pagina, e lo si cerca fra le ancore effettivamente presenti. Il
    calcolo e' un SHA256 per coppia, quindi qualche migliaio di hash su un ciclo
    tipico, e ha il vantaggio di non richiedere alcun registro di cosa e' stato
    pubblicato: l'ID e' il registro.

    Il motivo della ricerca e' che l'ID stabile dipende dalla pagina di
    destinazione, `sha256(node_id + "::" + cap_slug)`. Una riclassificazione che
    sposta un nodo produce quindi un ID nuovo: `--refresh` scrive il blocco sulla
    pagina giusta ma non riconosce piu' quello vecchio, che resta orfano, e
    l'evidenza risulta duplicata su due pagine.

    Ogni voce restituita porta la ragione dell'obsolescenza, che governa quale
    dei due flag di rimozione la include: `moved` se il diff colloca il nodo
    altrove, `unexpected` se non lo colloca da nessuna parte.
    """
    stale: list[dict] = []

    for md_path in sorted(docs_dir.rglob("*.md")):
        md_text = md_path.read_text(encoding="utf-8")
        anchors = set(EVIDENCE_ANCHOR_RE.findall(md_text))
        if not anchors:
            continue

        slug     = md_path.stem
        rel_file = md_path.relative_to(docs_dir).as_posix()

        for nk in known:
            targets = expected.get(nk, set())
            if slug in targets:
                continue
            sid = stable_id(nk, slug)
            if sid not in anchors:
                continue
            stale.append({
                "file":      rel_file,
                "path":      md_path,
                "slug":      slug,
                "sid":       sid,
                "node_key":  nk,
                "reason":    "moved" if targets else "unexpected",
                "moved_to":  sorted(targets),
            })

    return stale


def prune_stale_placements(
    stale: list[dict],
    reasons: set[str],
    apply_mode: bool,
) -> int:
    """
    Rimuove dalle pagine i collocamenti obsoleti la cui ragione e' fra quelle
    abilitate, e restituisce quanti blocchi sono stati rimossi.

    Le voci si raggruppano per file cosi' che un file con piu' rimozioni venga
    letto e riscritto una volta sola, e la riscrittura conserva il line-ending
    nativo del file per non generare un diff CRLF↔LF su pagine preesistenti.
    """
    selected = [s for s in stale if s["reason"] in reasons]
    if not selected:
        return 0

    by_path: dict[Path, list[dict]] = defaultdict(list)
    for s in selected:
        by_path[s["path"]].append(s)

    removed = 0
    for md_path, entries in sorted(by_path.items()):
        raw_bytes        = md_path.read_bytes()
        original_newline = "\r\n" if b"\r\n" in raw_bytes else "\n"
        md_text          = md_path.read_text(encoding="utf-8")
        original_text    = md_text

        local_removed = 0
        for s in entries:
            pruned = remove_block(md_text, s["sid"])
            if pruned is None:
                print(f"  ⚠ ancora {s['sid']} non delimitabile in {s['file']}",
                      file=sys.stderr)
                continue
            md_text = pruned
            local_removed += 1

        if local_removed:
            md_text = restore_placeholder_if_empty(md_text)
            removed += local_removed
            print(f"  {entries[0]['file']}: -{local_removed} evidenze", file=sys.stderr)
            if apply_mode and md_text != original_text:
                md_path.write_text(md_text, encoding="utf-8", newline=original_newline)

    return removed


# ---------------------------------------------------------------------------
# Generazione file nuovo per new_capability
# ---------------------------------------------------------------------------

def build_new_capability_file(nc: dict, anon_map: dict | None = None) -> str:
    """
    Genera il contenuto Markdown di una nuova Capability page
    seguendo lo schema a 4 H2 standard. Se passata anon_map, la applica a
    name/preview/labels prima di scrivere.
    """
    name    = apply_anon(nc.get("suggested_name", "New Capability"), anon_map)
    domain  = nc.get("domain", {}).get("name", "Unknown Domain")
    nodes   = nc.get("nodes", [])

    # Raccoglie preview dai nodi per Overview
    previews = [
        apply_anon(n.get("text_preview", "")[:80].replace("\n", " "), anon_map)
        for n in nodes
        if n.get("text_preview")
    ]
    preview_line = previews[0] if previews else ""

    # Raccoglie label dei nodi per Responsibilities
    node_labels = [apply_anon(n.get("label", ""), anon_map) for n in nodes if n.get("label")]

    content = f"""# {name}

## Overview

*Capability identified automatically from project documentation.*
Domain: **{domain}**.
{("Evidence preview: " + preview_line) if preview_line else ""}

## Technologies & tools

*To be populated from source documentation.*

## Responsibilities & operational scope

Operational scope inferred from the following evidence nodes:

"""
    for lbl in node_labels[:10]:
        content += f"- {lbl}\n"

    content += f"""
## Projects & evidence

*Project entries are populated automatically from anonymized project
documentation. None yet.*
"""
    return content


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Applica taxonomy_diff.json alle Capability pages di skills-repo."
    )
    parser.add_argument("--diff-json",   required=True, help="Path a taxonomy_diff.json")
    parser.add_argument("--skills-repo", required=True,
                        help="Path al working tree di skills-repo")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--dry-run", action="store_true", default=True,
                             help="Mostra cosa verrebbe fatto (default)")
    parser.add_argument("--refresh", action="store_true",
                        help="Riscrive i blocchi di evidenza gia' presenti invece di "
                             "saltarli. Serve a correggere evidenze pubblicate con un "
                             "difetto della pipeline; senza questo flag l'idempotenza "
                             "per ID le protegge e non c'e' modo di aggiornarle.")
    parser.add_argument("--prune-moved", action="store_true",
                        help="Rimuove i blocchi di evidenza dei nodi che questo diff "
                             "colloca su una Capability diversa da quella dove sono "
                             "pubblicati. Senza questo flag una riclassificazione "
                             "duplica l'evidenza su due pagine, perche' l'ID stabile "
                             "dipende dalla pagina e quello vecchio resta orfano.")
    parser.add_argument("--prune-unexpected", action="store_true",
                        help="Rimuove anche i blocchi dei nodi che questo diff conosce "
                             "ma non colloca piu' su nessuna Capability, perche' sono "
                             "scesi sotto soglia. Piu' invasivo di --prune-moved: una "
                             "variazione di soglia cancellerebbe evidenze valide, "
                             "quindi va usato solo dopo aver letto l'elenco in dry-run.")
    mode_group.add_argument("--apply",   action="store_true",
                             help="Applica effettivamente le modifiche")
    args = parser.parse_args()

    apply_mode   = args.apply
    refresh_mode = args.refresh
    prune_reasons: set[str] = set()
    if args.prune_moved:
        prune_reasons.add("moved")
    if args.prune_unexpected:
        prune_reasons.add("unexpected")
    diff_path    = Path(args.diff_json).resolve()
    skills_repo  = Path(args.skills_repo).resolve()

    if not diff_path.exists():
        print(f"ERRORE: diff-json non trovato: {diff_path}", file=sys.stderr)
        sys.exit(1)
    if not skills_repo.exists():
        print(f"ERRORE: skills-repo non trovato: {skills_repo}", file=sys.stderr)
        sys.exit(1)

    docs_dir = skills_repo / "docs"
    if not docs_dir.exists():
        docs_dir = skills_repo  # Fallback

    # Line-ending dominante del docs-dir: campionato da un file esistente,
    # usato quando creiamo new capability file da zero. I file preesistenti
    # mantengono il proprio original_newline detectato per file.
    _sample = next(docs_dir.rglob("*.md"), None)
    if _sample is not None:
        _raw = _sample.read_bytes()
        repo_default_newline = "\r\n" if b"\r\n" in _raw else "\n"
    else:
        repo_default_newline = "\n"

    diff = json.loads(diff_path.read_text(encoding="utf-8"))

    mode_label = "APPLY" if apply_mode else "DRY-RUN"
    print(f"=== export_to_taxonomy [{mode_label}] ===", file=sys.stderr)
    print(f"diff-json:   {diff_path}", file=sys.stderr)
    print(f"skills-repo: {skills_repo}", file=sys.stderr)
    print(f"docs-dir:    {docs_dir}", file=sys.stderr)
    print("", file=sys.stderr)

    # Recupera anonymization_map propagata da map_to_taxonomy.py.
    # Se il diff e' stato prodotto da una versione vecchia dello script,
    # la mappa e' vuota e i testi passano in chiaro: in quel caso il dry-run
    # fara' vedere gli originali e l'utente puo' decidere se rigenerare il
    # diff con il nuovo map_to_taxonomy prima di --apply.
    anon_map: dict[str, str] = diff.get("anonymization_map", {})
    if anon_map:
        print(f"anon-map:    {len(anon_map)} voci "
              f"({sum(1 for v in anon_map.values() if v.startswith('[AZIENDA_'))} aziende, "
              f"{sum(1 for v in anon_map.values() if v.startswith('[PERSONA_'))} persone, "
              f"{sum(1 for v in anon_map.values() if v.startswith('[EMAIL_'))} email, "
              f"{sum(1 for v in anon_map.values() if v.startswith('[IP_'))} ip, "
              f"{sum(1 for v in anon_map.values() if v.startswith('[HOSTNAME_'))} hostname)",
              file=sys.stderr)
    else:
        print("anon-map:    VUOTA (diff senza anonymization_map — rigenerare?)",
              file=sys.stderr)
    print("", file=sys.stderr)

    # -----------------------------------------------------------------------
    # Processa FIT
    # -----------------------------------------------------------------------
    fit_items = diff.get("fit", [])

    # Raggruppa per capability file
    by_cap_file: dict[str, list[dict]] = defaultdict(list)
    for item in fit_items:
        cap_file = item.get("capability", {}).get("file", "")
        if cap_file:
            by_cap_file[cap_file].append(item)

    injected_count  = 0
    refreshed_count = 0
    skipped_dup     = 0
    missing_files   = 0

    print(f"--- FIT: {len(fit_items)} nodi → {len(by_cap_file)} Capability ---", file=sys.stderr)

    for cap_file, items in sorted(by_cap_file.items()):
        md_path = docs_dir / cap_file
        if not md_path.exists():
            print(f"  ⚠ File non trovato: {md_path}", file=sys.stderr)
            missing_files += 1
            continue

        # Rileva il line-ending nativo del file prima di leggere in modo
        # normalizzato: quando riscriveremo useremo lo stesso, evitando di
        # generare un diff CRLF↔LF su file preesistenti.
        raw_bytes = md_path.read_bytes()
        original_newline = "\r\n" if b"\r\n" in raw_bytes else "\n"
        md_text = md_path.read_text(encoding="utf-8")
        original_text = md_text
        cap_slug = Path(cap_file).stem

        newly_injected = []
        refreshed      = []
        for item in items:
            node           = item.get("node", {})
            community_id   = item.get("community_id")
            is_hyperedge   = item.get("is_hyperedge", False)
            cap_slug_item  = item.get("capability", {}).get("slug", cap_slug)
            sid            = stable_id(
                node.get("id", node.get("label", "")),
                cap_slug_item,
            )

            # Community label: il diff non la porta direttamente per i fit,
            # usiamo il community_id come stringa se non disponibile
            community_label = str(community_id) if community_id is not None else None
            block = build_evidence_block(node, cap_slug_item, community_label, anon_map)

            if already_injected(md_text, sid):
                if not refresh_mode:
                    skipped_dup += 1
                    continue
                replaced = replace_block(md_text, sid, block)
                if replaced is None:
                    skipped_dup += 1
                    continue
                md_text = replaced
                refreshed.append(apply_anon(node.get("label", "?"), anon_map))
                refreshed_count += 1
                continue

            md_text = inject_into_section(md_text, block)
            newly_injected.append(apply_anon(node.get("label", "?"), anon_map))
            injected_count += 1

        if newly_injected or refreshed:
            if newly_injected:
                print(f"  {cap_file}: +{len(newly_injected)} nodi", file=sys.stderr)
                for lbl in newly_injected:
                    print(f"    + {lbl}", file=sys.stderr)
            if refreshed:
                print(f"  {cap_file}: ~{len(refreshed)} nodi riscritti", file=sys.stderr)

            if apply_mode and md_text != original_text:
                md_path.write_text(md_text, encoding="utf-8", newline=original_newline)
        else:
            pass  # Nessuna modifica per questo file

    # -----------------------------------------------------------------------
    # Collocamenti obsoleti
    # -----------------------------------------------------------------------
    # La ricerca gira sempre, anche senza flag di prune, perche' il suo valore
    # primario e' diagnostico: un'evidenza duplicata su due pagine e' invisibile
    # sia nel riepilogo delle iniezioni sia nel --numstat, e si nota solo
    # confrontando gli ID. La rimozione, che e' distruttiva, resta invece
    # subordinata a un flag esplicito.
    expected, known = collect_placements(diff)
    stale        = find_stale_placements(docs_dir, expected, known) if known else []
    pruned_count = 0

    if stale:
        n_moved = sum(1 for s in stale if s["reason"] == "moved")
        n_unexp = len(stale) - n_moved
        print(f"\n--- COLLOCAMENTI OBSOLETI: {len(stale)} "
              f"({n_moved} spostati, {n_unexp} non piu' previsti) ---", file=sys.stderr)
        for s in sorted(stale, key=lambda x: (x["reason"], x["file"])):
            label = apply_anon(s["node_key"], anon_map)
            if s["reason"] == "moved":
                print(f"  {s['file']}  [{s['sid']}]  {label}", file=sys.stderr)
                print(f"      ora previsto su: {', '.join(s['moved_to'])}", file=sys.stderr)
            else:
                print(f"  {s['file']}  [{s['sid']}]  {label}", file=sys.stderr)
                print(f"      non piu' previsto su nessuna Capability", file=sys.stderr)

        if prune_reasons:
            print(f"\n  Rimozione attiva per: {', '.join(sorted(prune_reasons))}",
                  file=sys.stderr)
            pruned_count = prune_stale_placements(stale, prune_reasons, apply_mode)
        else:
            print("\n  Nessun flag di rimozione attivo: i blocchi restano dove sono.",
                  file=sys.stderr)
            print("  Usa --prune-moved (e se serve --prune-unexpected) per rimuoverli.",
                  file=sys.stderr)

    # -----------------------------------------------------------------------
    # Processa NEW CAPABILITY
    # -----------------------------------------------------------------------
    new_caps = diff.get("new_capability", [])
    print(f"\n--- NEW CAPABILITY: {len(new_caps)} suggerite ---", file=sys.stderr)

    for nc in new_caps:
        domain_dir    = nc.get("domain", {}).get("dir", "")
        sug_name_raw  = nc.get("suggested_name", "New Capability")
        sug_name      = apply_anon(sug_name_raw, anon_map)
        # Ricava slug e file path dal NAME ANONIMIZZATO, non dal suggested_slug
        # del diff (calcolato pre-anon): altrimenti IP e hostname finiscono
        # nel nome del file esposto pubblicamente.
        sug_slug      = re.sub(r"[^a-z0-9]+", "-", sug_name.lower()).strip("-") or "new-capability"
        sug_file      = f"{domain_dir}/{sug_slug}.md"
        domain_name   = nc.get("domain", {}).get("name", "?")

        new_md_path   = docs_dir / sug_file
        n_nodes       = len(nc.get("nodes", []))

        print(f"  [{domain_name}] {sug_name}", file=sys.stderr)
        print(f"    File:  {sug_file}", file=sys.stderr)
        print(f"    Nodi:  {n_nodes}", file=sys.stderr)
        print(f"    Aggiungi a mkdocs.yml sotto '{domain_name}:':", file=sys.stderr)
        print(f"      - {sug_name}: {sug_file}", file=sys.stderr)

        if apply_mode:
            if new_md_path.exists():
                print(f"    ⚠ File già esistente, salto la creazione", file=sys.stderr)
            else:
                new_md_path.parent.mkdir(parents=True, exist_ok=True)
                content = build_new_capability_file(nc, anon_map)
                new_md_path.write_text(content, encoding="utf-8", newline=repo_default_newline)
                print(f"    ✓ Creato: {new_md_path}", file=sys.stderr)
        else:
            print(f"    [dry-run] avrebbe creato: {new_md_path}", file=sys.stderr)

    # -----------------------------------------------------------------------
    # Processa NEW DOMAIN (solo stampa - troppo invasivo per automatizzare)
    # -----------------------------------------------------------------------
    new_doms = diff.get("new_domain", [])
    if new_doms:
        print(f"\n--- NEW DOMAIN: {len(new_doms)} suggeriti (azione manuale) ---",
              file=sys.stderr)
        for nd in new_doms:
            nd_name = apply_anon(nd.get('suggested_domain', '?'), anon_map)
            print(f"  {nd_name} "
                  f"({len(nd.get('nodes', []))} nodi) - valuta manualmente",
                  file=sys.stderr)

    # -----------------------------------------------------------------------
    # Riepilogo
    # -----------------------------------------------------------------------
    print(f"\n=== Riepilogo ===", file=sys.stderr)
    print(f"  Iniezioni {'eseguite' if apply_mode else 'pianificate'}: {injected_count}",
          file=sys.stderr)
    if refresh_mode:
        print(f"  Riscritte (refresh):   {refreshed_count}", file=sys.stderr)
    if stale:
        print(f"  Collocamenti obsoleti: {len(stale)}", file=sys.stderr)
        print(f"  Rimozioni {'eseguite' if apply_mode else 'pianificate'}:  {pruned_count}",
              file=sys.stderr)
    print(f"  Già presenti (skip):   {skipped_dup}", file=sys.stderr)
    print(f"  File mancanti:         {missing_files}", file=sys.stderr)
    if new_caps:
        print(f"  Nuove Capability {'create' if apply_mode else 'da creare'}: {len(new_caps)}",
              file=sys.stderr)
    if not apply_mode:
        print(f"\n  Usa --apply per applicare le modifiche.", file=sys.stderr)


if __name__ == "__main__":
    main()
