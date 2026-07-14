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
    sid      = stable_id(node.get("id", node.get("label", "")), cap_slug)
    label    = apply_anon(node.get("label", "Untitled"), anon_map)
    src_file = node.get("source_file", "")
    preview  = apply_anon(node.get("text_preview", "").strip(), anon_map)

    src_basename = Path(src_file).name if src_file else "-"
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
    mode_group.add_argument("--apply",   action="store_true",
                             help="Applica effettivamente le modifiche")
    args = parser.parse_args()

    apply_mode   = args.apply
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
        for item in items:
            node           = item.get("node", {})
            community_id   = item.get("community_id")
            is_hyperedge   = item.get("is_hyperedge", False)
            cap_slug_item  = item.get("capability", {}).get("slug", cap_slug)
            sid            = stable_id(
                node.get("id", node.get("label", "")),
                cap_slug_item,
            )

            if already_injected(md_text, sid):
                skipped_dup += 1
                continue

            # Community label: il diff non la porta direttamente per i fit,
            # usiamo il community_id come stringa se non disponibile
            community_label = str(community_id) if community_id is not None else None

            block = build_evidence_block(node, cap_slug_item, community_label, anon_map)
            md_text = inject_into_section(md_text, block)
            newly_injected.append(apply_anon(node.get("label", "?"), anon_map))
            injected_count += 1

        if newly_injected:
            print(f"  {cap_file}: +{len(newly_injected)} nodi", file=sys.stderr)
            for lbl in newly_injected:
                print(f"    + {lbl}", file=sys.stderr)

            if apply_mode and md_text != original_text:
                md_path.write_text(md_text, encoding="utf-8", newline=original_newline)
        else:
            pass  # Nessuna modifica per questo file

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
    print(f"  Già presenti (skip):   {skipped_dup}", file=sys.stderr)
    print(f"  File mancanti:         {missing_files}", file=sys.stderr)
    if new_caps:
        print(f"  Nuove Capability {'create' if apply_mode else 'da creare'}: {len(new_caps)}",
              file=sys.stderr)
    if not apply_mode:
        print(f"\n  Usa --apply per applicare le modifiche.", file=sys.stderr)


if __name__ == "__main__":
    main()
