# Instala o Master Develops no Windows: skill + 18 agentes no Claude Code e no Codex,
# e gera a ferramenta (Painel de producao em tempo real).
#
#   irm https://raw.githubusercontent.com/carlos-dataengineer/master-develops-software-app/main/install.ps1 | iex
#
# Variaveis de ambiente opcionais (defina antes do comando):
#   $env:MASTERDEV_HOME = "D:\MDV"      pasta do painel e do historico (padrao: $HOME\MasterDevelops)
#   $env:MDV_SKIP_CLAUDE = "1"          nao instala no Claude Code
#   $env:MDV_SKIP_CODEX = "1"           nao instala no Codex
#   $env:MDV_NO_HOOKS = "1"             nao liga os hooks do Claude Code
#   $env:MDV_NO_OPEN = "1"              nao abre o navegador
#   $env:MDV_REF = "v1.0.0"             branch ou tag (padrao: main)
#
# Com o repositorio clonado:  .\install.ps1 [-Uninstall] [-Purge] [-Force] [-Project C:\caminho]
param([switch]$Uninstall, [switch]$Purge, [switch]$Force, [string]$Project)

$ErrorActionPreference = "Stop"
$Repo = "carlos-dataengineer/master-develops-software-app"
$Ref = if ($env:MDV_REF) { $env:MDV_REF } else { "main" }

function Find-Python {
    foreach ($cand in @(@("py", "-3"), @("python"), @("python3"))) {
        $exe = $cand[0]
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        $extra = @($cand | Select-Object -Skip 1)
        try {
            & $exe @extra -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) { return ,$cand }
        } catch { }
    }
    return $null
}

$py = Find-Python
if (-not $py) {
    Write-Host "O Master Develops precisa do Python 3.10 ou mais novo. Instale em https://www.python.org/downloads/ (marque 'Add to PATH') e rode de novo." -ForegroundColor Red
    return
}

$tmp = $null
try {
    $local = $null
    if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot "scripts\install.py"))) { $local = $PSScriptRoot }
    if ($local) {
        $root = $local
        Write-Host "  > Usando os arquivos locais em $root"
    } else {
        $tmp = Join-Path ([IO.Path]::GetTempPath()) ("mdv-" + [guid]::NewGuid().ToString("N"))
        New-Item -ItemType Directory -Path $tmp | Out-Null
        $kind = if ($Ref -match '^v\d') { "tags" } else { "heads" }
        $zip = Join-Path $tmp "mdv.zip"
        Write-Host "  > Baixando $Repo ($Ref)"
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri "https://codeload.github.com/$Repo/zip/refs/$kind/$Ref" -OutFile $zip
        Expand-Archive -Path $zip -DestinationPath $tmp -Force
        $root = (Get-ChildItem -Path $tmp -Directory | Select-Object -First 1).FullName
        if (-not (Test-Path (Join-Path $root "scripts\install.py"))) { throw "O pacote baixado nao tem scripts\install.py." }
    }

    $argsList = @()
    if ($Uninstall) { $argsList += "--uninstall" }
    if ($Purge) { $argsList += "--purge" }
    if ($Force) { $argsList += "--force" }
    if ($Project) { $argsList += @("--scope", "project", "--project", $Project) }
    $exe = $py[0]
    $pre = @($py | Select-Object -Skip 1)
    & $exe @pre -X utf8 (Join-Path $root "scripts\install.py") @argsList
} finally {
    if ($tmp -and (Test-Path $tmp)) { Remove-Item -Recurse -Force -LiteralPath $tmp }
}
