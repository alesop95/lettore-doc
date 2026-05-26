#!/usr/bin/env python3
"""
enrich_graph.py — Arricchisce il graph.json prodotto da graphify con entità
italiane estratte dai file sorgente, e costruisce una mappa di anonimizzazione.

Input:
  graph.json           (output di graphify)
  --workdir            cartella base dove era stato lanciato graphify
                       (serve per risolvere i source_file dei nodi)

Output:
  enriched_graph.json  stesso schema di graph.json +
                       - ogni nodo: campo italian_entities, text_preview
                       - campo di grafo: enrichment_metadata, anonymization_map

La anonymization_map è un dizionario {nome_reale: placeholder} usato da
map_to_taxonomy.py quando cita frammenti di testo nei Projects & evidence.
Sostituisce nomi propri con "[PERSONA_N]" e ragioni sociali con "[AZIENDA_N]".

I nodi graphify hanno già label in inglese (graphify traduce),
quindi la privacy layer agisce sul testo dei file sorgente, non sui label.

Uso:
  python scripts/enrich_graph.py \\
    --graph  graphify-out/graph.json \\
    --workdir E:\\lettore-doc-intrawelt\\version-control-copy-prova \\
    --output _intermediate/enriched_graph.json
"""

import argparse
import copy
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Import delle regex italiane da extract_entities.py
# ---------------------------------------------------------------------------
# Lo script vive in scripts/ insieme a extract_entities.py
_scripts_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_scripts_dir))

try:
    from extract_entities import (
        extract_from_text,
        normalize_and_dedupe,
        merge_company_aliases,
    )
except ImportError as e:
    print(f"ERRORE: impossibile importare extract_entities.py da {_scripts_dir}: {e}",
          file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Lettura testo dai file sorgente
# ---------------------------------------------------------------------------

def read_source_text(source_file: str, workdir: Path) -> str | None:
    """
    Risolve il source_file relativo rispetto a workdir e legge il testo.
    Gestisce .md, .txt. Salta .png, .jpg, .url, .7z e altri binari.
    Restituisce None se il file non è leggibile o non è testo.
    """
    if not source_file:
        return None

    SKIP_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp",
                       ".url", ".7z", ".zip", ".exe", ".json"}
    path = workdir / source_file
    if not path.exists():
        return None
    if path.suffix.lower() in SKIP_EXTENSIONS:
        return None

    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Costruzione della anonymization_map globale
# ---------------------------------------------------------------------------

def build_anonymization_map(
    all_entities: dict[str, list[dict]],
) -> dict[str, str]:
    """
    Costruisce {nome_reale: placeholder} per COMPANY e PROPER_NOUN.

    Ordina per frequenza decrescente in modo che i nomi più citati
    ricevano il numero più basso (AZIENDA_1 = la più citata).
    """
    anon_map: dict[str, str] = {}
    company_counter = 0
    person_counter = 0

    for item in all_entities.get("COMPANY", []):
        company_counter += 1
        anon_map[item["value"]] = f"[AZIENDA_{company_counter}]"

    for item in all_entities.get("PROPER_NOUN", []):
        person_counter += 1
        anon_map[item["value"]] = f"[PERSONA_{person_counter}]"

    return anon_map


def anonymize_text(text: str, anon_map: dict[str, str]) -> str:
    """Sostituisce occorrenze delle chiavi di anon_map nel testo."""
    if not anon_map:
        return text
    # Ordina per lunghezza decrescente (match più specifici prima)
    for original in sorted(anon_map, key=len, reverse=True):
        placeholder = anon_map[original]
        text = re.sub(re.escape(original), placeholder, text)
    return text


# ---------------------------------------------------------------------------
# Aggregazione entità globali (su tutti i nodi)
# ---------------------------------------------------------------------------

