#!/usr/bin/env python3
"""
prepare_graphify_source.py - Prepara una subfolder sorgente per graphify.

graphify scarta i file il cui NOME contiene termini che sembrano segreti
(`password`, `credential`, `secret`, `token`, `private_key`, estensioni di
chiave) oppure che stanno sotto una directory di segreti nota. Il filtro guarda
solo il nome, mai il contenuto, quindi una policy IT aziendale intitolata
"Configurazione-password-Windows.docx" viene esclusa dal grafo pur essendo
esattamente il materiale che si vuole indicizzare. In teoria lo scarto sarebbe
osservabile, perche' `detect` restituisce un campo `skipped_sensitive`; nel
ciclo Cybersec del 2026-07-16 quel campo e' pero' risultato vuoto, perche' si
popola in un loop a valle di un pre-detect che aveva gia' concluso
`total_files: 0`. La sessione ha quindi deciso `needs_graph: false` senza
eseguire alcuna analisi, e i documenti sono spariti dal corpus senza segnale.

Questo script fa due cose. In modalita' di sola verifica (default) elenca quali
file di una subfolder graphify scarterebbe e perche'. In modalita' `--apply`
produce accanto alla subfolder una cartella `<nome>-sanitized/` con gli stessi
documenti convertiti in Markdown e con i soli NOMI neutralizzati secondo una
mappa esplicita. Il contenuto non viene toccato: l'anonimizzazione dei dati
sensibili e' un altro problema, e la risolvono `enrich_graph.py` e
`sanitize_taxonomy_diff.py` piu' a valle.

Uso:
  # cosa scarterebbe graphify, senza scrivere nulla
  python scripts/prepare_graphify_source.py --folder "_intermediate/src/<nome>"

  # genera la cartella -sanitized/ pronta per /graphify
  python scripts/prepare_graphify_source.py --folder "_intermediate/src/<nome>" --apply
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_docx import parse_single_docx  # noqa: E402


# ---------------------------------------------------------------------------
# Specchio del filtro di graphify
#
# Copiati da graphify.detect (_SENSITIVE_DIRS, _SENSITIVE_PATTERNS) alla
# versione 0.8.14. Sono duplicati e non importati perche' graphify vive in un
# virtualenv separato (pipx) che questo script non ha motivo di caricare, e
# perche' un cambio di quelle regole a monte deve rompere qui in modo visibile
# invece di cambiare silenziosamente il comportamento della pipeline. Se un
# giorno il confronto non torna piu', la verifica e' rileggere quel modulo.
# ---------------------------------------------------------------------------
GRAPHIFY_VERSION_MIRRORED = "0.8.14"

SENSITIVE_DIRS = frozenset({
    ".ssh", ".gnupg", ".aws", ".gcloud", "secrets", ".secrets", "credentials",
})

SENSITIVE_PATTERNS = [
    re.compile(r'(^|[\\/])\.(env|envrc)(\.|$)', re.IGNORECASE),
    re.compile(r'\.(pem|key|p12|pfx|cert|crt|der|p8)$', re.IGNORECASE),
    re.compile(r'(?<![a-zA-Z0-9])(credential|secret|passwd|password|private_key)s?(?![a-zA-Z])', re.IGNORECASE),
    re.compile(r'(?<![a-zA-Z0-9])tokens?(?![a-zA-Z])', re.IGNORECASE),
    re.compile(r'(id_rsa|id_dsa|id_ecdsa|id_ed25519)(\.pub)?$'),
    re.compile(r'(\.netrc|\.pgpass|\.htpasswd)$', re.IGNORECASE),
    re.compile(r'(aws_credentials|gcloud_credentials|service.account)', re.IGNORECASE),
]

# Estensioni che indicano un vero materiale crittografico: qui il filtro di
# graphify ha ragione e non si rinomina nulla, si segnala e si esclude.
KEY_MATERIAL_SUFFIXES = {
    ".pem", ".key", ".p12", ".pfx", ".cert", ".crt", ".der", ".p8",
    ".netrc", ".pgpass", ".htpasswd",
}

# Documenti che la pipeline sa leggere.
DOC_SUFFIXES = {".docx", ".md", ".txt"}


# ---------------------------------------------------------------------------
# Mappa di neutralizzazione dei nomi
#
# Sostituzioni in italiano perche' il corpus e' italiano, scelte in modo che il
# nome resti leggibile e descriva ancora il documento. Non e' un offuscamento:
# il file resta riconoscibile a un umano, cambia solo il termine che accende il
# filtro a monte.
# ---------------------------------------------------------------------------
NAME_SUBSTITUTIONS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'private[_-]?keys?', re.IGNORECASE), "chiave-privata"),
    (re.compile(r'passwords?', re.IGNORECASE),        "autenticazione"),
    (re.compile(r'passwd', re.IGNORECASE),            "autenticazione"),
    (re.compile(r'credentials?', re.IGNORECASE),      "accesso"),
    (re.compile(r'secrets?', re.IGNORECASE),          "riservato"),
    (re.compile(r'tokens?', re.IGNORECASE),           "chiave"),
]


def is_sensitive_name(path: Path) -> bool:
    """Replica `graphify.detect._is_sensitive`: directory note, poi nome file."""
    if any(part in SENSITIVE_DIRS for part in path.parts[:-1]):
        return True
    return any(p.search(path.name) for p in SENSITIVE_PATTERNS)


def sanitize_stem(stem: str) -> str:
    """Applica la mappa di neutralizzazione allo stem di un nome file."""
    for pattern, replacement in NAME_SUBSTITUTIONS:
        stem = pattern.sub(replacement, stem)
    return stem


def docx_to_markdown(path: Path, base_dir: Path) -> str:
    """
    Converte un .docx in Markdown riusando il parser della pipeline.

    Il corpo non viene alterato: titoli di sezione, paragrafi e tabelle passano
    cosi' come sono. L'unico titolo che cambia e' l'H1, che viene derivato dal
    nome file gia' neutralizzato dal chiamante.
    """
    skeleton = parse_single_docx(path, base_dir, mode="full")
    if skeleton.error:
        raise RuntimeError(f"parse fallito su {path.name}: {skeleton.error}")

    parts: list[str] = []
    for section in skeleton.sections:
        title = (section.get("title") or "").strip()
        level = section.get("level") or 0
        # `parse_docx` apre sempre con una sezione sintetica di livello 0
        # ("Documento completo") che raccoglie il testo prima della prima
        # intestazione vera: non e' un heading del documento e non va emessa.
        # Le intestazioni reali scendono di un livello, cosi' l'unico H1 del
        # file resta il titolo derivato dal nome neutralizzato.
        if title and level >= 1:
            parts.append(f"{'#' * min(level + 1, 6)} {title}")
        for paragraph in section.get("paragraphs", []):
            if paragraph.strip():
                parts.append(paragraph.strip())
        for table in section.get("tables", []):
            if not table:
                continue
            headers = list(table[0].keys())
            parts.append("| " + " | ".join(headers) + " |")
            parts.append("| " + " | ".join("---" for _ in headers) + " |")
            for row in table:
                parts.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
    return "\n\n".join(parts)


def read_text_source(path: Path) -> str:
    """Legge un .md o .txt gia' testuale, senza toccarne il contenuto."""
    return path.read_text(encoding="utf-8", errors="replace")


