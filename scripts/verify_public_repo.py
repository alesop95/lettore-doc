#!/usr/bin/env python3
"""
verify_public_repo.py - Verifica di riservatezza sul repository pubblico.

Cerca nel repo pubblico, nell'albero di lavoro e opzionalmente in ogni commit
della storia, tutto cio' che non deve esserci: segreti, indirizzi di rete,
indirizzi di posta, hostname, nomi di persona, clienti terzi, sottodomini di
fornitori, e le intestazioni spurie prodotte da un preview mal formato.

Perche' esiste come script e non come procedura scritta. La sola fuga vera della
storia del progetto e' stata trovata a mano, cercando le stringhe sensibili nel
diff prima del commit, e le tre password pubblicate sono rimaste invisibili per
mesi perche' quella ricerca manuale dipendeva dal ricordarsi di farla e dal
sapere cosa cercare. Un controllo che vive nella memoria dell'operatore non e' un
controllo. Questo script lo rende eseguibile, ripetibile e capace di fallire con
un codice di uscita, quindi utilizzabile come cancello prima di un commit.

I pattern NON sono duplicati qui: si importano da `sanitize_taxonomy_diff.py`,
che e' il gate della pipeline. La ragione e' che un verificatore con una propria
copia delle regole diverge dal gate al primo aggiornamento, e a quel punto dice
che va tutto bene misurando qualcosa di diverso da cio' che il gate impedisce.
L'unica categoria che questo script costruisce da se' sono i nomi di persona,
che si derivano dalle `anonymization_map` dei corpora lavorati in locale: sono la
lista piu' completa di quali persone il sistema ha incontrato, e non vanno
scritte a mano in un file versionato.

Uso:
  python scripts/verify_public_repo.py                      # albero di lavoro
  python scripts/verify_public_repo.py --history            # anche ogni commit
  python scripts/verify_public_repo.py --staged             # solo quanto in stage

Codici di uscita: 0 pulito, 2 trovati riscontri, 1 errore d'uso.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sanitize_taxonomy_diff import (  # noqa: E402
    LEAK_PATTERNS,
    SECRET_PATTERNS,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
INTERMEDIATE = REPO_ROOT / "_intermediate"

TEXT_SUFFIXES = {".md", ".yml", ".yaml", ".html", ".txt", ".json"}

# Riscontri che sono strutturalmente falsi positivi e non vanno segnalati, per
# non abituare chi legge a ignorare l'output. Localhost non identifica nulla; la
# posta e il nome del proprietario del profilo sono dichiarati volutamente, come
# la ragione sociale, secondo la decisione del 2026-07-28.
ALLOWED_LITERALS = {
    "127.0.0.1",
    "0.0.0.0",
    "255.255.255.0",
    # Identita' e contatti del proprietario del profilo, dichiarati di proposito
    # nel sito e nel mkdocs.yml. Trattarli come fuga non protegge nessuno e
    # riempie l'output, che e' il modo piu' rapido di rendere inutile un
    # controllo automatico.
    "alessio.sopranzi.95@gmail.com",
    "www.linkedin.com",
    "linkedin.com",
}

# Contesti in cui una corrispondenza e' spiegata e non va segnalata. Si
# confrontano sul testo del riscontro, non sul file, cosi' la spiegazione vale
# dove ricorre e non silenzia un intero file.
BENIGN_CONTEXTS = (
    re.compile(r"^Token cost\s*:", re.I),      # report di graphify: costo in token
    re.compile(r"^token\s*:\s*(?:read|write|none)\b", re.I),  # permessi Actions
)

# Nome proprio del titolare del profilo: e' il soggetto della tassonomia, quindi
# la sua presenza non e' una fuga. Si tiene separato da NON_NAMES perche' la
# ragione e' diversa, e perche' su un'altra macchina va cambiato.
DECLARED_IDENTITY = {"Alessio", "Sopranzi"}

# Parole che il riconoscitore di entita' produce come falsi nomi di persona su
# testo inglese. Restano fuori dalla lista dei termini da cercare, altrimenti
# l'audit segnala le licenze dei pacchetti e il rumore sommerge il segnale.
NON_NAMES = {
    "should", "these", "with", "task", "blocks", "server", "print", "client",
    "system", "windows", "service", "network", "domain", "domini", "backup",
    "cloud", "office", "master", "power", "store", "level", "group", "admin",
    "user", "local", "mail", "host", "disk", "data", "test", "line", "port",
    "link", "file", "case", "team", "room", "read", "only", "offline",
    "periodo", "trados", "studio", "enterprise", "manager", "license",
    "project", "aruba", "seeweb", "fastnet", "vianova",
    # Parole italiane comuni che il NER estrae come nomi propri quando trova
    # una coppia "Nome Cognome" dove uno dei due e' un sostantivo. Il ciclo
    # Helpdesk_T-Rex ha reso evidente il caso: "Procedura Reso" catturata come
    # persona ha portato "Procedura" nella regex nome-persona e generato quattro
    # falsi positivi sui documenti di IT tecnica.
    "procedura", "reso", "storno", "cambio", "anno", "ordine", "fattura",
    "fatture", "sequenze", "sequenza", "tabella", "pagina", "codice", "codici",
    "magazzino", "progetto", "progetti", "marca", "marche", "bollo", "bolli",
    "lavori", "vendite", "acquisti", "revisione", "traduzione", "preventivo",
    "preventivi", "trasferimento", "impostazioni",
}

STRUCTURAL_PATTERNS = {
    # Un preview appiattito che comincia con dei cancelletti diventa una vera
    # intestazione dentro la sezione delle evidenze, e le intestazioni sono i
    # confini su cui la pipeline delimita i blocchi. Il segnale non e' una parola
    # chiave qualsiasi, altrimenti si segnalano le intestazioni legittime delle
    # evidenze che parlano di password: e' la presenza in una intestazione di un
    # marcatore di prosa, cioe' di frase narrativa la' dove ci vuole
    # un'etichetta.
    # Nota sul confine finale: non si chiude con \b, perche' l'alternativa che
    # termina con una cifra lo rende insoddisfacibile in mezzo a una data come
    # 15/11/2024, e il pattern smetteva di trovare anche i due casi veri.
    "struttura-intestazione-iniettata": re.compile(
        r"^#{1,6}\s+.*\b(?:In data\s+\d|Please complete|si e' scritto|"
        r"e' stato creato|In alternativa dal)",
        re.MULTILINE | re.IGNORECASE,
    ),
    # Residuo dello scrub che taglia una parola a meta', per esempio
    # "[RIMOSSO]rmatica": lascia leggibile una parte di cio' che doveva sparire.
    "struttura-scrub-parziale": re.compile(r"\[RIMOSSO\][a-z]{2,}"),
}


def derive_person_terms() -> set[str]:
    """
    Costruisce i termini di persona dalle mappe di anonimizzazione locali.

    Si prendono solo le voci che sono esattamente due parole alfabetiche con
    l'iniziale maiuscola, cioe' la forma di un nome proprio pulito, e da esse
    anche i singoli token, perche' la fuga tipica e' il cognome nudo o il nome di
    battesimo. Le voci sporche prodotte da uno span troppo largo del
    riconoscitore, che contengono trattini, cifre o parole comuni, sono escluse:
    i loro token danneggerebbero il segnale.
    """
    terms: set[str] = set()
    if not INTERMEDIATE.exists():
        return terms
    for path in sorted(INTERMEDIATE.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        amap = {}
        if isinstance(data, dict):
            amap = data.get("anonymization_map") or data.get("graph", {}).get(
                "anonymization_map", {}
            ) or {}
        if not isinstance(amap, dict):
            continue
        for original, placeholder in amap.items():
            if not isinstance(placeholder, str) or not placeholder.startswith("[PERSONA_"):
                continue
            parts = original.split()
            if len(parts) != 2:
                continue
            if not all(t.isalpha() and t[:1].isupper() for t in parts):
                continue
            if any(t.lower() in NON_NAMES for t in parts):
                continue
            if any(t in DECLARED_IDENTITY for t in parts):
                continue
            terms.add(original)
            for tok in parts:
                if (len(tok) >= 4
                        and tok.lower() not in NON_NAMES
                        and tok not in DECLARED_IDENTITY):
                    terms.add(tok)
    return terms


def build_categories() -> dict[str, re.Pattern]:
    """
    Compone le categorie di ricerca: i pattern del gate, quelli strutturali, e
    quello sui nomi di persona derivato dalle mappe.
    """
    categories: dict[str, re.Pattern] = {}
    categories.update({f"segreto:{k}": v for k, v in SECRET_PATTERNS.items()})
    categories.update(LEAK_PATTERNS)
    categories.update(STRUCTURAL_PATTERNS)

    terms = derive_person_terms()
    if terms:
        alt = "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True))
        categories["nome-persona"] = re.compile(rf"\b(?:{alt})\b")
    return categories


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return proc.stdout


def scan_text(text: str, categories: dict[str, re.Pattern]) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for name, rx in categories.items():
        hits = set()
        for m in rx.findall(text):
            value = m if isinstance(m, str) else next((g for g in m if g), "")
            value = value.strip()
            if not value or value in ALLOWED_LITERALS:
                continue
            if any(rx.search(value) for rx in BENIGN_CONTEXTS):
                continue
            hits.add(value[:80])
        if hits:
            found[name] = hits
    return found


def resolve_repo(cli_value: str | None) -> Path:
    raw = cli_value or os.environ.get("LETTERDOC_SKILLS_REPO", "")
    if not raw:
        print(
            "ERRORE: indicare il repo con --skills-repo oppure impostare "
            "LETTERDOC_SKILLS_REPO.",
            file=sys.stderr,
        )
        sys.exit(1)
    return Path(os.path.expandvars(raw)).resolve()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verifica di riservatezza sul repository pubblico."
    )
    parser.add_argument("--skills-repo", help="Path al repo pubblico "
                                             "(default: LETTERDOC_SKILLS_REPO)")
    parser.add_argument("--history", action="store_true",
                        help="Analizza anche ogni commit della storia, non solo "
                             "l'albero di lavoro. Piu' lento e necessario prima "
                             "di dichiarare bonificato un repository.")
    parser.add_argument("--staged", action="store_true",
                        help="Analizza solo il contenuto in stage: e' la forma "
                             "adatta a un hook di pre-commit.")
    parser.add_argument("--quiet", action="store_true",
                        help="Stampa solo il verdetto e i conteggi.")
    args = parser.parse_args()

    repo = resolve_repo(args.skills_repo)
    if not repo.exists():
        print(f"ERRORE: repo non trovato: {repo}", file=sys.stderr)
        sys.exit(1)

    categories = build_categories()
    n_person = 1 if "nome-persona" in categories else 0

    print(f"=== verify_public_repo ===", file=sys.stderr)
    print(f"repo:      {repo}", file=sys.stderr)
    print(f"categorie: {len(categories)} "
          f"({len(SECRET_PATTERNS)} segreto, {len(LEAK_PATTERNS)} residuo, "
          f"{len(STRUCTURAL_PATTERNS)} struttura, {n_person} nomi)", file=sys.stderr)
    print("", file=sys.stderr)

    total_findings = 0

    # ---- Albero di lavoro o stage ----------------------------------------
    if args.staged:
        files = [f for f in git(repo, "diff", "--cached", "--name-only").splitlines() if f]
        scope = "STAGE"
    else:
        files = [f for f in git(repo, "ls-files").splitlines() if f]
        scope = "ALBERO DI LAVORO"

    print(f"--- {scope}: {len(files)} file tracciati ---", file=sys.stderr)
    tree_findings: dict[str, dict[str, set[str]]] = {}
    for rel in sorted(files):
        path = repo / rel
        if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        found = scan_text(text, categories)
        if found:
            tree_findings[rel] = found

    if tree_findings:
        for rel, cats in sorted(tree_findings.items()):
            print(f"\n  {rel}", file=sys.stderr)
            for cat, hits in sorted(cats.items()):
                total_findings += len(hits)
                shown = sorted(hits)[:6] if not args.quiet else []
                suffix = f"  {shown}" if shown else f"  ({len(hits)})"
                print(f"     {cat:34s}{suffix}", file=sys.stderr)
    else:
        print("  pulito", file=sys.stderr)

    # ---- Storia -----------------------------------------------------------
    if args.history:
        commits = [c for c in git(repo, "rev-list", "--all").splitlines() if c]
        print(f"\n--- STORIA: {len(commits)} commit ---", file=sys.stderr)
        blobs: dict[str, str] = {}
        for sha in commits:
            for line in git(repo, "ls-tree", "-r", "--long", sha).splitlines():
                parts = line.split(None, 4)
                if len(parts) < 5:
                    continue
                blob, path_str = parts[2], parts[4].strip()
                if Path(path_str).suffix.lower() not in TEXT_SUFFIXES:
                    continue
                blobs.setdefault(blob, path_str)

        hist: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        for blob, path_str in blobs.items():
            found = scan_text(git(repo, "cat-file", "-p", blob), categories)
            for cat, hits in found.items():
                hist[path_str][cat] |= hits

        if hist:
            for path_str, cats in sorted(hist.items()):
                print(f"\n  {path_str}", file=sys.stderr)
                for cat, hits in sorted(cats.items()):
                    total_findings += len(hits)
                    shown = sorted(hits)[:6] if not args.quiet else []
                    suffix = f"  {shown}" if shown else f"  ({len(hits)})"
                    print(f"     {cat:34s}{suffix}", file=sys.stderr)
            print(f"\n  blob di testo distinti analizzati: {len(blobs)}", file=sys.stderr)
        else:
            print("  storia pulita", file=sys.stderr)

    print("", file=sys.stderr)
    if total_findings:
        print(f"ESITO: {total_findings} riscontri. NON committare finche' non "
              f"sono spiegati o rimossi.", file=sys.stderr)
        sys.exit(2)
    print("ESITO: pulito.", file=sys.stderr)


if __name__ == "__main__":
    main()
