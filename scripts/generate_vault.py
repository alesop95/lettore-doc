#!/usr/bin/env python3
"""
generate_vault.py — Genera il vault Obsidian a partire dal grafo e dalle sintesi.

Input:
- graph.json (da build_knowledge_graph.py)
- structure.json (per metadati)
- entities.json (per tag e wiki-link inline)
- Cartella sezioni-preview JSON (per estratti)
- Cartella sintesi opzionale: file di testo con sintesi scritte da Claude,
  uno per docx, nominati come "<safe_stem>.md".

Output:
- vault-output/<safe_stem>.md per ogni documento
- vault-output/index.md con la Mappa della Conoscenza
- vault-output/_data/graph.json copia del grafo per Dataview
"""

import argparse
import json
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def safe_filename(name: str) -> str:
    """Versione file-system safe del nome (mantiene leggibile)."""
    stem = Path(name).stem
    # Sostituisci caratteri problematici, mantieni accenti
    return re.sub(r"[<>:\"/\\|\?\*]", "_", stem).strip()


def to_wiki_link(file_name: str) -> str:
    """Da 'Documento.docx' a '[[Documento]]'."""
    return f"[[{safe_filename(file_name)}]]"


def yaml_escape(value):
    """Escape sicuro per YAML inline (stringhe semplici)."""
    if isinstance(value, str):
        if any(c in value for c in ":#&*!|>'\"%@`"):
            return f'"{value.replace(chr(34), chr(92)+chr(34))}"'
        return value
    return value


def render_yaml_list(items, max_items=10):
    if not items:
        return "[]"
    items = items[:max_items]
    return "[" + ", ".join(yaml_escape(str(i)) for i in items) + "]"


def detect_doc_type(file_name: str, entities: dict) -> str:
    """Euristica per la tipologia del documento."""
    lower = file_name.lower()
    rules = [
        ("verbale", "verbale"),
        ("contratto", "contratto"),
        ("accordo", "contratto"),
        ("procedura", "procedura"),
        ("istruzione", "procedura"),
        ("manuale", "manuale"),
        ("capitolato", "capitolato"),
        ("specifica", "specifica"),
        ("offerta", "offerta"),
        ("preventivo", "offerta"),
        ("fattura", "amministrativo"),
        ("ddt", "amministrativo"),
        ("report", "report"),
        ("relazione", "report"),
        ("scheda", "scheda_tecnica"),
        ("modulo", "modulo"),
        ("template", "template"),
    ]
    for keyword, doctype in rules:
        if keyword in lower:
            return doctype
    return "altro"


def extract_doc_date(doc_meta: dict, entities: dict) -> str | None:
    """Cerca una data di documento. Priorità: prima data nelle entità, poi mtime."""
    dates = entities.get("DATE", [])
    if dates:
        # Prendi quella che compare di più
        return dates[0]["value"]
    return None


