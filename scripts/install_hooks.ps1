# install_hooks.ps1 - Installa gli hook git nel repository pubblico.
#
# Gli hook vivono in .git/hooks/, che non e' versionato da nessun repository:
# su una macchina nuova, o dopo una nuova clonazione, non esistono. Il file
# sorgente e' quindi versionato qui in scripts/hooks/ e questo script lo copia
# dove git lo cerca. Va rilanciato dopo ogni clonazione del repository pubblico.

param(
    [string]$SkillsRepo = $env:LETTERDOC_SKILLS_REPO,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if (-not $SkillsRepo) {
    Write-Error "Indicare -SkillsRepo oppure impostare LETTERDOC_SKILLS_REPO."
}
if (-not (Test-Path (Join-Path $SkillsRepo ".git"))) {
    Write-Error "Non e' un repository git: $SkillsRepo"
}

$hooksSrc = Join-Path $root "scripts\hooks"
$hooksDst = Join-Path $SkillsRepo ".git\hooks"

Write-Host "=== install_hooks ===" -ForegroundColor Cyan
Write-Host "sorgente     : $hooksSrc"
Write-Host "destinazione : $hooksDst"
Write-Host ""

if (-not (Test-Path $hooksDst)) {
    New-Item -ItemType Directory -Path $hooksDst -Force | Out-Null
}

foreach ($hook in Get-ChildItem -LiteralPath $hooksSrc -File) {
    $target = Join-Path $hooksDst $hook.Name
    if ((Test-Path $target) -and -not $Force) {
        $existing = Get-Content $target -Raw
        $incoming = Get-Content $hook.FullName -Raw
        if ($existing -eq $incoming) {
            Write-Host "  = $($hook.Name) gia' installato e identico"
            continue
        }
        Write-Host "  ! $($hook.Name) esiste ed e' diverso: usare -Force per sovrascrivere" -ForegroundColor Yellow
        continue
    }
    Copy-Item -LiteralPath $hook.FullName -Destination $target -Force
    Write-Host "  + $($hook.Name) installato" -ForegroundColor Green
}

Write-Host ""
Write-Host "Per provare il cancello senza creare un commit, si esegue l'hook a mano:"
Write-Host "  cd `"$SkillsRepo`"; sh .git/hooks/pre-commit"
Write-Host ""
Write-Host "Nota: 'git commit --dry-run' NON esegue gli hook, quindi non serve a"
Write-Host "verificarli. La prova valida e' quella qui sopra, con il contenuto in stage."
