"""
ingest_state.py - Tracker dello stato di ingest per lettore-doc.

Mantiene _intermediate/ingest_state.json con uno snapshot sha256+mtime per file
di ciascuna subfolder sorgente che e' stata ingerita almeno una volta.
Permette di vedere, alla ripresa di una nuova sessione, quali file sono nuovi,
modificati, eliminati o invariati rispetto all'ultimo ciclo di ingest.

CLI:
    python scripts/ingest_state.py status
    python scripts/ingest_state.py status --folder "<path>"
    python scripts/ingest_state.py track --folder "<path>" --source ONEDRIVE [--commit <sha>]
    python scripts/ingest_state.py untrack --folder "<path>"

Lo state file e' la sorgente di verita' del progresso ingest, locale alla
macchina (vive in _intermediate/ che e' in .gitignore). Va aggiornato esattamente
una volta per ciclo, dopo l'apply al skills-repo. Non modificare a mano.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = REPO_ROOT / "_intermediate" / "ingest_state.json"

TEXT_EXTENSIONS = {".docx", ".txt", ".md"}
EXCLUDE_PREFIXES = ("~$",)
EXCLUDE_DIR_NAMES = {"_archive", "template", "templates"}

STATE_VERSION = 1


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"version": STATE_VERSION, "last_updated": None, "subfolders": {}}
    with STATE_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("version", STATE_VERSION)
    data.setdefault("last_updated", None)
    data.setdefault("subfolders", {})
    return data


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = now_iso()
    tmp = STATE_PATH.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    tmp.replace(STATE_PATH)


def normalize_folder_key(folder: Path) -> str:
    return str(folder.resolve()).replace("\\", "/")


def iter_text_files(folder: Path) -> Iterable[Path]:
    for root, dirnames, filenames in os.walk(folder):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIR_NAMES]
        for fn in filenames:
            if fn.startswith(EXCLUDE_PREFIXES):
                continue
            ext = Path(fn).suffix.lower()
            if ext not in TEXT_EXTENSIONS:
                continue
            yield Path(root) / fn


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot_folder(folder: Path) -> dict[str, dict]:
    files = {}
    for p in iter_text_files(folder):
        rel = p.relative_to(folder).as_posix()
        try:
            sha = sha256_of(p)
            mtime = dt.datetime.fromtimestamp(p.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except (OSError, PermissionError) as e:
            print(f"  WARN: skip {rel}: {e}", file=sys.stderr)
            continue
        files[rel] = {"sha256": sha, "mtime": mtime}
    return files


def diff_snapshot(old_files: dict, current_files: dict) -> dict[str, list[str]]:
    old_set = set(old_files.keys())
    cur_set = set(current_files.keys())

    new = sorted(cur_set - old_set)
    deleted = sorted(old_set - cur_set)
    common = old_set & cur_set
    modified = sorted(
        rel for rel in common
        if old_files[rel].get("sha256") != current_files[rel].get("sha256")
    )
    unchanged = sorted(common - set(modified))

    return {"new": new, "modified": modified, "deleted": deleted, "unchanged": unchanged}


def short_commit(sha: str | None) -> str:
    if not sha:
        return "-"
    return sha[:7]


def resolve_folder_arg(folder_arg: str) -> Path:
    p = Path(folder_arg).expanduser()
    if not p.is_absolute():
        cand = (REPO_ROOT / p).resolve()
        if cand.exists():
            p = cand
        else:
            p = p.resolve()
    return p


def cmd_status(args: argparse.Namespace) -> int:
    state = load_state()
    subs = state.get("subfolders", {})

    print(f"=== Ingest state - lettore-doc ===")
    print(f"Last updated: {state.get('last_updated') or '(mai aggiornato)'}")
    print(f"State file:   {STATE_PATH}")
    print()

    if not subs:
        print("Nessuna subfolder tracciata. Usa `ingest_state.py track --folder <PATH> --source <KEY>`.")
        return 0

    target_key = None
    if args.folder:
        target_key = normalize_folder_key(resolve_folder_arg(args.folder))

    any_printed = False
    for key, entry in sorted(subs.items()):
        if target_key and key != target_key:
            continue
        any_printed = True
        label = entry.get("label") or Path(key).name
        source = entry.get("source_root", "?")
        print(f"{label}  [{source}]")
        print(f"  path:        {entry.get('absolute_path', key)}")
        print(f"  last ingest: {entry.get('last_ingest_at') or '(mai)'} "
              f"(commit {short_commit(entry.get('last_ingest_commit'))})")

        folder = Path(entry.get("absolute_path", key))
        if not folder.exists():
            print(f"  STATO:       folder non trovata su disco")
            print()
            continue

        old_files = entry.get("files", {})
        cur_files = snapshot_folder(folder)
        diff = diff_snapshot(old_files, cur_files)

        print(f"  {len(diff['unchanged']):>4} unchanged   "
              f"{len(diff['modified']):>4} modified   "
              f"{len(diff['new']):>4} new   "
              f"{len(diff['deleted']):>4} deleted")

        if target_key:
            for tag, items in [("new", diff["new"]), ("modified", diff["modified"]), ("deleted", diff["deleted"])]:
                if items:
                    print(f"  --- {tag} ({len(items)}) ---")
                    for rel in items:
                        print(f"    {tag[0].upper()}  {rel}")
        print()

    if target_key and not any_printed:
        print(f"Subfolder non tracciata: {target_key}")
        print("Usa `ingest_state.py track` per registrarla.")
        return 1

    return 0


def cmd_track(args: argparse.Namespace) -> int:
    folder = resolve_folder_arg(args.folder)
    if not folder.exists():
        print(f"ERR: folder non esistente: {folder}", file=sys.stderr)
        return 2
    if not folder.is_dir():
        print(f"ERR: non e' una directory: {folder}", file=sys.stderr)
        return 2

    state = load_state()
    key = normalize_folder_key(folder)

    print(f"Scansione di {folder} ...")
    files = snapshot_folder(folder)
    print(f"  {len(files)} file di testo (docx/txt/md) registrati")

    existing = state["subfolders"].get(key, {})
    entry = {
        "label": folder.name,
        "source_root": args.source or existing.get("source_root", "UNKNOWN"),
        "absolute_path": str(folder),
        "last_ingest_at": now_iso(),
        "last_ingest_commit": args.commit or existing.get("last_ingest_commit"),
        "files": files,
    }
    state["subfolders"][key] = entry
    save_state(state)

    print(f"OK - state aggiornato in {STATE_PATH}")
    return 0


def cmd_untrack(args: argparse.Namespace) -> int:
    folder = resolve_folder_arg(args.folder)
    state = load_state()
    key = normalize_folder_key(folder)
    if key not in state.get("subfolders", {}):
        print(f"Subfolder non tracciata: {key}", file=sys.stderr)
        return 1
    del state["subfolders"][key]
    save_state(state)
    print(f"OK - {folder.name} rimossa dal tracking")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Tracker stato ingest per lettore-doc")
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="Mostra delta vs ultimo snapshot per ogni subfolder tracciata")
    p_status.add_argument("--folder", help="Filtra su una sola subfolder (mostra elenco esplicito dei file cambiati)")
    p_status.set_defaults(func=cmd_status)

    p_track = sub.add_parser("track", help="Registra/aggiorna lo snapshot di una subfolder")
    p_track.add_argument("--folder", required=True, help="Path della subfolder (assoluto o relativo al repo)")
    p_track.add_argument("--source", required=False, help="Label sorgente (es. ONEDRIVE, PORTFOLIO)")
    p_track.add_argument("--commit", required=False, help="Commit SHA del skills-repo associato a questo ingest")
    p_track.set_defaults(func=cmd_track)

    p_untrack = sub.add_parser("untrack", help="Rimuove una subfolder dal tracking")
    p_untrack.add_argument("--folder", required=True, help="Path della subfolder")
    p_untrack.set_defaults(func=cmd_untrack)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