def generate_doc_markdown(
    doc_meta: dict,
    sections_data: dict,
    entities: dict,
    neighbors: list[dict],
    all_doc_names: set[str],
    summary_text: str | None,
) -> str:
    file_name = doc_meta["file_name"]
    title = safe_filename(file_name)
    doc_type = detect_doc_type(file_name, entities)
    doc_date = extract_doc_date(doc_meta, entities)

    # Top entità per tipologia
    top_companies = [e["value"] for e in entities.get("COMPANY", [])[:5]]
    top_projects = [e["value"] for e in entities.get("PROJECT_CODE", [])[:5]]
    top_acronyms = [e["value"] for e in entities.get("ACRONYM", [])[:8]]
    top_proper_nouns = [e["value"] for e in entities.get("PROPER_NOUN", [])[:5]]
    top_laws = [e["value"] for e in entities.get("LAW_REF", [])[:5]]

    # Tag gerarchici Obsidian
    tags = [f"tipologia/{doc_type}"]
    for c in top_companies[:3]:
        clean = re.sub(r"[^\w]", "_", c.lower()).strip("_")
        tags.append(f"azienda/{clean}")
    for p in top_projects[:3]:
        clean = re.sub(r"[^\w]", "_", p.lower()).strip("_")
        tags.append(f"progetto/{clean}")

    # Frontmatter
    lines = ["---"]
    lines.append(f"titolo: {yaml_escape(title)}")
    lines.append(f"file_sorgente: {yaml_escape(doc_meta['relative_path'])}")
    lines.append(f"tipologia: {doc_type}")
    if doc_date:
        lines.append(f"data_documento: {yaml_escape(doc_date)}")
    lines.append(f"hash_origine: {doc_meta['file_hash']}")
    lines.append(f"parole_totali: {doc_meta['total_words']}")
    lines.append(f"sezioni: {len(doc_meta['sections'])}")
    lines.append(f"collegamenti: {len(neighbors)}")
    lines.append(f"entita_principali: {render_yaml_list(top_companies + top_projects + top_proper_nouns, 8)}")
    lines.append(f"acronimi: {render_yaml_list(top_acronyms)}")
    if top_laws:
        lines.append(f"riferimenti_normativi: {render_yaml_list(top_laws)}")
    lines.append(f"tags: {render_yaml_list(tags)}")
    lines.append(f"aggiornato: {datetime.now().isoformat()}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {title}")
    lines.append("")

    # Sintesi
    if summary_text:
        lines.append("> [!summary] Sintesi")
        for line in summary_text.strip().splitlines():
            lines.append(f"> {line}")
        lines.append("")
    else:
        lines.append("> [!summary] Sintesi")
        lines.append("> *Sintesi non ancora generata. Esegui lo step 4 (sintesi narrative) del workflow.*")
        lines.append("")

    # Indice del documento
    lines.append("## Indice del documento sorgente")
    lines.append("")
    sections = sections_data.get("sections", [])
    for s in sections:
        if s.get("level", 0) == 0 and s.get("title") == "Documento completo":
            continue
        indent = "  " * max(0, (s.get("level", 1) - 1))
        wc = s.get("word_count", 0)
        lines.append(f"{indent}- **{s['title']}** _({wc} parole)_")
    lines.append("")

    # Documenti correlati
    lines.append("## Documenti correlati")
    lines.append("")
    if neighbors:
        # Raggruppa per etichetta
        by_label = defaultdict(list)
        for n in neighbors:
            by_label[n["label"]].append(n)

        label_order = [
            "riferisce_esplicitamente",
            "serie_temporale",
            "stesso_progetto",
            "condivide_entita_chiave",
            "topica_affine",
            "correlato_debole",
        ]
        label_titles = {
            "riferisce_esplicitamente": "📎 Riferimenti espliciti",
            "serie_temporale": "📅 Serie temporale",
            "stesso_progetto": "🗂 Stesso progetto",
            "condivide_entita_chiave": "🔗 Entità chiave in comune",
            "topica_affine": "🏷 Topica affine",
            "correlato_debole": "↔ Correlazione debole",
        }
        for label in label_order:
            if label not in by_label:
                continue
            lines.append(f"### {label_titles[label]}")
            for n in by_label[label]:
                lines.append(f"- {to_wiki_link(n['file'])} — peso `{n['weight']:.2f}`")
            lines.append("")
    else:
        lines.append("*Nessun documento correlato sopra la soglia minima.*")
        lines.append("")

    # Estratto strutturato
    lines.append("## Estratto per sezione")
    lines.append("")
    for s in sections:
        if s.get("level", 0) == 0 and s.get("title") == "Documento completo":
            # Doc senza heading
            if "preview_start" in s and s["preview_start"]:
                lines.append(f"> {s['preview_start']}...")
                lines.append("")
            continue
        heading_prefix = "#" * (min(s.get("level", 1) + 2, 6))
        lines.append(f"{heading_prefix} {s['title']}")
        lines.append("")
        preview = s.get("preview_start", "")
        if preview:
            # Inserisci wiki-link inline per entità note che corrispondono ad altri docx
            preview_with_links = insert_inline_wikilinks(preview, all_doc_names, file_name)
            lines.append(preview_with_links)
            if s.get("preview_end"):
                lines.append(f"\n*[…contenuto omesso, {s.get('char_count', 0)} caratteri totali…]*\n")
                lines.append(f"...{s['preview_end']}")
            lines.append("")
        else:
            lines.append(f"*({s.get('word_count', 0)} parole, vedi documento sorgente per il contenuto)*")
            lines.append("")

    # Footer
    lines.append("---")
    lines.append(f"*Documento sorgente: `{doc_meta['relative_path']}`*")
    return "\n".join(lines)


