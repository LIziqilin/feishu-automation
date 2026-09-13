$env:PATH = "C:\Users\Administrator\AppData\Local\hermes\node;" + $env:PATH
Set-Location $PSScriptRoot
$python = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
& $python "learning_system.py" "--poll"
exit $LASTEXITCODE
