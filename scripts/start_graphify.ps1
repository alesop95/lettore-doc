# start_graphify.ps1
# Apre una sessione Claude Code dentro una subfolder sorgente con il modello
# forzato (di default Opus 4.7), pronta per eseguire `/graphify .`.
#
# Esempi:
#   .\scripts\start_graphify.ps1 -SourceFolder "$env:LETTERDOC_SOURCE_ONEDRIVE\Helpdesk_PC formatting"
#   .\scripts\start_graphify.ps1 -SourceFolder "..." -Account account2
#
# Parametri:
#   -SourceFolder : cartella sorgente su cui aprire la sessione.
#   -Model        : identificativo modello Claude (default claude-opus-4-7).
#   -Account      : nome account Claude Code, mappato a
#                   %USERPROFILE%\.claude-<Account>. Setta CLAUDE_CONFIG_DIR
#                   solo per il processo figlio, non a livello utente. Se
#                   omesso, la sessione eredita il default macchina (di solito
#                   quello del terminale corrente). Utile quando sulla stessa
#                   macchina convivono piu' account Claude Code.
#
# Note:
# - Il default progetto `lettore-doc/.claude/settings.json` imposta Opus 4.7
#   per le sessioni aperte nella root del progetto. Le sessioni aperte sulla
#   subfolder sorgente NON ereditano quel default (root di progetto diversa),
#   quindi qui lo passiamo esplicitamente via `--model`.
# - Se si passa -Account, verificare a priori che la skill graphify sia
#   effettivamente installata in quell'account: lo script controlla solo che
#   la directory di configurazione esista.

param(
    [Parameter(Mandatory=$true)][string]$SourceFolder,
    [string]$Model = "claude-opus-4-7",
    [string]$Account
)

if (-not (Test-Path $SourceFolder)) {
    Write-Error "SourceFolder non esiste: $SourceFolder"
    exit 1
}

$resolved = (Resolve-Path $SourceFolder).Path

$configDir = $null
if ($Account) {
    $configDir = Join-Path $env:USERPROFILE ".claude-$Account"
    if (-not (Test-Path $configDir)) {
        Write-Error "Account non trovato: '$Account' (atteso in $configDir)"
        exit 1
    }
    $env:CLAUDE_CONFIG_DIR = $configDir
}

Write-Host ""
Write-Host "=== start_graphify ===" -ForegroundColor Cyan
Write-Host "SourceFolder : $resolved"
Write-Host "Model        : $Model"
if ($Account) {
    Write-Host "Account      : $Account ($configDir)"
} else {
    Write-Host "Account      : (default macchina)"
}
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
