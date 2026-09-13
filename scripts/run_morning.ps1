$larkPath = "C:\Users\Administrator\AppData\Local\Doubao\User Data\Default\sandbox_envs_dir\envs\d21d026b-5ee9-430b-ab19-4efc2b884e8f\override_dlcs"
$env:PATH = "$larkPath;$env:PATH"
$pythonPath = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
& $pythonPath "learning_system.py" "--status"
exit $LASTEXITCODE
