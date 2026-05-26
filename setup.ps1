<#
.SYNOPSIS
    Crea un ambiente Python virtuale (.venv) locale alla cartella del progetto
    e installa le dipendenze al suo interno.

.DESCRIPTION
    Il venv vive in .\.venv\ ed e completamente isolato dal Python di sistema.
    Spostare la cartella, cambiare PC, reinstallare Windows: il venv si ricrea
    rilanciando questo script. Non altera PATH, registro, o altri Python esistenti.

.PARAMETER Force
    Ricrea il venv da zero anche se esiste gia.

.PARAMETER PythonPath
    Forza l'uso di un Python specifico (es. "C:\Python312\python.exe").
    Se omesso, lo script cerca "python" e poi "py" nel PATH.

.EXAMPLE
    .\setup.ps1
    Setup standard: crea .venv se non esiste, installa le dipendenze.

.EXAMPLE
    .\setup.ps1 -Force
    Cancella .venv esistente e ricrea tutto da zero.
#>

param(
    [switch]$Force,
    [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$venvDir = Join-Path $PSScriptRoot ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

Write-Host "=== Setup ambiente Python isolato ===" -ForegroundColor Cyan
Write-Host "Cartella progetto: $PSScriptRoot"
Write-Host "Cartella venv:     $venvDir"
Write-Host ""

# Verifica Python disponibile
function Find-Python {
    param([string]$Override)
    if ($Override) {
        if (Test-Path -LiteralPath $Override) { return $Override }
        Write-Error "Python specificato non trovato: $Override"
        exit 1
    }
    foreach ($cmd in @("python", "py")) {
        $found = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($found) {
            $version = & $cmd --version 2>&1
            if ($version -match "Python\s+(\d+)\.(\d+)") {
                $major = [int]$Matches[1]; $minor = [int]$Matches[2]
                if ($major -ge 3 -and $minor -ge 10) {
                    return $found.Source
                }
            }
        }
    }
    Write-Error "Python 3.10+ non trovato. Installa da https://www.python.org/ (spunta 'Add Python to PATH')."
    exit 1
}

$systemPython = Find-Python -Override $PythonPath
$systemVersion = & $systemPython --version 2>&1
Write-Host "Python di sistema trovato: $systemPython ($systemVersion)" -ForegroundColor Green

# Gestione venv esistente
if (Test-Path -LiteralPath $venvDir) {
    if ($Force) {
        Write-Host "Cancello .venv esistente (-Force)..." -ForegroundColor Yellow
        Remove-Item -LiteralPath $venvDir -Recurse -Force
    } else {
        Write-Host ".venv esistente trovato, lo riutilizzo. Per ricrearlo: .\setup.ps1 -Force" -ForegroundColor Yellow
    }
}

# Crea venv se non esiste
if (-not (Test-Path -LiteralPath $venvDir)) {
    Write-Host "Creo l'ambiente virtuale..." -ForegroundColor Yellow
    & $systemPython -m venv $venvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Creazione venv fallita."
        exit 1
    }
    Write-Host "Ambiente virtuale creato in $venvDir" -ForegroundColor Green
}

# Aggiorna pip e installa dipendenze nel venv
Write-Host ""
Write-Host "Aggiorno pip nel venv..." -ForegroundColor Yellow
& $venvPython -m pip install --upgrade pip --quiet
if ($LASTEXITCODE -ne 0) { Write-Error "Aggiornamento pip fallito."; exit 1 }

Write-Host "Installo le dipendenze da requirements.txt..." -ForegroundColor Yellow
& $venvPython -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { Write-Error "Installazione dipendenze fallita."; exit 1 }

# Verifica
Write-Host ""
Write-Host "Verifica installazione..." -ForegroundColor Yellow
& $venvPython -c "from docx import Document; print('python-docx OK')"
if ($LASTEXITCODE -ne 0) { Write-Error "Verifica python-docx fallita."; exit 1 }

Write-Host ""
Write-Host "=== Setup completato ===" -ForegroundColor Green
Write-Host ""
Write-Host "Prossimo passo:"
Write-Host "  .\run_pipeline.ps1 -SourceFolder `"<percorso cartella docx>`""
Write-Host ""
Write-Host "L'ambiente virtuale e contenuto in .\.venv\ e non interferisce con altri"
Write-Host "Python sul sistema. Per usare il venv manualmente (debug):"
Write-Host "  .\.venv\Scripts\Activate.ps1     (attiva nella sessione corrente)"
Write-Host "  deactivate                       (per disattivare)"
