# open_diary.ps1
# Apre il diario tecnico in Microsoft Word e stampa a schermo la lista dei
# file di draft attualmente presenti nello scratchpad di sessione, cosi' che
# chi sta per editare il .docx sappia cosa incollare.
#
# Il diario e' il file `.docx` in root del progetto lettore-doc; il .md
# affiancato e' derivato e non va toccato a mano (vedi CLAUDE.md sezione
# "Sincronia diario .docx e .md").
#
# Esempi:
#   .\scripts\open_diary.ps1
#   .\scripts\open_diary.ps1 -Scratch "C:\altra\cartella\draft.md"
#
# Parametri:
#   -Diario  : path del .docx (default: quello del progetto).
#   -Scratch : opzionale, path di uno specifico file di draft da segnalare
#              esplicitamente; se omesso, elenca tutti i file .md della
#              cartella di scratchpad di sessione con "diario" nel nome.

param(
    [string]$Diario = "$PSScriptRoot\..\diario-tecnico-progetto (lettore-doc + skills-repo).docx",
    [string]$Scratch
)

$diarioResolved = (Resolve-Path -LiteralPath $Diario -ErrorAction SilentlyContinue).Path
if (-not $diarioResolved) {
    Write-Error "Diario non trovato: $Diario"
    exit 1
}

Write-Host ""
Write-Host "=== open_diary ===" -ForegroundColor Cyan
Write-Host "Diario   : $diarioResolved"

# Scratchpad di sessione: cartella indicata dall'agente in
# "Scratchpad Directory" del prompt di sessione. Non e' rilevabile in modo
# affidabile da PS senza intervento manuale; segnaliamo la convenzione e
# lasciamo che l'agente stampi al chiamante la path corrente all'inizio
# della sessione.
$scratchRoot = "$env:LOCALAPPDATA\Temp\claude"
Write-Host "Scratch  : $scratchRoot (cerca sotto E--lettore-doc\<session>\scratchpad\)"

if ($Scratch) {
    if (Test-Path -LiteralPath $Scratch) {
        Write-Host ""
        Write-Host "Draft indicato:" -ForegroundColor Yellow
        Write-Host "  $Scratch"
    } else {
        Write-Warning "Scratch indicato non trovato: $Scratch"
    }
} else {
    $drafts = Get-ChildItem -LiteralPath $scratchRoot -Recurse -File -Filter "*diario*.md" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 5
    if ($drafts) {
        Write-Host ""
        Write-Host "Draft di scratchpad (piu' recenti):" -ForegroundColor Yellow
        foreach ($d in $drafts) {
            Write-Host ("  {0}  ({1})" -f $d.FullName, $d.LastWriteTime.ToString("yyyy-MM-dd HH:mm"))
        }
    } else {
        Write-Host ""
        Write-Host "Nessun draft *diario*.md nello scratchpad." -ForegroundColor DarkGray
    }
}

Write-Host ""
Write-Host "Apro il diario in Microsoft Word..." -ForegroundColor Green
Write-Host "Passo successivo dopo salvataggio: .\scripts\finalize_diary.ps1" -ForegroundColor Green
Write-Host ""

Start-Process -FilePath $diarioResolved
