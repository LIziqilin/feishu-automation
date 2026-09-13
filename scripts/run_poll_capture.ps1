$env:PATH = "C:\Users\Administrator\AppData\Local\Doubao\User Data\Default\sandbox_envs_dir\envs\d21d026b-5ee9-430b-ab19-4efc2b884e8f\override_dlcs;" + $env:PATH
$python = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
$output = & $python "learning_system.py" "--poll" 2>&1
$exitCode = $LASTEXITCODE
"EXIT_CODE: $exitCode" | Out-File -FilePath "poll_error.log" -Encoding ascii
"OUTPUT:" | Out-File -FilePath "poll_error.log" -Append -Encoding ascii
$output | Out-File -FilePath "poll_error.log" -Append -Encoding ascii
exit $exitCode
