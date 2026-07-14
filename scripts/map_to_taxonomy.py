#!/usr/bin/env python3
"""
map_to_taxonomy.py - Classifica i nodi di enriched_graph.json verso la tassonomia.

Per ogni nodo e hyperedge del grafo calcola il match score verso ogni Capability
della tassonomia e li classifica in:
  - fit            → nodo da aggiungere a Projects & evidence di una Capability esistente
  - new_capability → nodo che suggerisce una nuova Capability in un Domain esistente
  - new_domain     → nodo che suggerisce un Domain completamente nuovo

Produce taxonomy_diff.md per revisione manuale prima di applicare le modifiche.

Input:
  enriched_graph.json     (output di enrich_graph.py)
  taxonomy_index.json     (output di generate_taxonomy_index.py)

Output:
  taxonomy_diff.md        (diff strutturato per revisione)
  taxonomy_diff.json      (stessa info in formato machine-readable per export_to_taxonomy.py)

Uso:
  python scripts/map_to_taxonomy.py \\
    --enriched-graph _intermediate/enriched_graph.json \\
    --taxonomy       _intermediate/taxonomy_index.json \\
    --output-md      _intermediate/taxonomy_diff.md \\
    --output-json    _intermediate/taxonomy_diff.json
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Soglie di classificazione
# ---------------------------------------------------------------------------
THRESHOLD_FIT       = 0.15   # recall_cap >= questa → fit
THRESHOLD_DOMAIN    = 0.08   # domain_recall >= questa → new_capability nel domain
MIN_SCORE_REPORT    = 0.01   # sotto questa soglia → non classificato

# Numero minimo di nodi per proporre una new_capability
MIN_NODES_NEW_CAP   = 2

# Stopwords per tokenizzazione
STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "in", "for", "to", "with",
    "on", "at", "by", "from", "is", "are", "was", "be", "been",
    "it", "its", "as", "use", "using", "via", "see", "also",
    "this", "that", "all", "per", "such", "based", "based",
    "setup", "operations", "tools", "tool", "system", "systems",
    "management", "workflow", "complete", "full", "advanced",
    "multiple", "single", "two", "one", "three", "four", "five",
}


# ---------------------------------------------------------------------------
# Tokenizzazione
# ---------------------------------------------------------------------------

def tokenize(text: str) -> set[str]:
    """Estrae token significativi da una stringa."""
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9\+\#\.]{2,}", text.lower())
    return {t for t in tokens if t not in STOPWORDS and len(t) >= 3}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def recall_score(node_tokens: set[str], keyword_set: set[str]) -> float:
    """
    Proporzione dei token del nodo che matchano le keyword.
    Misura quanto il nodo è 'coperto' dalla Capability.
    """
    if not node_tokens:
        return 0.0
    matches = node_tokens & keyword_set
    return len(matches) / len(node_tokens)


def match_capability(
    node_tokens: set[str],
    taxonomy: dict,
) -> tuple[float, dict | None, dict | None]:
    """
    Restituisce (best_score, best_capability_dict, best_domain_dict).
    Considera anche parziale: anche se nessuna Capability supera THRESHOLD_FIT,
    individua il Domain più affine per suggerire new_capability.
    """
    best_cap_score   = 0.0
    best_cap         = None
    best_domain      = None
    best_domain_score = 0.0

    for domain in taxonomy["domains"]:
        domain_kw_set = set(domain.get("domain_keywords", []))
        d_score = recall_score(node_tokens, domain_kw_set)

        if d_score > best_domain_score:
            best_domain_score = d_score
            best_domain = domain

        for cap in domain["capabilities"]:
            cap_kw_set = set(cap.get("keywords", []))
            c_score = recall_score(node_tokens, cap_kw_set)
            if c_score > best_cap_score:
                best_cap_score = c_score
                best_cap = cap
                if d_score == 0.0:
                    # Forza il domain al Capability domain anche se d_score basso
                    best_domain = domain

    return best_cap_score, best_cap, best_domain


# ---------------------------------------------------------------------------
# Suggerimento nome new_capability
# ---------------------------------------------------------------------------

def suggest_capability_name(
    nodes_in_cluster: list[dict],
    community_label: str | None,
) -> tuple[str, str]:
    """
    Suggerisce (nome, slug) per una nuova Capability
    basandosi sul community_label e sui label dei nodi.
    """
    if community_label:
        name = community_label.title()
        slug = re.sub(r"[^a-z0-9]+", "-", community_label.lower()).strip("-")
    else:
        # Prendi il label del nodo più connesso (primo della lista)
        label = nodes_in_cluster[0].get("label", "New Capability") if nodes_in_cluster else "New Capability"
        name = label
        slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return name, slug


# ---------------------------------------------------------------------------
# Classificazione di tutti i nodi
# ---------------------------------------------------------------------------

def classify_nodes(
    enriched_graph: dict,
    taxonomy: dict,
) -> dict:
    """
    Classifica nodi e hyperedges.
    Restituisce dict strutturato per la generazione del diff.
    """
    nodes        = enriched_graph.get("nodes", [])
    hyperedges   = enriched_graph.get("graph", {}).get("hyperedges", [])

    # Mappa community id → community label (graphify mette i label nel GRAPH_REPORT
    # ma non esplicitamente nel graph.json per ogni nodo)
    # Usiamo il community index numerico + il label estratto dal GRAPH_REPORT se disponibile
    # Qui usiamo i label dei nodi stessi come proxy
    community_labels: dict[int, list[str]] = defaultdict(list)
    for node in nodes:
        cid = node.get("community", -1)
        community_labels[cid].append(node.get("norm_label", ""))

    # Costruiamo community_name da graphify se presente nel grafo (v8+)
    # In v7 non c'è: usiamo il nodo più "centrale" (primo della lista) come nome
    community_name_map: dict[int, str] = {}
    for cid, labels in community_labels.items():
        # Prendi il label più lungo come rappresentativo
        rep = max(labels, key=len) if labels else str(cid)
        community_name_map[cid] = rep.title()

    results = {
        "generated_at": datetime.now().isoformat(),
        "fit":           [],   # {node, capability, domain, score}
        "new_capability": [],  # {community_id, community_label, domain, nodes, suggested_name, suggested_slug}
        "new_domain":     [],  # {community_id, community_label, nodes, suggested_domain}
        "unclassified":   [],  # {node, best_score}
    }

    # --- Classifica nodi ---
    # Raggruppa i "near-miss" per community per proporre new_capability coerenti
    near_miss_by_community: dict[int, list[tuple[dict, dict | None, float]]] = defaultdict(list)

    for node in nodes:
        label         = node.get("label", "")
        norm_label    = node.get("norm_label", "")
        community_id  = node.get("community", -1)

        # Token del nodo: norm_label + token dal community name
        node_tokens = tokenize(norm_label)
        cname = community_name_map.get(community_id, "")
        community_tokens = tokenize(cname)
        combined_tokens = node_tokens | community_tokens

        cap_score, best_cap, best_domain = match_capability(combined_tokens, taxonomy)

        if cap_score >= THRESHOLD_FIT and best_cap:
            # Individua il domain di questa capability
            cap_domain = None
            for d in taxonomy["domains"]:
                if any(c["slug"] == best_cap["slug"] for c in d["capabilities"]):
                    cap_domain = d
                    break
            results["fit"].append({
                "node":        node,
                "capability":  best_cap,
                "domain":      cap_domain,
                "score":       round(cap_score, 3),
                "community_id": community_id,
            })
        elif cap_score >= MIN_SCORE_REPORT:
            near_miss_by_community[community_id].append((node, best_domain, cap_score))
        else:
            results["unclassified"].append({
                "node":       node,
                "best_score": round(cap_score, 3),
            })

    # --- Raggruppa near-miss per community → new_capability ---
    for community_id, cluster in near_miss_by_community.items():
        if not cluster:
            continue

        cname = community_name_map.get(community_id, f"Community {community_id}")
        # Domain più frequente nel cluster
        domain_counts: dict[str, int] = defaultdict(int)
        domain_objs: dict[str, dict] = {}
        for _, dom, _ in cluster:
            if dom:
                domain_counts[dom["name"]] += 1
                domain_objs[dom["name"]] = dom
        best_domain_name = max(domain_counts, key=domain_counts.get) if domain_counts else None
        best_domain_obj  = domain_objs.get(best_domain_name) if best_domain_name else None

        cluster_nodes = [n for n, _, _ in cluster]
        avg_score = sum(s for _, _, s in cluster) / len(cluster)

        domain_score = 0.0
        if best_domain_obj:
            domain_kw = set(best_domain_obj.get("domain_keywords", []))
            all_tokens = set()
            for n in cluster_nodes:
                all_tokens |= tokenize(n.get("norm_label", ""))
            domain_score = recall_score(all_tokens, domain_kw)

        sug_name, sug_slug = suggest_capability_name(cluster_nodes, cname)

        if domain_score >= THRESHOLD_DOMAIN and best_domain_obj:
            results["new_capability"].append({
                "community_id":     community_id,
                "community_label":  cname,
                "domain":           best_domain_obj,
                "nodes":            cluster_nodes,
                "avg_score":        round(avg_score, 3),
                "domain_score":     round(domain_score, 3),
                "suggested_name":   sug_name,
                "suggested_slug":   sug_slug,
                "suggested_file":   f"{best_domain_obj['dir']}/{sug_slug}.md",
            })
        else:
            results["new_domain"].append({
                "community_id":     community_id,
                "community_label":  cname,
                "nodes":            cluster_nodes,
                "avg_score":        round(avg_score, 3),
                "suggested_domain": sug_name,
            })

    # --- Classifica hyperedges ---
    for he in hyperedges:
        label  = he.get("label", "")
        tokens = tokenize(label)
        cap_score, best_cap, best_domain = match_capability(tokens, taxonomy)
        # Gli hyperedge si aggiungono solo ai fit forti (sono già aggregazioni)
        if cap_score >= THRESHOLD_FIT and best_cap:
            cap_domain = None
            for d in taxonomy["domains"]:
                if any(c["slug"] == best_cap["slug"] for c in d["capabilities"]):
                    cap_domain = d
                    break
            results["fit"].append({
                "node":        {"label": label, "id": he.get("id", ""), "file_type": "hyperedge",
                                "source_file": he.get("source_file", ""), "text_preview": "",
                                "italian_entities": {}},
                "capability":  best_cap,
                "domain":      cap_domain,
                "score":       round(cap_score, 3),
                "is_hyperedge": True,
            })

    return results


# ---------------------------------------------------------------------------
# Generazione taxonomy_diff.md
# ---------------------------------------------------------------------------

def render_markdown(results: dict, source_graph: str) -> str:
    lines = []
    ts = results["generated_at"]
    n_fit    = len(results["fit"])
    n_new    = len(results["new_capability"])
    n_dom    = len(results["new_domain"])
    n_unc    = len(results["unclassified"])

    lines += [
        f"# Taxonomy Diff",
        f"",
        f"Generated: {ts}",
        f"Source: `{source_graph}`",
        f"",
        f"## Summary",
        f"",
        f"| Classificazione | Nodi |",
        f"|-----------------|------|",
        f"| ✅ Fit (Capability esistente) | {n_fit} |",
        f"| 🆕 New Capability suggerite   | {n_new} |",
        f"| 🗂 New Domain suggeriti       | {n_dom} |",
        f"| ⚠️ Non classificati           | {n_unc} |",
        f"",
        f"---",
        f"",
    ]

    # ---- FIT ----
    lines += [
        f"## ✅ Fit - Capability esistenti da aggiornare",
        f"",
        f"> Questi nodi vanno aggiunti alla sezione **Projects & evidence**",
        f"> della Capability corrispondente in `skills-repo`.",
        f"",
    ]
    if results["fit"]:
        # Raggruppa per Capability
        by_cap: dict[str, list[dict]] = defaultdict(list)
        for item in results["fit"]:
            key = f"[{item['domain']['name']}] {item['capability']['name']}" if item.get("domain") else "?"
            by_cap[key].append(item)
        for cap_key, items in sorted(by_cap.items()):
            first = items[0]
            lines += [
                f"### {cap_key}",
                f"File: `{first['capability']['file']}`",
                f"",
            ]
            for item in items:
                node = item["node"]
                is_hyper = item.get("is_hyperedge", False)
                tag = " *(hyperedge)*" if is_hyper else ""
                lines.append(f"- **{node['label']}**{tag} (score: {item['score']})")
                if node.get("source_file"):
                    lines.append(f"  - Source: `{node['source_file']}`")
                if node.get("text_preview"):
                    preview = node["text_preview"][:120].replace("\n", " ")
                    lines.append(f"  - Preview: *{preview}...*")
                ents = node.get("italian_entities", {})
                companies = [e["value"] for e in ents.get("COMPANY", [])[:3]]
                if companies:
                    lines.append(f"  - Aziende: {', '.join(companies)}")
            lines.append("")
    else:
        lines += ["*Nessun nodo classificato come fit.*", ""]

    lines += ["---", ""]

    # ---- NEW CAPABILITY ----
    lines += [
        f"## 🆕 New Capabilities suggerite",
        f"",
        f"> Queste Capability non esistono ancora nella tassonomia.",
        f"> Revisiona, rinomina se necessario, poi crea il file `.md` corrispondente",
        f"> e aggiorna `mkdocs.yml`.",
        f"",
    ]
    if results["new_capability"]:
        for nc in sorted(results["new_capability"], key=lambda x: -x["domain_score"]):
            dom_name = nc["domain"]["name"]
            lines += [
                f"### [{dom_name}] → **{nc['suggested_name']}** *(NUOVA)*",
                f"",
                f"- Domain score: {nc['domain_score']} | Avg node score: {nc['avg_score']}",
                f"- Slug suggerito: `{nc['suggested_slug']}`",
                f"- File suggerito: `docs/{nc['suggested_file']}`",
                f"- Aggiungere a `mkdocs.yml` sotto `{dom_name}:`",
                f"",
                f"**Nodi che giustificano questa Capability:**",
                f"",
            ]
            for node in nc["nodes"]:
                lines.append(f"- `{node['label']}` (community: {nc['community_label']})")
                if node.get("text_preview"):
                    preview = node["text_preview"][:100].replace("\n", " ")
                    lines.append(f"  *{preview}...*")
            lines.append("")
    else:
        lines += ["*Nessuna nuova Capability suggerita.*", ""]

    lines += ["---", ""]

    # ---- NEW DOMAIN ----
    lines += [
        f"## 🗂 New Domains suggeriti",
        f"",
        f"> Domain score troppo basso per classificare in un Domain esistente.",
        f"> Valuta se creare un nuovo Domain o se il nodo è irrilevante.",
        f"",
    ]
    if results["new_domain"]:
        for nd in results["new_domain"]:
            lines += [
                f"### **{nd['suggested_domain']}** *(DOMINIO NUOVO)*",
                f"",
                f"- Avg score: {nd['avg_score']}",
                f"",
                f"**Nodi:**",
            ]
            for node in nd["nodes"]:
                lines.append(f"- `{node['label']}`")
            lines.append("")
    else:
        lines += ["*Nessun nuovo Domain suggerito.*", ""]

    lines += ["---", ""]

    # ---- NON CLASSIFICATI ----
    if results["unclassified"]:
        lines += [
            f"## ⚠️ Non classificati (score < {MIN_SCORE_REPORT})",
            f"",
        ]
        for item in results["unclassified"]:
            lines.append(f"- `{item['node']['label']}` (best score: {item['best_score']})")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Classifica nodi del grafo verso la tassonomia di skills-repo."
    )
    parser.add_argument("--enriched-graph", required=True,
                        help="Path a enriched_graph.json")
    parser.add_argument("--taxonomy",       required=True,
                        help="Path a taxonomy_index.json")
    parser.add_argument("--output-md",      required=True,
                        help="Output taxonomy_diff.md")
    parser.add_argument("--output-json",    required=True,
                        help="Output taxonomy_diff.json")
    args = parser.parse_args()

    graph_path    = Path(args.enriched_graph).resolve()
    taxonomy_path = Path(args.taxonomy).resolve()
    md_path       = Path(args.output_md).resolve()
    json_path     = Path(args.output_json).resolve()

    for p in (graph_path, taxonomy_path):
        if not p.exists():
            print(f"ERRORE: file non trovato: {p}", file=sys.stderr)
            sys.exit(1)

    print(f"Carico enriched_graph da {graph_path}", file=sys.stderr)
    enriched_graph = json.loads(graph_path.read_text(encoding="utf-8"))

    print(f"Carico taxonomy_index da {taxonomy_path}", file=sys.stderr)
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))

    n_nodes = len(enriched_graph.get("nodes", []))
    n_hyper = len(enriched_graph.get("graph", {}).get("hyperedges", []))
    n_caps  = sum(len(d["capabilities"]) for d in taxonomy["domains"])
    print(f"Grafo: {n_nodes} nodi, {n_hyper} hyperedges | Tassonomia: {n_caps} Capability",
          file=sys.stderr)

    results = classify_nodes(enriched_graph, taxonomy)

    # Statistiche
    n_fit  = len(results["fit"])
    n_new  = len(results["new_capability"])
    n_dom  = len(results["new_domain"])
    n_unc  = len(results["unclassified"])
    print(f"\nClassificazione:", file=sys.stderr)
    print(f"  Fit:              {n_fit}", file=sys.stderr)
    print(f"  New Capability:   {n_new}", file=sys.stderr)
    print(f"  New Domain:       {n_dom}", file=sys.stderr)
    print(f"  Non classificati: {n_unc}", file=sys.stderr)

    # Scrivi taxonomy_diff.md
    md_content = render_markdown(results, str(graph_path))
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md_content, encoding="utf-8")
    print(f"\nScritto: {md_path}", file=sys.stderr)

    # Scrivi taxonomy_diff.json (per export_to_taxonomy.py)
    # Serializza rimuovendo oggetti non serializzabili
    def sanitize(obj):
        if isinstance(obj, dict):
            return {k: sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [sanitize(i) for i in obj]
        return obj

    # Propaga la anonymization_map dell'enriched_graph nel diff, cosi'
    # export_to_taxonomy la applica ai label/name/preview prima di scriverli
    # nel repo pubblico.
    diff_out = {
        **results,
        "anonymization_map":
            enriched_graph.get("graph", {}).get("anonymization_map", {}),
    }

    json_path.write_text(
        json.dumps(sanitize(diff_out), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Scritto: {json_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
