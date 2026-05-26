#!/usr/bin/env bash
# run_pipeline.sh - Esegue la pipeline usando il Python del venv locale.
# Equivalente di run_pipeline.ps1 per Linux/macOS.
#
# Uso:
#   ./run_pipeline.sh --source "<percorso cartella docx>"
#   ./run_pipeline.sh --source "<percorso>" --incremental
#   ./run_pipeline.sh --source "<percorso>" --only-vault

set -euo pipefail
cd "$(dirname "$0")"

VENV_PY="$(pwd)/.venv/bin/python"
SOURCE_FOLDER=""
WORK_DIR="./_intermediate"
VAULT_DIR="./vault-output"
INCREMENTAL=0
ONLY_VAULT=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --source) SOURCE_FOLDER="$2"; shift 2 ;;
        --work-dir) WORK_DIR="$2"; shift 2 ;;
        --vault-dir) VAULT_DIR="$2"; shift 2 ;;
        --incremental) INCREMENTAL=1; shift ;;
        --only-vault) ONLY_VAULT=1; shift ;;
        -h|--help)
            echo "Uso: $0 --source <cartella .docx> [--incremental] [--only-vault]"
            exit 0 ;;
        *) echo "Opzione sconosciuta: $1" >&2; exit 1 ;;
    esac
done

if [[ -z "$SOURCE_FOLDER" ]]; then
    echo "ERRORE: --source e obbligatorio." >&2
    echo "Uso: $0 --source \"<percorso cartella .docx>\"" >&2
    exit 1
fi

if [[ ! -x "$VENV_PY" ]]; then
    echo "Ambiente Python isolato non trovato (./.venv non esiste)." >&2
    echo "Esegui prima:  ./setup.sh" >&2
    exit 1
fi

if [[ ! -d "$SOURCE_FOLDER" ]]; then
    echo "ERRORE: cartella sorgente non trovata: $SOURCE_FOLDER" >&2
    exit 1
fi

echo "=== Lettore Documentazione Intrawelt ==="
echo "Python:   $VENV_PY"
echo "Sorgente: $SOURCE_FOLDER"
echo "Lavoro:   $WORK_DIR"
echo "Vault:    $VAULT_DIR"
[[ "$INCREMENTAL" -eq 1 ]] && echo "Modalita: INCREMENTALE"
[[ "$ONLY_VAULT" -eq 1 ]] && echo "Modalita: SOLO VAULT"
echo ""

mkdir -p "$WORK_DIR/sections" "$WORK_DIR/summaries" "$VAULT_DIR"

STRUCTURE_JSON="$WORK_DIR/structure.json"
ENTITIES_JSON="$WORK_DIR/entities.json"
GRAPH_JSON="$WORK_DIR/graph.json"

INC_FLAG=""
[[ "$INCREMENTAL" -eq 1 ]] && INC_FLAG="--incremental"

if [[ "$ONLY_VAULT" -eq 0 ]]; then
    echo "[1/5] Parsing skeleton..."
    "$VENV_PY" scripts/parse_docx.py skeleton --input "$SOURCE_FOLDER" --output "$STRUCTURE_JSON" $INC_FLAG

    echo "[2/5] Parsing sections-preview..."
    "$VENV_PY" scripts/parse_docx.py sections-preview --input "$SOURCE_FOLDER" --output-dir "$WORK_DIR/sections" $INC_FLAG

    echo "[3/5] Estrazione entita..."
    "$VENV_PY" scripts/extract_entities.py --structure "$STRUCTURE_JSON" --full-text "$WORK_DIR/sections" --output "$ENTITIES_JSON"

    echo "[4/5] Costruzione grafo..."
    "$VENV_PY" scripts/build_knowledge_graph.py --structure "$STRUCTURE_JSON" --entities "$ENTITIES_JSON" --output "$GRAPH_JSON"
else
    echo "[1-4/5] Saltati (--only-vault)"
fi

echo "[5/5] Generazione vault Obsidian..."
"$VENV_PY" scripts/generate_vault.py \
    --graph "$GRAPH_JSON" \
    --structure "$STRUCTURE_JSON" \
    --entities "$ENTITIES_JSON" \
    --sections-dir "$WORK_DIR/sections" \
    --summaries-dir "$WORK_DIR/summaries" \
    --output "$VAULT_DIR"

echo ""
echo "=== Pipeline completata ==="
echo "Vault disponibile in: $VAULT_DIR"
echo ""
echo "Prossimi passi:"
echo "  1. Apri '$VAULT_DIR' come Vault in Obsidian"
echo "  2. Per le sintesi narrative, lancia 'claude' da questa cartella"
echo "  3. Dopo: ./run_pipeline.sh --source \"$SOURCE_FOLDER\" --only-vault"
