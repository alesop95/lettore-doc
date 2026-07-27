# finalize_diary.ps1
# Dopo che il .docx del diario e' stato modificato in Word e salvato,
# questo script chiude il ciclo di sincronia:
#   1) rigenera il .md via sync_diary_md.py
#   2) mostra il git diff del .md per la review
#   3) stampa i comandi git per commit+push (manuali, per policy)
#
# Non committa e non pusha: la regola git-commands-format.md tiene git
# manuale dell'utente.
#
# Esempi:
#   .\scripts\finalize_diary.ps1
#   .\scripts\finalize_diary.ps1 -NoDiff   # salta il git diff
#
# Parametri:
#   -NoDiff : non mostrare il git diff dopo la rigenerazione.

param(
    [switch]$NoDiff
)

$root = Resolve-Path -LiteralPath "$PSScriptRoot\.."
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$syncScript = Join-Path $root "scripts\sync_diary_md.py"
$docx = Join-Path $root "diario-tecnico-progetto (lettore-doc + skills-repo).docx"
$md   = Join-Path $root "diario-tecnico-progetto (lettore-doc + skills-repo).md"

foreach ($p in @($venvPython, $syncScript, $docx)) {
    if (-not (Test-Path -LiteralPath $p)) {
        Write-Error "Manca: $p"
        exit 1
    }
}

Write-Host ""
Write-Host "=== finalize_diary ===" -ForegroundColor Cyan
Write-Host "Root     : $root"
Write-Host ""

Write-Host "[1/3] Rigenero il .md dal .docx..." -ForegroundColor Yellow
& $venvPython $syncScript
if ($LASTEXITCODE -ne 0) {
    Write-Error "sync_diary_md.py ha fallito (exit $LASTEXITCODE)."
    exit $LASTEXITCODE
}

Write-Host ""
if (-not $NoDiff) {
    Write-Host "[2/3] Git diff sul .md (review):" -ForegroundColor Yellow
    Push-Location $root
    try {
        git diff --stat -- "diario-tecnico-progetto (lettore-doc + skills-repo).md"
        Write-Host ""
        Write-Host "Diff completo (primi 200 righe):" -ForegroundColor DarkGray
        git --no-pager diff -- "diario-tecnico-progetto (lettore-doc + skills-repo).md" | Select-Object -First 200
    } finally {
        Pop-Location
    }
} else {
    Write-Host "[2/3] Diff saltato (-NoDiff)." -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "[3/3] Comandi git manuali per committare (regola git-commands-format.md):" -ForegroundColor Yellow
Write-Host ""
Write-Host '```powershell'
Write-Host 'git add "diario-tecnico-progetto (lettore-doc + skills-repo).docx" "diario-tecnico-progetto (lettore-doc + skills-repo).md" "diario-assets/"'
Write-Host 'git commit -m "Diario: <descrizione modifica>"'
Write-Host 'git push'
Write-Host '```'
Write-Host ""
Write-Host '```bash'
Write-Host 'git add "diario-tecnico-progetto (lettore-doc + skills-repo).docx" "diario-tecnico-progetto (lettore-doc + skills-repo).md" "diario-assets/"'
Write-Host 'git commit -m "Diario: <descrizione modifica>"'
Write-Host 'git push'
Write-Host '```'
Write-Host ""
