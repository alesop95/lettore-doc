#!/usr/bin/env python3
"""
extract_entities.py - Estrazione entita da documenti italiani.

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
- IP_ADDR       indirizzi IPv4 (192.168.20.5, 10.1.116.3/24)
- HOSTNAME      hostname/machine name (WINGROUPSHARE, USG-FLEX-500, PC-GIGI, VM101)
- DOC_REF       riferimenti a documenti ("vedi specifica X.docx")

Le categorie EMAIL, IP_ADDR, HOSTNAME sono usate da enrich_graph per estendere
la anonymization_map con placeholder [EMAIL_N], [IP_N], [HOSTNAME_N] cosi da
non far trapelare configurazioni infrastrutturali nelle evidenze esportate.
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# ============================================================
# spaCy NER (lazy load) - usato per PROPER_NOUN con label PER
# ============================================================

_NLP = None
_SPACY_TRIED = False
_SPACY_MODEL = "it_core_news_lg"


def _get_nlp():
    """Carica il modello spaCy italiano alla prima chiamata.
    Restituisce None se spaCy o il modello non sono installati: in quel caso
    il chiamante fa fallback a regex+stoplist (sub-ottimale)."""
    global _NLP, _SPACY_TRIED
    if _NLP is not None:
        return _NLP
    if _SPACY_TRIED:
        return None
    _SPACY_TRIED = True
    try:
        import spacy  # type: ignore
    except ImportError:
        print(
            "AVVISO: pacchetto 'spacy' non installato. "
            "Esegui: pip install -r requirements.txt",
            file=sys.stderr,
        )
        print("Fallback regex+stoplist per PROPER_NOUN.", file=sys.stderr)
        return None
    try:
        _NLP = spacy.load(
            _SPACY_MODEL,
            disable=["tagger", "morphologizer", "parser", "lemmatizer", "attribute_ruler"],
        )
        return _NLP
    except OSError:
        print(
            f"AVVISO: modello spaCy '{_SPACY_MODEL}' non installato. "
            f"Esegui: python -m spacy download {_SPACY_MODEL}",
            file=sys.stderr,
        )
        print("Fallback regex+stoplist per PROPER_NOUN.", file=sys.stderr)
        return None


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
    r"(?<![\.\!\?]\s)(?<!^)("
    r"[A-ZÀ-Ý][a-zà-ÿ]+"
    r"(?:\s+(?:di|della|del|degli|delle|dei|da|de|d')\s+|\s+)"
    r"[A-ZÀ-Ý][a-zà-ÿ]+"
    r"(?:\s+[A-ZÀ-Ý][a-zà-ÿ]+){0,2}"
    r")"
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

# IPv4 dotted-quad, con CIDR opzionale. Cattura anche IP di rete tipo 192.168.20.0/24.
# Ottetto 0-255 ma il pattern accetta 0-999 e filtra a valle: piu' semplice del RFC-esatto
# e sufficiente per lo scopo di anonimizzazione (falsi positivi = altro numero anonimizzato,
# non pericoloso; falsi negativi = leak, pericoloso).
IP_ADDR_RE = re.compile(
    r"(?<![\d\.])"
    r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:/\d{1,2})?)"
    r"(?![\d\.])"
)

# HOSTNAME - due strategie in OR:
#  1. Prefisso "infrastrutturale" + resto: WIN* / SRV* / PC- / NAS* / USG* / VM<num> / DC* / HOST*.
#  2. Uppercase con dash (>=1) e almeno un digit o >=8 char: USG-FLEX-500, XGS2220-30HP-EU0101F.
# Il filtro TECH_BRAND_STOPWORDS + HOSTNAME_STOPLIST tolgono i falsi positivi tipici.
HOSTNAME_PREFIX_RE = re.compile(
    r"\b("
    r"WIN(?:SRV|GROUP|SERVER|DC|SQL|EX|HOST)?[A-Z0-9][A-Z0-9\-]{2,}"
    r"|SRV[-_]?[A-Z0-9][A-Z0-9\-]{1,}"
    r"|PC[-_][A-Z0-9][A-Z0-9\-]{1,}"
    r"|NAS[-_]?[A-Z0-9][A-Z0-9\-]{0,}"
    r"|USG[-_]?[A-Z0-9][A-Z0-9\-]{0,}"
    r"|VM\d{1,4}(?:[-_][A-Z0-9\-]+)?"
    r"|DC\d{1,2}(?:[-_][A-Z0-9\-]+)?"
    r"|HOST[-_]?[A-Z0-9][A-Z0-9\-]{1,}"
    r")\b"
)
HOSTNAME_DASHED_RE = re.compile(
    r"\b([A-Z][A-Z0-9]{1,}(?:-[A-Z0-9]+){1,}[A-Z0-9]?)\b"
)
HOSTNAME_STOPLIST = {
    # Codici versione / prodotto che matchano il pattern dashed ma non sono hostname.
    "IT-EN", "EN-IT", "UTF-8", "UTF-16", "ISO-8859", "X-64", "X86-64",
    "WIN-32", "WIN-64", "MAC-OS", "IPV-4", "IPV-6",
    "RFC-822", "RFC-2822", "RFC-5321", "RFC-5322",
    "TCP-IP", "IP-SEC", "HTTP-2", "HTTP-3",
    "IEEE-802", "IEEE-8021X",
    "USB-3", "USB-C", "HDMI-2", "PCI-E", "PCI-EX", "M-2",
    "DDR-4", "DDR-5", "SATA-3", "SATA-III", "SAS-3",
    "US-EN", "IT-IT", "EN-US", "EN-GB", "FR-FR", "DE-DE", "ES-ES",
}

DOC_REF_RE = re.compile(
    r"(?:vedi|cfr\.?|secondo|come\s+da|in\s+base\s+(?:a|al|alla))\s+"
    r"(?:il\s+|la\s+|lo\s+)?"
    r"(?:documento|procedura|specifica|verbale|allegato|capitolato|contratto|manuale)?\s*"
    r"([A-Za-zÀ-ÿ0-9][\w\-\.\s]{2,60}?\.docx?)",
    re.IGNORECASE,
)

TECH_BRAND_STOPWORDS = {
    # Vendor/brand
    "Microsoft", "Apple", "Google", "Amazon", "Meta", "Facebook",
    "Intel", "AMD", "NVIDIA", "Qualcomm", "ARM",
    "Cisco", "Juniper", "Fortinet", "Palo", "Sophos", "Symantec", "McAfee",
    "Oracle", "IBM", "SAP", "Salesforce", "Atlassian",
    "Adobe", "Autodesk", "VMware", "Red", "RedHat", "Canonical", "SUSE",
    "Asrock", "Asus", "ASUS", "Gigabyte", "MSI", "Acer", "Lenovo", "Dell", "HP",
    "Samsung", "Kingston", "Western", "Seagate", "Hitachi", "Toshiba", "Crucial",
    "Logitech", "Razer", "Corsair",
    "Telegram", "WhatsApp", "Signal", "Slack", "Discord", "Zoom",
    "GitHub", "GitLab", "Bitbucket", "Atlassian",
    # OS / tech
    "Windows", "Win", "Linux", "Ubuntu", "Xubuntu", "Lubuntu", "Kubuntu",
    "Debian", "Fedora", "CentOS", "Arch", "Mint", "MacOS", "OSX", "iOS", "Android",
    "AnduinOS", "Noble", "Plucky",
    # Tools / commands / frameworks / products
    "Power", "PowerShell", "Bash", "Python", "Java", "JavaScript", "TypeScript",
    "Bit", "BitLocker", "OneDrive", "OneNote", "Outlook", "SharePoint", "Teams",
    "Office", "Edge", "Chrome", "Firefox", "Safari", "Opera",
    "Acrobat", "Photoshop", "Illustrator",
    "Docker", "Kubernetes", "Terraform", "Ansible", "Puppet", "Chef",
    "Xbox", "Skype", "LinkedIn", "Yammer", "Stream",
    "Cortana", "Siri", "Alexa",
    "Visual", "Studio", "Code", "Notepad", "Word", "Excel",
    "Active", "Directory", "Internet", "Explorer", "Group", "Policy",
    "Server", "Client", "Mobile", "Desktop", "Cloud",
    "Mixed", "Reality", "Async", "Sync", "Cred", "Dialog",
    "Audio", "Video", "Image", "Webp", "Web",
    "Wmi", "WmiObject", "Get", "Set", "New", "Remove", "Appx", "AppxPackage",
    "Original", "Product", "Microsoftcorporation",
    "Boot", "Hardware", "Software", "Driver", "Firmware", "Kernel",
    "Disk", "Drive", "Partition", "Volume", "File", "Folder",
    "User", "Account", "Login", "Logoff", "Password",
    "Memory", "Integrity", "Security", "Update", "Upgrade",
    "Secure", "Trusted", "Platform", "Module",
    "Gnome", "GNOME", "Cinnamon", "Plasma", "Mate",
    "Ubuntu", "Fedora", "Mint",
    "Clonezilla", "Rufus", "BalenaEtcher", "Etcher", "UNetbootin",
    "Dism", "Diskpart", "Diskmgmt", "Sysprep",
    "Wim", "ISO", "USB", "DVD", "CD", "HDD", "SSD", "NVMe",
    "Bios", "BIOS", "UEFI", "AMI", "Phoenix",
    "Tcp", "Udp", "Http", "Https", "Ftp", "Sftp", "Ssh", "Telnet",
    "Json", "Xml", "Yaml", "Csv", "Sql",
    "Photo", "Screenshot", "Image",
    # Vendor e prodotti di sicurezza. Aggiunti dal ciclo Cybersec endpoint:
    # senza di questi il NER classificava "Bitdefender Gravityzone" come nome
    # di persona, cioe' mascherava con [PERSONA_N] il prodotto centrale del
    # corpus. Sono esattamente i termini che devono restare visibili
    # nell'evidenza pubblica, perche' sono la competenza dichiarata.
    "Bitdefender", "GravityZone", "Gravityzone", "ESET", "Eset",
    "Kaspersky", "Avast", "AVG", "Malwarebytes", "Norton",
    "CrowdStrike", "SentinelOne", "Defender", "Trellix", "Cylance",
    "Nessus", "OpenVAS", "Qualys", "Tenable", "Metasploit", "Wireshark",
    "Veeam", "Proxmox", "Zyxel", "Fortigate", "pfSense", "OPNsense",
}

# Versione minuscola per i confronti sui percorsi che producono token gia'
# normalizzati in maiuscolo (hostname). Si costruisce una volta sola.
_TECH_BRAND_LOWER = {w.lower() for w in TECH_BRAND_STOPWORDS}

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

    for m in IP_ADDR_RE.finditer(text):
        candidate = m.group(1)
        # Filtro base: nessun ottetto > 255. Riduce collisioni con version number
        # (es. 999.98.88), pattern data 2025.03.10, ecc.
        parts = candidate.split("/")[0].split(".")
        try:
            octets = [int(p) for p in parts]
        except ValueError:
            continue
        if any(o > 255 for o in octets):
            continue
        results["IP_ADDR"].append(candidate)

    # Il confronto con TECH_BRAND_STOPWORDS va fatto case-insensitive: le due
    # regex hostname matchano solo maiuscolo per costruzione, mentre la stoplist
    # e' scritta in forma capitalizzata. Confrontandole cosi' com'erano, il
    # filtro non scattava mai su questo percorso: "WINDOWS" passava come
    # hostname pur essendo gia' presente come "Windows" fra i brand, e in un
    # corpus di endpoint security finiva mascherato come [HOSTNAME_N] ovunque.
    hostname_seen: set[str] = set()
    for m in HOSTNAME_PREFIX_RE.finditer(text):
        h = m.group(1)
        if h in hostname_seen or h in HOSTNAME_STOPLIST:
            continue
        if h.lower() in _TECH_BRAND_LOWER:
            continue
        hostname_seen.add(h)
        results["HOSTNAME"].append(h)
    for m in HOSTNAME_DASHED_RE.finditer(text):
        h = m.group(1)
        if h in hostname_seen or h in HOSTNAME_STOPLIST:
            continue
        if h.lower() in _TECH_BRAND_LOWER:
            continue
        # Salta acronimi puri gia' scartati come ACRONYM: se non ha ne' digit
        # ne' >=3 dash-parts, non e' un hostname credibile.
        if not any(c.isdigit() for c in h) and h.count("-") < 2:
            continue
        hostname_seen.add(h)
        results["HOSTNAME"].append(h)

    for m in DOC_REF_RE.finditer(text):
        results["DOC_REF"].append(m.group(1).strip())

    nlp = _get_nlp()
    if nlp is not None:
        # spaCy NER: estrae solo entita' label PER (persone), alta precisione
        # su italiano formale. Si applica comunque il filtro TECH_BRAND_STOPWORDS
        # come safety net per eventuali mis-classification (es. nomi prodotto
        # che sembrano nomi propri).
        doc = nlp(text)
        for ent in doc.ents:
            if ent.label_ != "PER":
                continue
            candidate = ent.text.strip()
            # Un nome di persona non attraversa un'interruzione di riga. Senza
            # questo vincolo lo span del NER inglobava il testo successivo, e
            # nel ciclo Cybersec endpoint produsse una voce di mappa che
            # partiva da "Bitdefender Gravityzone" e proseguiva su tre righe di
            # residui del template: una sostituzione cosi' e' insieme inutile e
            # dannosa, perche' aggancia testo che non e' un nome.
            if "\n" in candidate or "\r" in candidate:
                continue
            tokens = candidate.split()
            if len(tokens) < 2:
                continue  # nomi singoli ambigui (PER + iniziale isolata, troppo rischioso)
            if tokens[0] in ITALIAN_STOPWORDS:
                continue
            if any(w in company_substrings for w in tokens):
                continue
            if any(t.lower() in _TECH_BRAND_LOWER for t in tokens):
                continue
            results["PROPER_NOUN"].append(candidate)
    else:
        # Fallback regex+stoplist quando spaCy/modello non disponibili.
        # Sub-ottimale: produce falsi positivi su frasi tecniche a due parole
        # (es. "Restore Point", "Media Feature Pack"). Vedi diario C.8.
        for m in PROPER_NOUN_RE.finditer(text):
            candidate = m.group(1).strip()
            tokens = candidate.split()
            first_word = tokens[0]
            if first_word in ITALIAN_STOPWORDS:
                continue
            if any(w in company_substrings for w in tokens):
                continue
            if any(t in TECH_BRAND_STOPWORDS for t in tokens):
                continue
            if len(tokens) >= 2:
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
