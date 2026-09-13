$logFile = $PSScriptRoot + "\hermes_debug.log"
"started" | Out-File -FilePath $logFile -Encoding ascii
$env:PATH = "C:\Users\Administrator\AppData\Local\hermes\node;" + $env:PATH
"path set" | Out-File -FilePath $logFile -Append -Encoding ascii
Set-Location $PSScriptRoot
"dir: $(Get-Location)" | Out-File -FilePath $logFile -Append -Encoding ascii
$larkTest = & lark-cli --version 2>&1
"lark version: $larkTest" | Out-File -FilePath $logFile -Append -Encoding ascii
$python = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
$output = & $python "learning_system.py" "--poll" 2>&1
$exitCode = $LASTEXITCODE
"python exit: $exitCode" | Out-File -FilePath $logFile -Append -Encoding ascii
"python output:" | Out-File -FilePath $logFile -Append -Encoding ascii
$output | Out-File -FilePath $logFile -Append -Encoding ascii
exit $exitCode
