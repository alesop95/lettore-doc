#!/usr/bin/env python3
"""
extract_entities.py — Estrazione entita da documenti italiani.

Input: JSON prodotti da parse_docx.py (sections-preview o full).
Output: entities.json con entita per documento e classifica globale.

Non usa modelli ML: solo regex e euristica linguistica. Veloce, deterministico, offline.

Categorie:
- ACRONYM       sigle 2-7 lettere maiuscole (es. RTI, DURC, SAL)
- COMPANY       ragioni sociali (SpA, Srl, SaS, SCarl, Ltd, GmbH...)
- PROPER_NOUN   nomi propri (Mario Rossi, AlphaBeta)
- PROJECT_CODE  codici progetto (PRJ-001, TECH-2024-08)
- LAW_REF       riferimenti normativi (D.Lgs, L., DPR, Reg. UE, art.)
- DATE          date in vari formati
- AMOUNT        importi in euro
- EMAIL         indirizzi email
- URL           web
- DOC_REF       riferimenti a documenti ("vedi specifica X.docx")
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# ============================================================
# Pattern
# ============================================================

ACRONYM_RE = re.compile(r"(?<![A-Za-z])([A-Z]{2,7})(?![A-Za-z])")
ACRONYM_STOPLIST = {
    "PDF", "DOCX", "XLSX", "PPTX", "OK", "KO", "TBD", "TBC", "NA", "ND", "IT", "EN",
    "URL", "API", "GUI", "CSV", "XML", "JSON", "HTML", "CSS", "SQL", "ID", "IP",
    "USB", "PC", "MAC", "OS", "RAM", "CPU", "GPU", "AM", "PM", "GMT", "CET",
    "VS", "ECC", "ETC", "ES", "EX", "CV", "PEC", "FAX", "TEL", "WEB",
    "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
    "WWW", "HTTP", "HTTPS", "FTP", "TCP", "UDP", "DNS", "SSL", "TLS",
    "UE", "USA", "UK", "ONU", "NATO", "UNI", "ISO", "IEC", "CE",
}

COMPANY_SUFFIX_RE = re.compile(
    r"\b([A-ZÀ-Ý][\w&\.\-]{1,40}(?:\s+[A-ZÀ-Ý][\w&\.\-]{1,40}){0,4})\s+"
    r"(S\.p\.A\.|SpA|S\.r\.l\.|Srl|S\.n\.c\.|Snc|S\.a\.s\.|Sas|S\.S\.|"
    r"SCarl|Coop\.?|Ltd\.?|GmbH|Inc\.?|Corp\.?|LLC|S\.A\.|SA|AG|NV|BV)"
    r"(?![\w])"
)

PROPER_NOUN_RE = re.compile(
    r"(?<![\.\!\?]\s)(?<!^)([A-ZÀ-Ý][a-zà-ÿ]+(?:\s+(?:di|della|del|degli|delle|dei|da|de|d')\s+)?"
    r"(?:[A-ZÀ-Ý][a-zà-ÿ]+)(?:\s+[A-ZÀ-Ý][a-zà-ÿ]+){0,2})"
)

LAW_REF_RE = re.compile(
    r"(?:D\.?\s?Lgs\.?|D\.?\s?L\.?|D\.?\s?P\.?R\.?|D\.?\s?M\.?|Legge|"
    r"Reg(?:olamento)?\.?\s*(?:UE|CE|CEE)?|Direttiva|art(?:icolo|t)?\.?|"
    r"comma\s+|Allegato\s+)\s*"
    r"n?\.?\s*\d+(?:[\./\-]\d+)*(?:/\d+)?",
    re.IGNORECASE,
)

PROJECT_CODE_RE = re.compile(
    r"\b([A-Z]{2,5}[-_/]\d{1,4}(?:[-_/][A-Z0-9]{1,8}){0,3})\b"
)

DATE_RE = re.compile(
    r"\b(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}|"
    r"\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}|"
    r"\d{1,2}\s+(?:gennaio|febbraio|marzo|aprile|maggio|giugno|"
    r"luglio|agosto|settembre|ottobre|novembre|dicembre)\s+\d{4})\b",
    re.IGNORECASE,
)

AMOUNT_RE = re.compile(
    r"(?:euro|EUR)\s*([\d\.\,]+(?:\,\d{2})?)|"
    r"([\d\.\,]+(?:\,\d{2})?)\s*(?:euro|EUR)",
    re.IGNORECASE,
)
AMOUNT_SYMBOL_RE = re.compile(r"\u20AC\s*([\d\.\,]+(?:\,\d{2})?)|([\d\.\,]+(?:\,\d{2})?)\s*\u20AC")

EMAIL_RE = re.compile(r"\b[\w\.\-]+@[\w\.\-]+\.\w{2,}\b")
URL_RE = re.compile(r"https?://[^\s\)\]]+|www\.[^\s\)\]]+")

DOC_REF_RE = re.compile(
    r"(?:vedi|cfr\.?|secondo|come\s+da|in\s+base\s+(?:a|al|alla))\s+"
    r"(?:il\s+|la\s+|lo\s+)?"
    r"(?:documento|procedura|specifica|verbale|allegato|capitolato|contratto|manuale)?\s*"
    r"([A-Za-zÀ-ÿ0-9][\w\-\.\s]{2,60}?\.docx?)",
    re.IGNORECASE,
)

ITALIAN_STOPWORDS = {
    "Il", "Lo", "La", "I", "Gli", "Le", "Un", "Uno", "Una", "Del", "Dello",
    "Della", "Dei", "Degli", "Delle", "Al", "Allo", "Alla", "Ai", "Agli", "Alle",
    "Dal", "Dallo", "Dalla", "Dai", "Dagli", "Dalle", "Nel", "Nello", "Nella",
    "Nei", "Negli", "Nelle", "Sul", "Sullo", "Sulla", "Sui", "Sugli", "Sulle",
    "Per", "Con", "Senza", "Tra", "Fra", "Su", "In", "A", "Di", "Da",
    "Questo", "Questa", "Questi", "Queste", "Quello", "Quella", "Quelli", "Quelle",
    "Tale", "Tali", "Stesso", "Stessa", "Stessi", "Stesse",
    "Articolo", "Comma", "Punto", "Capo", "Titolo", "Sezione", "Allegato", "Capitolo",
    "Anno", "Mese", "Giorno", "Data", "Sede", "Ufficio",
}

# Falsi positivi LAW_REF
DATE_AS_LAW_RE = re.compile(r"^[Ll]\.?\s*\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}$")
SHORT_L_GARBAGE_RE = re.compile(r"^[Ll]\.?\s*\d{1,2}\s*$")


# ============================================================
# Estrazione e normalizzazione
# ============================================================

def extract_from_text(text: str) -> dict[str, list[str]]:
    """Applica tutti i pattern e ritorna dict di liste con duplicati."""
    results = defaultdict(list)

    for m in ACRONYM_RE.finditer(text):
        ac = m.group(1)
        if ac not in ACRONYM_STOPLIST:
            results["ACRONYM"].append(ac)

    company_substrings = set()
    for m in COMPANY_SUFFIX_RE.finditer(text):
        name = m.group(1).strip()
        suffix = m.group(2).strip()
        full = f"{name} {suffix}"
        results["COMPANY"].append(full)
        company_substrings.update(name.split())

    for m in LAW_REF_RE.finditer(text):
        candidate = m.group(0).strip()
        if DATE_AS_LAW_RE.match(candidate) or SHORT_L_GARBAGE_RE.match(candidate):
            continue
        results["LAW_REF"].append(candidate)

    for m in PROJECT_CODE_RE.finditer(text):
        results["PROJECT_CODE"].append(m.group(1))

    for m in DATE_RE.finditer(text):
        results["DATE"].append(m.group(1))

    for m in AMOUNT_RE.finditer(text):
        val = m.group(1) or m.group(2)
        if val:
            results["AMOUNT"].append(f"EUR {val}")
    for m in AMOUNT_SYMBOL_RE.finditer(text):
        val = m.group(1) or m.group(2)
        if val:
            results["AMOUNT"].append(f"EUR {val}")

    for m in EMAIL_RE.finditer(text):
        results["EMAIL"].append(m.group(0))
    for m in URL_RE.finditer(text):
        results["URL"].append(m.group(0))

    for m in DOC_REF_RE.finditer(text):
        results["DOC_REF"].append(m.group(1).strip())

    for m in PROPER_NOUN_RE.finditer(text):
        candidate = m.group(1).strip()
        first_word = candidate.split()[0]
        if first_word in ITALIAN_STOPWORDS:
            continue
        if any(w in company_substrings for w in candidate.split()):
            continue
        if len(candidate.split()) >= 2 or len(candidate) > 8:
            results["PROPER_NOUN"].append(candidate)

    return dict(results)


def collect_text(doc_data: dict) -> str:
    """Concatena tutto il testo disponibile in un JSON parse_docx."""
    parts = []
    for s in doc_data.get("sections", []):
        parts.append(s.get("title", ""))
        if "preview_start" in s:
            parts.append(s.get("preview_start", ""))
            parts.append(s.get("preview_end", ""))
        if "paragraphs" in s:
            parts.extend(s.get("paragraphs", []))
        if "tables" in s:
            for table in s.get("tables", []):
                for row in table:
                    parts.extend(str(v) for v in row.values())
    return "\n".join(p for p in parts if p)


def normalize_and_dedupe(entities: dict[str, list[str]]) -> dict[str, list[dict]]:
    """Conta occorrenze, deduplica, ordina per frequenza."""
    out = {}
    for category, items in entities.items():
        counter = Counter(items)
        out[category] = [{"value": v, "count": c} for v, c in counter.most_common() if c > 0]
    return out


def merge_company_aliases(global_companies: list[dict]) -> list[dict]:
    """Unifica varianti della stessa azienda (AlphaBeta SpA == AlphaBeta S.p.A.)."""
    if not global_companies:
        return global_companies

    def normalize_key(name):
        # rimuovi suffisso aziendale, spazi e punteggiatura, lowercase
        key = re.sub(r"\s+(S\.?p\.?A\.?|S\.?r\.?l\.?|S\.?a\.?s\.?|S\.?n\.?c\.?|SCarl|Coop\.?|Ltd\.?|GmbH|Inc\.?|Corp\.?|LLC|S\.?A\.?|AG|NV|BV)\s*$",
                     "", name, flags=re.IGNORECASE)
        return re.sub(r"[^\w]", "", key.lower())

    grouped = defaultdict(list)
    for entry in global_companies:
        grouped[normalize_key(entry["value"])].append(entry)

    merged = []
    for key, entries in grouped.items():
        # tieni il nome piu lungo come canonico, somma i count
        canonical = max(entries, key=lambda e: len(e["value"]))
        total = sum(e["count"] for e in entries)
        merged.append({"value": canonical["value"], "count": total})
    merged.sort(key=lambda e: -e["count"])
    return merged


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Estrazione entita da JSON di parse_docx.py")
    parser.add_argument("--structure", required=True, help="structure.json (parse_docx skeleton)")
    parser.add_argument("--full-text", required=True, help="Cartella sections-preview JSON")
    parser.add_argument("--output", required=True, help="JSON output entita")
    args = parser.parse_args()

    structure_path = Path(args.structure).resolve()
    sections_dir = Path(args.full_text).resolve()
    output_path = Path(args.output).resolve()

    if not structure_path.exists():
        print(f"File non trovato: {structure_path}", file=sys.stderr)
        sys.exit(1)
    if not sections_dir.exists():
        print(f"Cartella non trovata: {sections_dir}", file=sys.stderr)
        sys.exit(1)

    structure = json.loads(structure_path.read_text(encoding="utf-8"))
    print(f"Estrazione entita da {structure['document_count']} documenti...", file=sys.stderr)

    all_docs_entities = {}
    global_counts = defaultdict(Counter)

    for doc in structure["documents"]:
        file_name = doc["file_name"]
        safe_stem = re.sub(r"[^\w\-_.]", "_", Path(file_name).stem)
        json_path = sections_dir / f"{safe_stem}.json"

        if not json_path.exists():
            print(f"  ! manca {json_path.name}, salto", file=sys.stderr)
            continue

        doc_data = json.loads(json_path.read_text(encoding="utf-8"))
        text = collect_text(doc_data)
        raw = extract_from_text(text)
        normalized = normalize_and_dedupe(raw)

        all_docs_entities[file_name] = {
            "relative_path": doc["relative_path"],
            "file_hash": doc["file_hash"],
            "entities": normalized,
            "entity_count_total": sum(len(v) for v in normalized.values()),
        }

        for cat, items in normalized.items():
            for item in items:
                global_counts[cat][item["value"]] += item["count"]

    top_global = {}
    for cat, counter in global_counts.items():
        items = [{"value": v, "count": c} for v, c in counter.most_common(80)]
        if cat == "COMPANY":
            items = merge_company_aliases(items)[:50]
        top_global[cat] = items[:50]

    output = {"documents": all_docs_entities, "global_top_entities": top_global}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nScritto: {output_path}", file=sys.stderr)
    print(f"Entita globali piu frequenti per categoria:", file=sys.stderr)
    for cat, items in top_global.items():
        if items:
            top3 = ", ".join(f"{i['value']}({i['count']})" for i in items[:3])
            print(f"  {cat}: {top3}", file=sys.stderr)


if __name__ == "__main__":
    main()
