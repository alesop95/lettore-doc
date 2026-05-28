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


def extract_capability_keywords(md_path: Path) -> tuple[list[str], str]:
    """
    Legge un .md di Capability e restituisce:
    - lista di keyword estratte da Technologies & tools + Overview
    - excerpt dell'Overview (prime 150 char)
    """
    if not md_path.exists():
        return [], ""

    text = md_path.read_text(encoding="utf-8", errors="replace")

    tech_section   = extract_section_text(text, "Technologies & tools")
    overview_section = extract_section_text(text, "Overview")

    combined = tech_section + " " + overview_section
    keywords = list(dict.fromkeys(tokenize_for_keywords(combined)))  # dedup preserving order

    overview_excerpt = overview_section[:150].split("\n")[0].strip()

    return keywords[:60], overview_excerpt


def parse_nav(nav: list, docs_dir: Path) -> list[dict]:
    """
    Parsa il nav di mkdocs e restituisce lista di domain dict.
    Ignora la Home entry.
    """
    domains = []

    for entry in nav:
        if not isinstance(entry, dict):
            continue
        for domain_name, children in entry.items():
            if domain_name == "Home":
                continue
            if not isinstance(children, list):
                continue

            capabilities = []
            for child in children:
                if not isinstance(child, dict):
                    continue
                for cap_name, cap_file in child.items():
                    if not isinstance(cap_file, str):
                        continue
                    # slug dal nome del file senza estensione e cartella
                    slug = Path(cap_file).stem
                    md_path = docs_dir / cap_file

                    keywords, overview_excerpt = extract_capability_keywords(md_path)

                    capabilities.append({
                        "name":             cap_name,
                        "slug":             slug,
                        "file":             cap_file,
                        "keywords":         keywords,
                        "overview_excerpt": overview_excerpt,
                    })

            domain_dir = capabilities[0]["file"].split("/")[0] if capabilities else ""
            domains.append({
                "name":            domain_name,
                "dir":             domain_dir,
                "domain_keywords": DOMAIN_BASE_KEYWORDS.get(domain_name, []),
                "capabilities":    capabilities,
            })

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


if __name__ == "__main__":
    main()
