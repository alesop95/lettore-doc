#!/usr/bin/env python3
"""
build_knowledge_graph.py — Costruisce il grafo di relazioni tra documenti.

Input:
- structure.json (da parse_docx skeleton)
- entities.json (da extract_entities)

Output:
- graph.json con archi pesati ed etichettati semanticamente.

Algoritmo:
peso(A,B) = w1*Jaccard(entità) + w2*riferimenti + w3*vicinanza_cartella
          + w4*vicinanza_temporale + w5*similarità_titolo
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Pesi default
W_JACCARD = 0.40
W_EXPLICIT_REF = 0.30
W_FOLDER = 0.10
W_TEMPORAL = 0.10
W_TITLE_SIM = 0.10

MIN_EDGE_WEIGHT = 0.15
MAX_LINKS_PER_DOC = 8

ENTITY_CATEGORIES_FOR_JACCARD = [
    "ACRONYM", "COMPANY", "PROPER_NOUN", "PROJECT_CODE",
]


def normalize_for_match(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def get_entity_set(doc_entities: dict) -> set[str]:
    """Restituisce l'insieme di entità normalizzate utili per Jaccard."""
    out = set()
    for cat in ENTITY_CATEGORIES_FOR_JACCARD:
        for item in doc_entities.get(cat, []):
            normalized = normalize_for_match(item["value"])
            if len(normalized) > 2:
                out.add(normalized)
    return out


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def folder_proximity(path_a: str, path_b: str) -> float:
    """1.0 stessa cartella, 0.5 stessa cartella padre, 0 altrimenti."""
    a = Path(path_a).parent
    b = Path(path_b).parent
    if a == b:
        return 1.0
    if a.parent == b.parent and len(a.parts) > 0 and len(b.parts) > 0:
        return 0.5
    return 0.0


def temporal_proximity(mtime_a: str, mtime_b: str) -> float:
    """1.0 entro 7 giorni, decresce linearmente fino a 180 giorni → 0."""
    try:
        da = datetime.fromisoformat(mtime_a)
        db = datetime.fromisoformat(mtime_b)
    except (ValueError, TypeError):
        return 0.0
    delta = abs((da - db).days)
    if delta <= 7:
        return 1.0
    if delta >= 180:
        return 0.0
    return 1.0 - ((delta - 7) / (180 - 7))


