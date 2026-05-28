# session_resume.ps1
# Stampa un digest dello stato di ingest corrente: per ogni subfolder
# tracciata mostra ultima data di ingest, commit associato sul skills-repo,
# e conteggio dei file unchanged/modified/new/deleted rispetto al disco.
#
# Da eseguire come prima azione quando si riprende il lavoro su lettore-doc
# in una nuova sessione Claude Code.
#
# Esempi:
#   .\scripts\session_resume.ps1
#   .\scripts\session_resume.ps1 -Folder "$env:LETTERDOC_SOURCE_ONEDRIVE\Helpdesk_PC formatting"

param(
    [string]$Folder
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Error "Python virtualenv non trovato: $python. Esegui setup.ps1."
    exit 1
}

if ($Folder) {
    & $python (Join-Path $repoRoot "scripts\ingest_state.py") status --folder $Folder
} else {
    & $python (Join-Path $repoRoot "scripts\ingest_state.py") status
}