def build_frontmatter(source_name: str, folder_name: str, profile: str) -> str:
    """Frontmatter di tracciabilita', nel formato gia' usato dal ciclo Cybersec."""
    return (
        "---\n"
        f"source_file: {source_name}\n"
        f"sanitized_from: {folder_name}\n"
        f"sanitized_at: {date.today().isoformat()}\n"
        f"profile: {profile}\n"
        "---\n"
    )


def collect(folder: Path) -> tuple[list[Path], list[Path], list[Path]]:
    """
    Ispeziona la subfolder e restituisce tre liste:
    documenti processabili, documenti che graphify scarterebbe per il nome,
    file di materiale crittografico da lasciare fuori del tutto.
    """
    ok: list[Path] = []
    renamed: list[Path] = []
    key_material: list[Path] = []

    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        # La cartella di output di graphify non e' materiale sorgente.
        if "graphify-out" in path.parts:
            continue
        if path.name.startswith("~$"):
            continue
        if path.suffix.lower() in KEY_MATERIAL_SUFFIXES:
            key_material.append(path)
            continue
        if path.suffix.lower() not in DOC_SUFFIXES:
            continue
        (renamed if is_sensitive_name(path) else ok).append(path)

    return ok, renamed, key_material


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--folder", required=True,
                        help="Subfolder sorgente da preparare.")
    parser.add_argument("--output", default=None,
                        help="Cartella di destinazione (default: <folder>-sanitized).")
    parser.add_argument("--profile", default="deep",
                        help="Etichetta di profilo scritta nel frontmatter (default: deep).")
    parser.add_argument("--apply", action="store_true",
                        help="Scrive davvero la cartella di output. Senza questo flag "
                             "lo script si limita a riportare cosa farebbe.")
    args = parser.parse_args()

    folder = Path(args.folder).resolve()
    if not folder.is_dir():
        print(f"ERRORE: non e' una cartella: {folder}", file=sys.stderr)
        sys.exit(1)

    output = Path(args.output).resolve() if args.output else folder.parent / f"{folder.name}-sanitized"

    ok, renamed, key_material = collect(folder)

    print(f"Subfolder : {folder}")
    print(f"Output    : {output}{'' if args.apply else '  (non scritto: manca --apply)'}")
    print(f"Filtro replicato da graphify {GRAPHIFY_VERSION_MIRRORED}")
    print()
    print(f"Documenti totali            : {len(ok) + len(renamed)}")
    print(f"  passano il filtro         : {len(ok)}")
    print(f"  graphify li scarterebbe   : {len(renamed)}")
    if key_material:
        print(f"  materiale crittografico   : {len(key_material)}  (esclusi, non rinominabili)")
    print()

    if renamed:
        print("Da rinominare (il filtro guarda il nome, non il contenuto):")
        for path in renamed:
            new_stem = sanitize_stem(path.stem)
            new_name = f"{new_stem}.md"
            still = is_sensitive_name(Path(new_name))
            flag = "  ATTENZIONE: match ancora attivo" if still else ""
            print(f"  {path.name}\n     -> {new_name}{flag}")
        print()

    if key_material:
        print("Esclusi come materiale crittografico:")
        for path in key_material:
            print(f"  {path.relative_to(folder)}")
        print()

    if not args.apply:
        print("Nessun file scritto. Rilanciare con --apply per generare la cartella.")
        return

    output.mkdir(parents=True, exist_ok=True)
    written = 0
    failures: list[tuple[Path, str]] = []

    for path in ok + renamed:
        new_stem = sanitize_stem(path.stem)
        target = output / f"{new_stem}.md"
        try:
            if path.suffix.lower() == ".docx":
                body = docx_to_markdown(path, folder)
            else:
                body = read_text_source(path)
        except Exception as exc:  # il ciclo non si ferma su un singolo documento
            failures.append((path, str(exc)))
            continue

        title = new_stem.replace("-", " ").replace("_", " ")
        content = (
            build_frontmatter(path.name, folder.name, args.profile)
            + "\n"
            + f"# {title}\n\n"
            + body.rstrip()
            + "\n"
        )
        target.write_text(content, encoding="utf-8")
        written += 1

    print(f"Scritti {written} file in {output}")
    if failures:
        print(f"\n{len(failures)} conversioni fallite:", file=sys.stderr)
        for path, msg in failures:
            print(f"  {path.name}: {msg}", file=sys.stderr)

    residual = [p.name for p in output.glob("*.md") if is_sensitive_name(p)]
    if residual:
        print(f"\nATTENZIONE: {len(residual)} file in output attivano ancora il "
              f"filtro di graphify:", file=sys.stderr)
        for name in residual:
            print(f"  {name}", file=sys.stderr)
        print("  Estendere NAME_SUBSTITUTIONS oppure rinominarli a mano.", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
