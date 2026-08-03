#!/usr/bin/env python3
"""
generate_taxonomy_index.py - Genera taxonomy_index.json dal mkdocs.yml di skills-repo.

Legge la struttura nav del mkdocs.yml, per ogni Capability page legge le sezioni
"Technologies & tools" e "Overview" ed estrae keyword significative.
Produce _intermediate/taxonomy_index.json usato da map_to_taxonomy.py.

Uso:
  python scripts/generate_taxonomy_index.py \\
    --skills-repo "J:\\googleDrive_sync\\Portfolio and ongoing studies\\Skills (EN)\\skills-repo" \\
    --output _intermediate/taxonomy_index.json
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERRORE: pyyaml non installato. Esegui: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Keyword per Domain (base, integrate con quelle estratte dai .md)
# ---------------------------------------------------------------------------
DOMAIN_BASE_KEYWORDS: dict[str, list[str]] = {
    "Infrastructure": [
        "infrastructure", "server", "network", "networking", "backup",
        "virtualization", "hypervisor", "storage", "hardware", "proxmox",
        "vmware", "esxi", "veeam", "qnap", "nas", "lan", "wan", "vlan",
        "firewall", "vpn", "switch", "router", "cluster", "ha",
    ],
    "Security": [
        "security", "cybersecurity", "encryption", "firewall", "antivirus",
        "edr", "protection", "authentication", "compliance", "gdpr",
        "bitlocker", "veracrypt", "bitdefender", "eset", "iso27001",
        "pentest", "vulnerability", "soc",
    ],
    "Cloud": [
        "cloud", "aws", "azure", "google", "saas", "serverless", "hosting",
        "seeweb", "s3", "iam", "lambda", "cloudflare", "cdn",
    ],
    "Software Engineering": [
        "software", "development", "programming", "code", "coding",
        "git", "github", "docker", "api", "database", "fullstack", "devops",
        "automation", "typescript", "javascript", "python", "react", "nextjs",
        "nodejs", "express", "prisma", "mysql", "postgresql", "rest", "crud",
        "branch", "merge", "push", "pull", "clone", "commit", "repository",
        "version", "control", "ssh", "vscode", "ide", "workflow",
        "fork", "rebase", "stash", "fetch", "remote", "upstream",
        "authentication", "credential", "token", "key", "deploy",
    ],
    "Data": [
        "data", "analytics", "reporting", "database", "sql", "bi",
        "excel", "powerquery", "dashboard", "statistics",
    ],
    "IT Operations": [
        "operations", "helpdesk", "support", "administration", "sysadmin",
        "monitoring", "windows", "office", "microsoft", "ninjaone", "rmm",
        "exchange", "sharepoint", "teams", "onedrive", "m365", "powershell",
        "linux", "ubuntu", "debian", "patch", "endpoint", "license",
    ],
    "Management": [
        "management", "leadership", "planning", "documentation", "quality",
        "strategy", "roadmap", "budget", "vendor", "procurement", "kpi",
        "project", "gantt", "wbs", "agile", "scrum", "kanban",
    ],
}

# Tetto di keyword per Capability. Esiste perche' `recall_score` in
# map_to_taxonomy.py normalizza sui token del nodo e non sul numero di keyword:
# a parita' di tutto il resto un set molto piu' grande degli altri puo' solo
# alzare il proprio punteggio, quindi una pagina patologicamente lunga finirebbe
# per attrarre evidenze che non le competono.
#
# Il valore era 60 e su cinque Capability su trentuno tagliava vocabolario
# discriminante: sulla pagina Cybersecurity & IT Governance faceva sparire
# `gdpr`, `penetration`, `testing` e `malware`, che sono esattamente i termini
# che la distinguono dalle vicine. Uno sweep a 60, 90, 120 e senza tetto sul
# corpus del ciclo Cybersec ha prodotto la stessa identica classificazione, cioe'
# il tetto non e' un parametro di tuning con effetto osservabile: e' solo una
# guardia. Portato quindi a 90, che sul nav attuale lascia intatte tutte le
# pagine tranne System Administration (94 token, ne perde 4).
MAX_KEYWORDS = 90

# Stopwords per keyword extraction
KEYWORD_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "in", "for", "to", "with",
    "on", "at", "by", "from", "is", "are", "was", "be", "been",
    "it", "its", "as", "use", "used", "using", "via", "see", "also",
    "this", "that", "all", "both", "each", "per", "such", "e", "le",
    "la", "di", "da", "su", "con", "per", "non", "una", "che", "del",
    "include", "includes", "including", "provides", "provide",
    "support", "supports", "setup", "management", "operations",
    "tools", "tools", "tool", "based", "based", "coverage", "system",
}


def tokenize_for_keywords(text: str) -> list[str]:
    """Estrae token significativi da un testo per costruire keyword set."""
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9\+\#\.]{2,}", text.lower())
    return [t for t in tokens if t not in KEYWORD_STOPWORDS and len(t) >= 3]


def extract_section_text(md_text: str, heading: str) -> str:
    """Estrae il testo di una sezione H2 da un file Markdown."""
    # Cerca ## heading (case-insensitive)
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$(.+?)(?=^##\s|\Z)",
        re.MULTILINE | re.IGNORECASE | re.DOTALL,
    )
    m = pattern.search(md_text)
    return m.group(1).strip() if m else ""


def _interleave_dedup(*token_lists: list[str]) -> list[str]:
    """
    Fonde piu' liste di token alternandole a giro (round-robin), deduplicando e
    preservando l'ordine di prima apparizione.

    Serve a rendere equo il taglio a MAX_KEYWORDS: una concatenazione semplice
    mette in coda la seconda sezione, e sulle pagine con una sezione lunga il
    taglio la elimina per intero.
    """
    merged: list[str] = []
    seen: set[str] = set()
    for i in range(max((len(lst) for lst in token_lists), default=0)):
        for lst in token_lists:
            if i < len(lst) and lst[i] not in seen:
                seen.add(lst[i])
                merged.append(lst[i])
    return merged


# Capability che non partecipano alla classificazione automatica, indicate per
# path relativo dentro docs/. Non e' un ripiego: sono pagine la cui evidenza non
# sta nei documenti aziendali. `soft/index.md` descrive competenze trasversali
# fondate su ruoli e percorsi personali, e nessun nodo estratto da una procedura
# IT ne e' evidenza.
#
# La storia di questa costante e' istruttiva. La pagina usciva a zero parole
# chiave per un difetto, cioe' non aveva le quattro intestazioni di contratto;
# portarla a contratto le ha dato novanta parole chiave, le piu' numerose della
# tassonomia, e la misura su due corpora diceva zero destinazioni cambiate. Sui
# due corpora non misurati la pagina ha invece cominciato a ricevere funzioni
# PowerShell, perche' con etichette di due token una sola sovrapposizione fa
# punteggio 0.5 e vince, e la pagina con piu' parole chiave e' quella con piu'
# probabilita' di sovrapporsi per caso. Lo zero era quindi il comportamento
# giusto raggiunto per la ragione sbagliata: qui diventa una scelta dichiarata.
MANUAL_ONLY_FILES = {"soft/index.md"}


def extract_capability_keywords(md_path: Path) -> tuple[list[str], str, int]:
    """
    Legge un .md di Capability e restituisce:
    - lista di keyword estratte da Overview + Technologies & tools, al massimo
      MAX_KEYWORDS, con le due sezioni alternate a giro
    - excerpt dell'Overview (prime 150 char)
    - numero di token scartati dal taglio a MAX_KEYWORDS (0 se nessuno)

    Le due sezioni si alternano invece di concatenarsi perche' il taglio finale
    non deve poter azzerare il contributo di una delle due. L'Overview apre il
    giro perche' e' la sezione che descrive il perimetro della Capability, ed e'
    quindi quella che porta i termini discriminanti.
    """
    if not md_path.exists():
        return [], "", 0

    text = md_path.read_text(encoding="utf-8", errors="replace")

    tech_section     = extract_section_text(text, "Technologies & tools")
    overview_section = extract_section_text(text, "Overview")

    overview_tokens = tokenize_for_keywords(overview_section)
    tech_tokens     = tokenize_for_keywords(tech_section)

    keywords = _interleave_dedup(overview_tokens, tech_tokens)
    dropped  = max(0, len(keywords) - MAX_KEYWORDS)

    overview_excerpt = overview_section[:150].split("\n")[0].strip()

    return keywords[:MAX_KEYWORDS], overview_excerpt, dropped


def _collect_leaves(children: list) -> list[tuple[str, str]]:
    """Ricorsivamente estrae tutte le foglie (cap_name, cap_file) sotto un nodo nav."""
    leaves: list[tuple[str, str]] = []
    for entry in children:
        if not isinstance(entry, dict):
            continue
        for name, value in entry.items():
            if isinstance(value, str):
                leaves.append((name, value))
            elif isinstance(value, list):
                leaves.extend(_collect_leaves(value))
    return leaves


def _build_domain(domain_name: str, leaves: list[tuple[str, str]], docs_dir: Path) -> dict:
    capabilities = []
    for cap_name, cap_file in leaves:
        slug = Path(cap_file).stem
        md_path = docs_dir / cap_file
        manual_only = Path(cap_file).as_posix() in MANUAL_ONLY_FILES
        if manual_only:
            keywords, overview_excerpt, dropped = [], "", 0
        else:
            keywords, overview_excerpt, dropped = extract_capability_keywords(md_path)
        capabilities.append({
            "name":             cap_name,
            "slug":             slug,
            "file":             cap_file,
            "keywords":         keywords,
            "overview_excerpt": overview_excerpt,
            "keywords_dropped": dropped,
            "manual_only":      manual_only,
        })
    # dir = cartella parent della prima capability, in stile POSIX per coerenza cross-OS
    domain_dir = ""
    if capabilities:
        parent = Path(capabilities[0]["file"]).parent
        parent_str = parent.as_posix()
        domain_dir = "" if parent_str == "." else parent_str
    return {
        "name":            domain_name,
        "dir":             domain_dir,
        "domain_keywords": DOMAIN_BASE_KEYWORDS.get(domain_name, []),
        "capabilities":    capabilities,
    }


def parse_nav(nav: list, docs_dir: Path) -> list[dict]:
    """
    Parsa il nav di mkdocs e restituisce lista di domain dict. Ignora la Home entry.

    Struttura nav supportata:
    - Top-level piatto (foglie dirette):
        - Soft Skills:
            - Overview: soft/index.md
      Il top-level diventa il domain.
    - Top-level con sotto-sezioni (Domain > SubArea > Capability):
        - Technical:
            - Infrastructure:
                - "Infrastructure & Virtualization": technical/infrastructure/xxx.md
                - ...
            - Security:
                - ...
      Ogni sotto-sezione (Infrastructure, Security, ...) diventa un domain.
      Le chiavi in DOMAIN_BASE_KEYWORDS sono allineate alle sotto-sezioni.
    - Caso misto (foglie dirette + sotto-sezioni sotto lo stesso top-level):
      il top-level diventa domain per le foglie dirette e ogni sotto-sezione
      diventa un domain separato.
    """
    domains = []

    for entry in nav:
        if not isinstance(entry, dict):
            continue
        for top_name, children in entry.items():
            if top_name == "Home":
                continue
            if not isinstance(children, list):
                continue

            direct_leaves: list[tuple[str, str]] = []
            subsections: list[tuple[str, list]] = []
            for child in children:
                if not isinstance(child, dict):
                    continue
                for name, value in child.items():
                    if isinstance(value, str):
                        direct_leaves.append((name, value))
                    elif isinstance(value, list):
                        subsections.append((name, value))

            if direct_leaves:
                domains.append(_build_domain(top_name, direct_leaves, docs_dir))
            for sub_name, sub_children in subsections:
                leaves = _collect_leaves(sub_children)
                if leaves:
                    domains.append(_build_domain(sub_name, leaves, docs_dir))

    return domains


def _resolve_skills_repo(cli_value):
    import os
    if cli_value:
        return Path(os.path.expandvars(cli_value)).resolve()
    sources_yml = Path(__file__).resolve().parent.parent / "sources.yml"
    if sources_yml.exists():
        try:
            import yaml as _yaml
            data = _yaml.safe_load(sources_yml.read_text(encoding="utf-8"))
            raw = data.get("skills_repo", "")
            if raw:
                expanded = os.path.expandvars(raw)
                if expanded and "${" not in expanded:
                    return Path(expanded).resolve()
        except Exception:
            pass
    env_val = os.environ.get("LETTERDOC_SKILLS_REPO", "")
    if env_val:
        return Path(env_val).resolve()
    print(
        "ERRORE: path di skills-repo non trovato.\n"
        "  1. Passa --skills-repo <path>\n"
        "  2. Setta skills_repo in sources.yml con variabile di ambiente\n"
        "  3. Setta LETTERDOC_SKILLS_REPO come variabile di ambiente",
        file=__import__("sys").stderr
    )
    __import__("sys").exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera taxonomy_index.json dal mkdocs.yml di skills-repo."
    )
    parser.add_argument(
        "--skills-repo", default=None,
        help=("Path al working tree di skills-repo. Se omesso, letto da "
              "sources.yml (skills_repo: key) o da LETTERDOC_SKILLS_REPO.")
    )
    parser.add_argument(
        "--output", required=True,
        help="Path output taxonomy_index.json"
    )
    args = parser.parse_args()

    skills_repo = _resolve_skills_repo(args.skills_repo)
    output_path = Path(args.output).resolve()

    mkdocs_yml = skills_repo / "mkdocs.yml"
    if not mkdocs_yml.exists():
        print(f"ERRORE: mkdocs.yml non trovato in {skills_repo}", file=sys.stderr)
        sys.exit(1)

    print(f"Leggo mkdocs.yml da {mkdocs_yml}", file=sys.stderr)
    config = yaml.safe_load(mkdocs_yml.read_text(encoding="utf-8"))
    nav = config.get("nav", [])

    # MkDocs Material usa docs/ come docs_dir di default
    docs_dir = skills_repo / "docs"
    if not docs_dir.exists():
        # Fallback: cerca i .md direttamente nella root
        docs_dir = skills_repo

    domains = parse_nav(nav, docs_dir)

    total_caps = sum(len(d["capabilities"]) for d in domains)
    print(f"Trovati {len(domains)} domain, {total_caps} Capability", file=sys.stderr)

    taxonomy_index = {
        "generated_at": datetime.now().isoformat(),
        "skills_repo":  str(skills_repo),
        "domains":      domains,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(taxonomy_index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Scritto: {output_path}", file=sys.stderr)

    # Riepilogo
    for domain in domains:
        caps = domain["capabilities"]
        kw_counts = [len(c["keywords"]) for c in caps]
        avg_kw = sum(kw_counts) / len(kw_counts) if kw_counts else 0
        print(f"  {domain['name']:25s}: {len(caps)} cap, {avg_kw:.0f} kw/cap in media",
              file=sys.stderr)

    # Il taglio a MAX_KEYWORDS non deve restare silenzioso: una Capability
    # troncata perde vocabolario discriminante e viene battuta nel matching da
    # Capability piu' povere che quel vocabolario lo conservano.
    truncated = [
        (d["name"], c["name"], c["keywords_dropped"])
        for d in domains
        for c in d["capabilities"]
        if c.get("keywords_dropped")
    ]
    if truncated:
        print(f"\nATTENZIONE: {len(truncated)} Capability troncate a "
              f"{MAX_KEYWORDS} keyword:", file=sys.stderr)
        for dom_name, cap_name, dropped in sorted(truncated, key=lambda t: -t[2]):
            print(f"  -{dropped:3d} token  {dom_name} / {cap_name}", file=sys.stderr)
        print("  Se una di queste risulta poi mal classificata, valutare se "
              "accorciare\n  le sezioni Overview e Technologies & tools della "
              "pagina, oppure alzare\n  MAX_KEYWORDS in modo uniforme.",
              file=sys.stderr)


if __name__ == "__main__":
    main()
