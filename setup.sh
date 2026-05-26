#!/usr/bin/env bash
# setup.sh - Crea un ambiente Python virtuale (.venv) locale e installa le dipendenze.
#
# Funziona su Linux e macOS. Per Windows usa setup.ps1.
#
# Uso:
#   ./setup.sh              setup standard
#   ./setup.sh --force      ricrea il venv da zero
#   ./setup.sh --python /percorso/python3.12  usa un Python specifico

set -euo pipefail
cd "$(dirname "$0")"

FORCE=0
PYTHON_OVERRIDE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --force) FORCE=1; shift ;;
        --python) PYTHON_OVERRIDE="$2"; shift 2 ;;
        -h|--help)
            sed -n '2,12p' "$0"; exit 0 ;;
        *) echo "Opzione sconosciuta: $1" >&2; exit 1 ;;
    esac
done

VENV_DIR="$(pwd)/.venv"
VENV_PY="$VENV_DIR/bin/python"

echo "=== Setup ambiente Python isolato ==="
echo "Cartella progetto: $(pwd)"
echo "Cartella venv:     $VENV_DIR"
echo ""

# Trova Python 3.10+
find_python() {
    if [[ -n "$PYTHON_OVERRIDE" ]]; then
        if [[ ! -x "$PYTHON_OVERRIDE" ]]; then
            echo "ERRORE: Python specificato non eseguibile: $PYTHON_OVERRIDE" >&2
            exit 1
        fi
        echo "$PYTHON_OVERRIDE"; return
    fi
    for candidate in python3.13 python3.12 python3.11 python3.10 python3 python; do
        if command -v "$candidate" >/dev/null 2>&1; then
            version=$("$candidate" --version 2>&1 | sed 's/Python //')
            major=$(echo "$version" | cut -d. -f1)
            minor=$(echo "$version" | cut -d. -f2)
            if [[ "$major" -ge 3 ]] && [[ "$minor" -ge 10 ]]; then
                echo "$candidate"; return
            fi
        fi
    done
    echo "ERRORE: Python 3.10+ non trovato nel PATH." >&2
    echo "Installa Python 3.10 o successivo (https://www.python.org/ o gestore pacchetti)." >&2
    exit 1
}

SYSTEM_PYTHON=$(find_python)
SYSTEM_VERSION=$("$SYSTEM_PYTHON" --version 2>&1)
echo "Python di sistema trovato: $SYSTEM_PYTHON ($SYSTEM_VERSION)"

if [[ -d "$VENV_DIR" ]]; then
    if [[ "$FORCE" -eq 1 ]]; then
        echo "Cancello .venv esistente (--force)..."
        rm -rf "$VENV_DIR"
    else
        echo ".venv esistente trovato, lo riutilizzo. Per ricrearlo: ./setup.sh --force"
    fi
fi

if [[ ! -d "$VENV_DIR" ]]; then
    echo "Creo l'ambiente virtuale..."
    "$SYSTEM_PYTHON" -m venv "$VENV_DIR"
    echo "Ambiente virtuale creato in $VENV_DIR"
fi

echo ""
echo "Aggiorno pip nel venv..."
"$VENV_PY" -m pip install --upgrade pip --quiet

echo "Installo le dipendenze da requirements.txt..."
"$VENV_PY" -m pip install -r requirements.txt

echo ""
echo "Verifica installazione..."
"$VENV_PY" -c "from docx import Document; print('python-docx OK')"

echo ""
echo "=== Setup completato ==="
echo ""
echo "Prossimo passo:"
echo "  ./run_pipeline.sh --source \"<percorso cartella docx>\""
echo ""
echo "L'ambiente virtuale e in ./.venv/ e non interferisce con altri Python."
echo "Per usarlo manualmente (debug):"
echo "  source .venv/bin/activate    (attiva nella sessione corrente)"
echo "  deactivate                   (per disattivare)"