def insert_inline_wikilinks(text: str, all_doc_names: set[str], current_doc: str) -> str:
    """Sostituisce la prima occorrenza di nomi di altri documenti con wiki-link."""
    current_stem = safe_filename(current_doc).lower()
    candidates = []
    for name in all_doc_names:
        if name == current_doc:
            continue
        stem = safe_filename(name)
        # Tokens significativi del nome file (parole >= 4 lettere)
        tokens = re.findall(r"[A-Za-zÀ-ÿ]{4,}", stem)
        for tok in tokens:
            if tok.lower() not in ["docx", "doc", "file", "documento"]:
                candidates.append((tok, stem))

    # Ordina per lunghezza decrescente (match più specifici prima)
    candidates.sort(key=lambda x: -len(x[0]))
    used = set()
    for token, stem in candidates:
        if stem in used:
            continue
        pattern = re.compile(rf"\b({re.escape(token)})\b", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            text = pattern.sub(f"[[{stem}|{match.group(1)}]]", text, count=1)
            used.add(stem)
    return text


def generate_index(structure: dict, graph: dict, entities_data: dict) -> str:
    docs = structure["documents"]
    docs_entities = entities_data["documents"]

    # Raggruppa per tipologia
    by_type = defaultdict(list)
    for doc in docs:
        fname = doc["file_name"]
        ents = docs_entities.get(fname, {}).get("entities", {})
        dtype = detect_doc_type(fname, ents)
        by_type[dtype].append(doc)

    lines = ["---"]
    lines.append("titolo: Mappa della Conoscenza")
    lines.append(f"aggiornato: {datetime.now().isoformat()}")
    lines.append(f"documenti_totali: {len(docs)}")
    lines.append(f"relazioni_mappate: {graph['edge_count']}")
    lines.append("tags: [moc, indice]")
    lines.append("---")
    lines.append("")
    lines.append("# 🗺 Mappa della Conoscenza — Documenti IT Intrawelt")
    lines.append("")
    lines.append(f"> **Aggiornato**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"> **Documenti totali**: {len(docs)}")
    lines.append(f"> **Relazioni mappate**: {graph['edge_count']}")
    lines.append(f"> **Hub identificati**: {len(graph['hubs'])}")
    lines.append(f"> **Cluster tematici**: {len(graph['clusters'])}")
    lines.append(f"> **Documenti isolati**: {len(graph['isolated'])}")
    lines.append("")

    # Per tipologia
    lines.append("## Per tipologia")
    lines.append("")
    type_order = ["procedura", "contratto", "verbale", "manuale", "capitolato",
                  "specifica", "offerta", "report", "scheda_tecnica", "modulo",
                  "template", "amministrativo", "altro"]
    type_emojis = {
        "procedura": "🔧", "contratto": "📜", "verbale": "📋", "manuale": "📖",
        "capitolato": "🏗", "specifica": "📐", "offerta": "💼", "report": "📊",
        "scheda_tecnica": "🔬", "modulo": "📝", "template": "🧩",
        "amministrativo": "🧾", "altro": "📄",
    }

    for dtype in type_order:
        if dtype not in by_type:
            continue
        emoji = type_emojis.get(dtype, "📄")
        lines.append(f"### {emoji} {dtype.capitalize()} ({len(by_type[dtype])})")
        lines.append("")
        for doc in sorted(by_type[dtype], key=lambda d: d["file_name"]):
            words = doc["total_words"]
            lines.append(f"- {to_wiki_link(doc['file_name'])} — _{words} parole_")
        lines.append("")

    # Hub
    if graph["hubs"]:
        lines.append("## 🌐 Hub (documenti più connessi)")
        lines.append("")
        lines.append("Documenti con molte relazioni: spesso sono indici, capitolati generali, "
                     "o documenti di riferimento trasversali.")
        lines.append("")
        for hub in graph["hubs"][:15]:
            lines.append(f"- {to_wiki_link(hub['file'])} — **{hub['edges']} relazioni**")
        lines.append("")

    # Cluster
    if graph["clusters"]:
        lines.append("## 🏷 Cluster tematici")
        lines.append("")
        lines.append("Raggruppamenti per entità chiave più rappresentativa di ogni documento.")
        lines.append("")
        sorted_clusters = sorted(graph["clusters"].items(), key=lambda x: -len(x[1]))
        for seed, doc_list in sorted_clusters[:20]:
            if len(doc_list) < 2:
                continue
            lines.append(f"### {seed} ({len(doc_list)})")
            lines.append("")
            for fname in sorted(doc_list):
                lines.append(f"- {to_wiki_link(fname)}")
            lines.append("")

    # Isolati
    if graph["isolated"]:
        lines.append("## 🏝 Documenti isolati")
        lines.append("")
        lines.append("Documenti senza relazioni sopra la soglia minima. Candidati per: "
                     "verifica classificazione, archiviazione, o aggiornamento.")
        lines.append("")
        for fname in graph["isolated"][:50]:
            lines.append(f"- {to_wiki_link(fname)}")
        if len(graph["isolated"]) > 50:
            lines.append(f"- _...e altri {len(graph['isolated']) - 50}._")
        lines.append("")

    # Top entità globali
    lines.append("## 🔝 Entità più frequenti nell'intera documentazione")
    lines.append("")
    top_global = entities_data.get("global_top_entities", {})
    for cat_label, cat_key in [
        ("Aziende", "COMPANY"),
        ("Codici progetto", "PROJECT_CODE"),
        ("Acronimi", "ACRONYM"),
        ("Nomi propri", "PROPER_NOUN"),
        ("Riferimenti normativi", "LAW_REF"),
    ]:
        items = top_global.get(cat_key, [])[:10]
        if not items:
            continue
        lines.append(f"### {cat_label}")
        lines.append("")
        for it in items:
            lines.append(f"- **{it['value']}** _(in {it['count']} occorrenze)_")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 📌 Come navigare questo vault")
    lines.append("")
    lines.append("1. Apri questo file in **Obsidian** dopo aver impostato la cartella `vault-output` come Vault")
    lines.append("2. Usa la **Graph view** (Ctrl/Cmd+G) per visualizzare la rete delle relazioni")
    lines.append("3. Clicca su qualsiasi `[[link]]` per saltare al documento")
    lines.append("4. Usa la barra di ricerca per cercare per tag (es. `tag:#progetto/prj-001`)")
    lines.append("5. Plugin consigliati: **Dataview**, **Breadcrumbs**, **Graph Analysis**")
    lines.append("")
    lines.append("> Nota: questo vault è generato. Per modifiche permanenti, aggiorna i documenti sorgente "
                 "e rilancia il workflow di indicizzazione.")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Genera il vault Obsidian")
    parser.add_argument("--graph", required=True)
    parser.add_argument("--structure", required=True)
    parser.add_argument("--entities", required=True)
    parser.add_argument("--sections-dir", required=True,
                        help="Cartella con i JSON sections-preview")
    parser.add_argument("--summaries-dir", default=None,
                        help="Cartella opzionale con .md di sintesi (uno per docx)")
    parser.add_argument("--output", required=True, help="Cartella vault output")
    args = parser.parse_args()

    graph = json.loads(Path(args.graph).read_text(encoding="utf-8"))
    structure = json.loads(Path(args.structure).read_text(encoding="utf-8"))
    entities_data = json.loads(Path(args.entities).read_text(encoding="utf-8"))
    sections_dir = Path(args.sections_dir)
    summaries_dir = Path(args.summaries_dir) if args.summaries_dir else None
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "_data").mkdir(exist_ok=True)

    all_doc_names = {d["file_name"] for d in structure["documents"]}
    neighbors_map = graph.get("neighbors", {})

    print(f"Generazione vault in {output_dir}...", file=sys.stderr)

    for doc in structure["documents"]:
        fname = doc["file_name"]
        safe_stem = re.sub(r"[^\w\-_.]", "_", Path(fname).stem)
        sections_json = sections_dir / f"{safe_stem}.json"
        if not sections_json.exists():
            print(f"  ! manca sezioni per {fname}, salto", file=sys.stderr)
            continue

        sections_data = json.loads(sections_json.read_text(encoding="utf-8"))
        doc_entities = entities_data["documents"].get(fname, {}).get("entities", {})
        doc_neighbors = neighbors_map.get(fname, [])

        summary_text = None
        if summaries_dir:
            summary_file = summaries_dir / f"{safe_stem}.md"
            if summary_file.exists():
                summary_text = summary_file.read_text(encoding="utf-8")

        md = generate_doc_markdown(
            doc_meta=doc,
            sections_data=sections_data,
            entities=doc_entities,
            neighbors=doc_neighbors,
            all_doc_names=all_doc_names,
            summary_text=summary_text,
        )

        out_file = output_dir / f"{safe_filename(fname)}.md"
        out_file.write_text(md, encoding="utf-8")
        print(f"  ✓ {out_file.name}", file=sys.stderr)

    # Index
    index_md = generate_index(structure, graph, entities_data)
    (output_dir / "index.md").write_text(index_md, encoding="utf-8")

    # Copia il grafo per debug/Dataview
    shutil.copy(args.graph, output_dir / "_data" / "graph.json")
    shutil.copy(args.entities, output_dir / "_data" / "entities.json")

    print(f"\n✓ Vault generato in {output_dir}", file=sys.stderr)
    print(f"  - {structure['document_count']} file .md", file=sys.stderr)
    print(f"  - 1 index.md", file=sys.stderr)
    print(f"  - _data/ con grafo ed entità", file=sys.stderr)
    print(f"\nApri {output_dir} come Vault in Obsidian.", file=sys.stderr)


if __name__ == "__main__":
    main()