def aggregate_global_entities(
    node_entities: list[dict],
) -> dict[str, list[dict]]:
    """
    Somma i conteggi delle entità estratte da tutti i nodi.
    node_entities è una lista di dict {category: [{value, count}, ...]}
    """
    global_counts: dict[str, Counter] = defaultdict(Counter)

    for node_ents in node_entities:
        for category, items in node_ents.items():
            for item in items:
                global_counts[category][item["value"]] += item["count"]

    result: dict[str, list[dict]] = {}
    for category, counter in global_counts.items():
        items = [{"value": v, "count": c} for v, c in counter.most_common()]
        if category == "COMPANY":
            items = merge_company_aliases(items)
        result[category] = items

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Arricchisce graph.json con entità italiane e anonymization_map."
    )
    parser.add_argument("--graph",   required=True, help="Path al graph.json di graphify")
    parser.add_argument("--workdir", required=True,
                        help="Cartella dove era stato lanciato graphify "
                             "(per risolvere i source_file dei nodi)")
    parser.add_argument("--output",  required=True, help="Output enriched_graph.json")
    parser.add_argument("--no-anonymize", action="store_true",
                        help="Disabilita la costruzione della anonymization_map")
    args = parser.parse_args()

    graph_path  = Path(args.graph).resolve()
    workdir     = Path(args.workdir).resolve()
    output_path = Path(args.output).resolve()

    if not graph_path.exists():
        print(f"ERRORE: graph.json non trovato: {graph_path}", file=sys.stderr)
        sys.exit(1)
    if not workdir.exists():
        print(f"ERRORE: workdir non trovata: {workdir}", file=sys.stderr)
        sys.exit(1)

    print(f"Carico graph.json da {graph_path}", file=sys.stderr)
    graph = json.loads(graph_path.read_text(encoding="utf-8"))

    nodes     = graph.get("nodes", [])
    links     = graph.get("links", [])
    graph_hdr = graph.get("graph", {})

    print(f"Grafo: {len(nodes)} nodi, {len(links)} archi", file=sys.stderr)

    # -----------------------------------------------------------------------
    # Per ogni nodo: leggi testo sorgente, applica regex italiane
    # -----------------------------------------------------------------------
    enriched_nodes = []
    all_node_entities: list[dict] = []
    skipped_no_text = 0
    processed_with_text = 0

    for node in nodes:
        n = copy.deepcopy(node)
        source_file = node.get("source_file", "")
        text = read_source_text(source_file, workdir)

        if text:
            processed_with_text += 1
            raw = extract_from_text(text)
            normalized = normalize_and_dedupe(raw)
            n["italian_entities"] = normalized
            n["text_preview"] = text[:200].strip()
            if normalized:
                all_node_entities.append(normalized)
        else:
            skipped_no_text += 1
            n["italian_entities"] = {}
            n["text_preview"] = ""

        enriched_nodes.append(n)

    print(f"Nodi con testo estratto: {processed_with_text}",  file=sys.stderr)
    print(f"Nodi senza testo (skip): {skipped_no_text}", file=sys.stderr)

    # -----------------------------------------------------------------------
    # Aggrega entità globali e costruisci anonymization_map
    # -----------------------------------------------------------------------
    global_entities = aggregate_global_entities(all_node_entities)

    anon_map: dict[str, str] = {}
    if not args.no_anonymize:
        anon_map = build_anonymization_map(global_entities)
        print(f"Anonymization map: {len(anon_map)} voci "
              f"({sum(1 for v in anon_map.values() if 'AZIENDA' in v)} aziende, "
              f"{sum(1 for v in anon_map.values() if 'PERSONA' in v)} persone)",
              file=sys.stderr)
    else:
        print("Anonimizzazione disabilitata (--no-anonymize)", file=sys.stderr)

    # -----------------------------------------------------------------------
    # Assembla enriched_graph.json
    # -----------------------------------------------------------------------
    enriched = {
        "directed":   graph.get("directed",   False),
        "multigraph": graph.get("multigraph", False),
        "graph": {
            **graph_hdr,
            "enrichment_metadata": {
                "enriched_at":          datetime.now().isoformat(),
                "workdir":              str(workdir),
                "nodes_total":          len(nodes),
                "nodes_with_text":      processed_with_text,
                "nodes_skipped":        skipped_no_text,
                "anonymization_entries": len(anon_map),
                "global_entity_counts": {
                    cat: len(items)
                    for cat, items in global_entities.items()
                    if items
                },
            },
            "anonymization_map":    anon_map,
            "global_entities":      global_entities,
        },
        "nodes": enriched_nodes,
        "links": links,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(enriched, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\nScritto: {output_path}", file=sys.stderr)

    # Riepilogo entità globali trovate
    for cat, items in global_entities.items():
        if items:
            top3 = ", ".join(f"{i['value']}({i['count']})" for i in items[:3])
            print(f"  {cat:15s}: {top3}", file=sys.stderr)

    if anon_map:
        print("\nAnonymization map (prime 10 voci):", file=sys.stderr)
        for k, v in list(anon_map.items())[:10]:
            print(f"  {v:20s} ← {k}", file=sys.stderr)


if __name__ == "__main__":
    main()
