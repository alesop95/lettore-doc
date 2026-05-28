# start_graphify.ps1
# Apre una sessione Claude Code dentro una subfolder sorgente con il modello
# forzato (di default Opus 4.7), pronta per eseguire `/graphify .`.
#
# Esempio:
#   .\scripts\start_graphify.ps1 -SourceFolder "$env:LETTERDOC_SOURCE_ONEDRIVE\Helpdesk_PC formatting"
#
# Note:
# - Il default progetto `lettore-doc/.claude/settings.json` imposta Opus 4.7
#   per le sessioni aperte nella root del progetto. Le sessioni aperte sulla
#   subfolder sorgente NON ereditano quel default (root di progetto diversa),
#   quindi qui lo passiamo esplicitamente via `--model`.

param(
    [Parameter(Mandatory=$true)][string]$SourceFolder,
    [string]$Model = "claude-opus-4-7"
)

if (-not (Test-Path $SourceFolder)) {
    Write-Error "SourceFolder non esiste: $SourceFolder"
    exit 1
}

$resolved = (Resolve-Path $SourceFolder).Path

Write-Host ""
Write-Host "=== start_graphify ===" -ForegroundColor Cyan
Write-Host "SourceFolder : $resolved"
Write-Host "Model        : $Model"
Write-Host "Comando      : claude --model $Model"
Write-Host ""
Write-Host "Una volta dentro la sessione, esegui:" -ForegroundColor Yellow
Write-Host "  /graphify ."
Write-Host ""

Push-Location $resolved
try {
    claude --model $Model
}
finally {
    Pop-Location
}
