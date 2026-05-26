<#
.SYNOPSIS
    Esegue la pipeline di indicizzazione usando il Python del venv locale.

.DESCRIPTION
    Usa .\.venv\Scripts\python.exe per tutti i comandi. Non richiede
    l'attivazione del venv nella sessione corrente. Se .venv non esiste,
    rimanda all'esecuzione di setup.ps1.

.PARAMETER SourceFolder
    Cartella sorgente con i .docx.

.PARAMETER WorkDir
    Cartella per i file intermedi (default: .\_intermediate).

.PARAMETER VaultDir
    Cartella di output Obsidian (default: .\vault-output).

.PARAMETER Incremental
    Rielabora solo i .docx con hash diverso dalla volta precedente.

.PARAMETER OnlyVault
    Rigenera solo il vault, saltando parsing/entita/grafo.

.EXAMPLE
    .\run_pipeline.ps1 -SourceFolder "C:\Users\Utente\OneDrive - Intrawelt S.a.s\Documenti - IT"

.EXAMPLE
    .\run_pipeline.ps1 -SourceFolder "C:\...\Documenti - IT" -Incremental
#>

param(
    [Parameter(Mandatory=$true, HelpMessage="Percorso della cartella con i .docx")]
    [string]$SourceFolder,
    [string]$WorkDir = ".\_intermediate",
    [string]$VaultDir = ".\vault-output",
    [switch]$Incremental,
    [switch]$OnlyVault
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "Ambiente Python isolato non trovato (.\.venv non esiste)." -ForegroundColor Red
    Write-Host "Esegui prima:" -ForegroundColor Yellow
    Write-Host "  .\setup.ps1" -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path -LiteralPath $SourceFolder)) {
    Write-Error "Cartella sorgente non trovata: $SourceFolder"
    exit 1
}

Write-Host "=== Lettore Documentazione Intrawelt ===" -ForegroundColor Cyan
Write-Host "Python:   $venvPython"
Write-Host "Sorgente: $SourceFolder"
Write-Host "Lavoro:   $WorkDir"
Write-Host "Vault:    $VaultDir"
if ($Incremental) { Write-Host "Modalita: INCREMENTALE" -ForegroundColor Yellow }
if ($OnlyVault)   { Write-Host "Modalita: SOLO VAULT" -ForegroundColor Yellow }
Write-Host ""

New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
New-Item -ItemType Directory -Force -Path "$WorkDir\sections" | Out-Null
New-Item -ItemType Directory -Force -Path "$WorkDir\summaries" | Out-Null
New-Item -ItemType Directory -Force -Path $VaultDir | Out-Null

$structureJson = Join-Path $WorkDir "structure.json"
$entitiesJson = Join-Path $WorkDir "entities.json"
$graphJson = Join-Path $WorkDir "graph.json"

if (-not $OnlyVault) {
    Write-Host "[1/5] Parsing skeleton..." -ForegroundColor Yellow
    if ($Incremental) {
        & $venvPython scripts\parse_docx.py skeleton --input $SourceFolder --output $structureJson --incremental
    } else {
        & $venvPython scripts\parse_docx.py skeleton --input $SourceFolder --output $structureJson
    }
    if ($LASTEXITCODE -ne 0) { exit 1 }

    Write-Host "[2/5] Parsing sections-preview..." -ForegroundColor Yellow
    if ($Incremental) {
        & $venvPython scripts\parse_docx.py sections-preview --input $SourceFolder --output-dir "$WorkDir\sections" --incremental
    } else {
        & $venvPython scripts\parse_docx.py sections-preview --input $SourceFolder --output-dir "$WorkDir\sections"
    }
    if ($LASTEXITCODE -ne 0) { exit 1 }

    Write-Host "[3/5] Estrazione entita..." -ForegroundColor Yellow
    & $venvPython scripts\extract_entities.py --structure $structureJson --full-text "$WorkDir\sections" --output $entitiesJson
    if ($LASTEXITCODE -ne 0) { exit 1 }

    Write-Host "[4/5] Costruzione grafo..." -ForegroundColor Yellow
    & $venvPython scripts\build_knowledge_graph.py --structure $structureJson --entities $entitiesJson --output $graphJson
    if ($LASTEXITCODE -ne 0) { exit 1 }
} else {
    Write-Host "[1-4/5] Saltati (-OnlyVault)" -ForegroundColor DarkGray
}

Write-Host "[5/5] Generazione vault Obsidian..." -ForegroundColor Yellow
& $venvPython scripts\generate_vault.py `
    --graph $graphJson `
    --structure $structureJson `
    --entities $entitiesJson `
    --sections-dir "$WorkDir\sections" `
    --summaries-dir "$WorkDir\summaries" `
    --output $VaultDir
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host ""
Write-Host "=== Pipeline completata ===" -ForegroundColor Green
Write-Host "Vault disponibile in: $VaultDir"
Write-Host ""
Write-Host "Prossimi passi:"
Write-Host "  1. Apri '$VaultDir' come Vault in Obsidian (File -> Open folder as vault)"
Write-Host "  2. Per generare le sintesi narrative dei documenti, lancia Claude Code"
Write-Host "     da questa cartella e chiedi al subagente 'lettore-documentazione'"
Write-Host "     (vedi README.md sezione 'Sintesi narrative')."
Write-Host "  3. Dopo che le sintesi sono in '$WorkDir\summaries\', rilancia:"
Write-Host "       .\run_pipeline.ps1 -SourceFolder `"$SourceFolder`" -OnlyVault"