def title_similarity(name_a: str, name_b: str) -> float:
    """
    Estrae la "radice" del nome file (parole significative) e misura overlap.
    Es: 'Verbale-2024-Q1.docx' e 'Verbale-2024-Q2.docx' → 0.67.
    """
    def tokenize(name):
        stem = Path(name).stem.lower()
        tokens = re.findall(r"[a-z0-9]+", stem)
        # Filtra token comuni
        skip = {"docx", "doc", "v", "ver", "rev", "final", "draft", "copia", "copy", "new", "old"}
        return set(t for t in tokens if t not in skip and len(t) > 1)

    ta, tb = tokenize(name_a), tokenize(name_b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def count_explicit_refs(entities_a: dict, file_name_b: str) -> int:
    """Quante volte il nome file B (o suo stem) appare nei DOC_REF di A."""
    stem_b = Path(file_name_b).stem.lower()
    count = 0
    for ref in entities_a.get("DOC_REF", []):
        ref_lower = ref["value"].lower()
        if stem_b in ref_lower or Path(ref_lower).stem == stem_b:
            count += ref["count"]
    return count


def edge_label(jac: float, explicit: int, folder: float, temporal: float,
               title_sim: float, shared_entities: int) -> str:
    """Etichetta semantica dell'arco, in ordine di priorità."""
    if explicit > 0:
        return "riferisce_esplicitamente"
    if title_sim >= 0.5 and temporal >= 0.3:
        return "serie_temporale"
    if title_sim >= 0.4:
        return "stesso_progetto"
    if shared_entities >= 5:
        return "condivide_entita_chiave"
    if jac >= 0.15:
        return "topica_affine"
    return "correlato_debole"


def build_graph(structure: dict, entities_data: dict) -> dict:
    docs = structure["documents"]
    docs_entities = entities_data["documents"]

    # Pre-calcola insiemi entità
    entity_sets = {}
    for doc in docs:
        fname = doc["file_name"]
        if fname in docs_entities:
            entity_sets[fname] = get_entity_set(docs_entities[fname]["entities"])
        else:
            entity_sets[fname] = set()

    edges = []
    n = len(docs)

    print(f"Calcolo {n*(n-1)//2} archi candidati...", file=sys.stderr)

    for i in range(n):
        for j in range(i + 1, n):
            doc_a, doc_b = docs[i], docs[j]
            name_a, name_b = doc_a["file_name"], doc_b["file_name"]

            ents_a = entity_sets.get(name_a, set())
            ents_b = entity_sets.get(name_b, set())

            jac = jaccard(ents_a, ents_b)
            shared = len(ents_a & ents_b)

            refs_a_to_b = count_explicit_refs(
                docs_entities.get(name_a, {}).get("entities", {}), name_b
            )
            refs_b_to_a = count_explicit_refs(
                docs_entities.get(name_b, {}).get("entities", {}), name_a
            )
            explicit = refs_a_to_b + refs_b_to_a

            folder = folder_proximity(doc_a["relative_path"], doc_b["relative_path"])
            temporal = temporal_proximity(doc_a["mtime_iso"], doc_b["mtime_iso"])
            title_sim = title_similarity(name_a, name_b)

            weight = (
                W_JACCARD * jac
                + W_EXPLICIT_REF * min(explicit / 3.0, 1.0)
                + W_FOLDER * folder
                + W_TEMPORAL * temporal
                + W_TITLE_SIM * title_sim
            )

            if weight < MIN_EDGE_WEIGHT:
                continue

            label = edge_label(jac, explicit, folder, temporal, title_sim, shared)

            edges.append({
                "source": name_a,
                "target": name_b,
                "weight": round(weight, 4),
                "label": label,
                "components": {
                    "jaccard_entities": round(jac, 4),
                    "shared_entity_count": shared,
                    "explicit_refs": explicit,
                    "folder_proximity": round(folder, 4),
                    "temporal_proximity": round(temporal, 4),
                    "title_similarity": round(title_sim, 4),
                },
                "shared_entities_examples": sorted(list(ents_a & ents_b))[:5],
            })

    edges.sort(key=lambda e: e["weight"], reverse=True)

    # Top-K vicini per nodo
    neighbors = defaultdict(list)
    for e in edges:
        if len(neighbors[e["source"]]) < MAX_LINKS_PER_DOC:
            neighbors[e["source"]].append(
                {"file": e["target"], "weight": e["weight"], "label": e["label"]}
            )
        if len(neighbors[e["target"]]) < MAX_LINKS_PER_DOC:
            neighbors[e["target"]].append(
                {"file": e["source"], "weight": e["weight"], "label": e["label"]}
            )

    # Identifica hub (>15 archi sopra soglia)
    edge_counts = defaultdict(int)
    for e in edges:
        edge_counts[e["source"]] += 1
        edge_counts[e["target"]] += 1
    hubs = sorted(
        [(name, count) for name, count in edge_counts.items() if count >= 15],
        key=lambda x: x[1], reverse=True,
    )

    # Documenti isolati (nessun arco sopra soglia)
    all_names = {d["file_name"] for d in docs}
    connected = set(edge_counts.keys())
    isolated = sorted(all_names - connected)

    # Cluster naive: per entità più frequente di ogni doc
    cluster_seed = {}
    for doc in docs:
        fname = doc["file_name"]
        ents = docs_entities.get(fname, {}).get("entities", {})
        # Trova l'entità più "forte" tra COMPANY > PROJECT_CODE > PROPER_NOUN
        seed = None
        for cat in ["COMPANY", "PROJECT_CODE", "PROPER_NOUN", "ACRONYM"]:
            if ents.get(cat):
                seed = ents[cat][0]["value"]
                break
        cluster_seed[fname] = seed or "non-classificato"

    clusters = defaultdict(list)
    for fname, seed in cluster_seed.items():
        clusters[seed].append(fname)
    # Solo cluster con >= 2 documenti
    clusters = {k: v for k, v in clusters.items() if len(v) >= 2}

    return {
        "generated_at": datetime.now().isoformat(),
        "document_count": len(docs),
        "edge_count": len(edges),
        "edges": edges,
        "neighbors": dict(neighbors),
        "hubs": [{"file": n, "edges": c} for n, c in hubs],
        "isolated": isolated,
        "clusters": clusters,
        "weights_config": {
            "jaccard": W_JACCARD,
            "explicit_ref": W_EXPLICIT_REF,
            "folder": W_FOLDER,
            "temporal": W_TEMPORAL,
            "title_sim": W_TITLE_SIM,
            "min_edge_weight": MIN_EDGE_WEIGHT,
            "max_links_per_doc": MAX_LINKS_PER_DOC,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Costruisce il grafo di conoscenza")
    parser.add_argument("--entities", required=True, help="entities.json")
    parser.add_argument("--structure", required=True, help="structure.json")
    parser.add_argument("--output", required=True, help="Output graph.json")
    args = parser.parse_args()

    structure = json.loads(Path(args.structure).read_text(encoding="utf-8"))
    entities = json.loads(Path(args.entities).read_text(encoding="utf-8"))

    graph = build_graph(structure, entities)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n✓ Grafo costruito", file=sys.stderr)
    print(f"  Nodi: {graph['document_count']}", file=sys.stderr)
    print(f"  Archi sopra soglia: {graph['edge_count']}", file=sys.stderr)
    print(f"  Hub: {len(graph['hubs'])}", file=sys.stderr)
    print(f"  Isolati: {len(graph['isolated'])}", file=sys.stderr)
    print(f"  Cluster: {len(graph['clusters'])}", file=sys.stderr)
    print(f"  Scritto: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
