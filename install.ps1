# Установка конвертера прайс-листов на Windows (запуск в PowerShell).
# Одной командой на VPS:
#   powershell -ExecutionPolicy Bypass -c "iwr -useb https://raw.githubusercontent.com/gynsus/best-practice-converter/main/install.ps1 | iex"
$ErrorActionPreference = "Stop"
$Dest = "C:\Convert\best-practice-converter"
$Zip  = "https://github.com/gynsus/best-practice-converter/archive/refs/heads/main.zip"

Write-Host "== 1/5 Проверка Python =="
$py = $null
foreach ($cand in @("py -3", "python")) {
    try {
        $v = & $cand.Split()[0] $cand.Split()[1..9] --version 2>$null
        if ($v -match "Python 3\.(9|1[0-9])") { $py = $cand; break }
    } catch {}
}
if (-not $py) {
    Write-Host "Python 3.9+ не найден. Ставлю через winget..."
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
    $py = "py -3"
}
Write-Host "Python: $(& $py.Split()[0] $py.Split()[1..9] --version)"

Write-Host "== 2/5 Загрузка конвертера =="
$tmp = Join-Path $env:TEMP "bpc.zip"
Invoke-WebRequest -UseBasicParsing $Zip -OutFile $tmp
$extract = Join-Path $env:TEMP "bpc_extract"
if (Test-Path $extract) { Remove-Item -Recurse -Force $extract }
Expand-Archive $tmp -DestinationPath $extract
New-Item -ItemType Directory -Force (Split-Path $Dest) | Out-Null
if (Test-Path $Dest) {
    # обновление: код заменяем, settings.yaml сохраняем
    $keep = Join-Path $env:TEMP "settings.keep.yaml"
    if (Test-Path "$Dest\settings.yaml") { Copy-Item "$Dest\settings.yaml" $keep -Force }
    Remove-Item -Recurse -Force $Dest
    Copy-Item (Get-ChildItem $extract | Select-Object -First 1).FullName $Dest -Recurse
    if (Test-Path $keep) { Copy-Item $keep "$Dest\settings.yaml" -Force }
} else {
    Copy-Item (Get-ChildItem $extract | Select-Object -First 1).FullName $Dest -Recurse
}
Write-Host "Код: $Dest"

Write-Host "== 3/5 Окружение и зависимости =="
Set-Location $Dest
& $py.Split()[0] $py.Split()[1..9] -m venv .venv
& "$Dest\.venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
& "$Dest\.venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt

Write-Host "== 4/5 Проверка каталогов и сопоставления файлов =="
& "$Dest\.venv\Scripts\python.exe" main.py --check
if ($LASTEXITCODE -ne 0) { Write-Host "ВНИМАНИЕ: проверка нашла проблемы (см. выше)." -ForegroundColor Yellow }

Write-Host "== 5/5 Готово =="
Write-Host "Боевой запуск:      $Dest\.venv\Scripts\python.exe $Dest\main.py"
Write-Host "Повторная проверка: $Dest\.venv\Scripts\python.exe $Dest\main.py --check"
Write-Host "Планировщик (пример, ежедневно в 22:00):"
Write-Host '  schtasks /Create /F /TN "PriceConverter" /SC DAILY /ST 22:00 /TR "C:\Convert\best-practice-converter\.venv\Scripts\python.exe C:\Convert\best-practice-converter\main.py"'
