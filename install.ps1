# Price-list converter installer for Windows (ASCII-only, works in PS 5.1 and 7).
# One-liner (run inside an open PowerShell window):
#   iwr -useb https://raw.githubusercontent.com/gynsus/best-practice-converter/main/install.ps1 | iex
$ErrorActionPreference = "Stop"
$Dest = "C:\Convert\best-practice-converter"
$Zip  = "https://github.com/gynsus/best-practice-converter/archive/refs/heads/main.zip"
$PyInstaller = "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe"

function Find-Python {
    foreach ($cmd in @("py", "python")) {
        $c = Get-Command $cmd -ErrorAction SilentlyContinue
        if (-not $c) { continue }
        try {
            $verArgs = if ($cmd -eq "py") { @("-3", "--version") } else { @("--version") }
            $v = (& $c.Source @verArgs) 2>&1 | Out-String
            if ($v -match "Python 3\.(9|1[0-9])") {
                if ($cmd -eq "py") { return @{ Exe = $c.Source; Args = @("-3") } }
                else { return @{ Exe = $c.Source; Args = @() } }
            }
        } catch {}
    }
    return $null
}

Write-Host "== 1/5 Python check =="
$py = Find-Python
if (-not $py) {
    Write-Host "Python 3.9+ not found. Downloading installer from python.org (no winget needed)..."
    $exe = Join-Path $env:TEMP "python-setup.exe"
    Invoke-WebRequest -UseBasicParsing $PyInstaller -OutFile $exe
    Write-Host "Installing Python 3.12 (silent, all users, add to PATH)..."
    Start-Process -Wait $exe -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_launcher=1 Include_test=0"
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
    $py = Find-Python
    if (-not $py) { throw "Python installation failed. Install manually from python.org and re-run." }
}
Write-Host ("Python: " + ((& $py.Exe ($py.Args + @("--version"))) 2>&1 | Out-String).Trim())

Write-Host "== 2/5 Downloading converter =="
$tmp = Join-Path $env:TEMP "bpc.zip"
Invoke-WebRequest -UseBasicParsing $Zip -OutFile $tmp
$extract = Join-Path $env:TEMP "bpc_extract"
if (Test-Path $extract) { Remove-Item -Recurse -Force $extract }
Expand-Archive $tmp -DestinationPath $extract
New-Item -ItemType Directory -Force (Split-Path $Dest) | Out-Null
$src = (Get-ChildItem $extract | Select-Object -First 1).FullName
if (Test-Path $Dest) {
    # keep local-only files across updates: settings and mail credentials
    $keepFiles = @("settings.yaml", "email.yaml")
    $keepDir = Join-Path $env:TEMP "bpc_keep"
    if (Test-Path $keepDir) { Remove-Item -Recurse -Force $keepDir }
    New-Item -ItemType Directory $keepDir | Out-Null
    foreach ($f in $keepFiles) {
        if (Test-Path "$Dest\$f") { Copy-Item "$Dest\$f" (Join-Path $keepDir $f) -Force }
    }
    Remove-Item -Recurse -Force $Dest
    Copy-Item $src $Dest -Recurse
    foreach ($f in $keepFiles) {
        $kept = Join-Path $keepDir $f
        if (Test-Path $kept) { Copy-Item $kept "$Dest\$f" -Force }
    }
    Remove-Item -Recurse -Force $keepDir
} else {
    Copy-Item $src $Dest -Recurse
}
Write-Host "Code: $Dest"

Write-Host "== 3/5 Virtual environment and dependencies =="
Set-Location $Dest
& $py.Exe ($py.Args + @("-m", "venv", ".venv"))
$venvPy = "$Dest\.venv\Scripts\python.exe"
& $venvPy -m pip install --quiet --upgrade pip
& $venvPy -m pip install --quiet -r requirements.txt

Write-Host "== 4/5 Directory / file-matching check (--check) =="
& $venvPy main.py --check
if ($LASTEXITCODE -ne 0) { Write-Host "WARNING: check reported problems (see [!!] above)." -ForegroundColor Yellow }

Write-Host "== 5/5 Done =="
Write-Host "Run now:       $Dest\run.cmd   (output goes to launcher.log)"
Write-Host "Re-check:      $venvPy $Dest\main.py --check"
Write-Host "Scheduler (daily 22:00, via run.cmd so early errors are logged):"
Write-Host '  schtasks /Create /F /TN "PriceConverter" /SC DAILY /ST 22:00 /TR "C:\Convert\best-practice-converter\run.cmd"'
Write-Host "Mail reports:  create email.yaml next to main.py (see INSTALL-WINDOWS.md)"
