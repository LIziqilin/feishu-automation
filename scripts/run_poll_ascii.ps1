$logFile = $PSScriptRoot + "\task_ascii_test.log"
"started" | Out-File -FilePath $logFile -Encoding ascii
"dir: $PSScriptRoot" | Out-File -FilePath $logFile -Append -Encoding ascii
$env:PATH = "C:\Users\Administrator\AppData\Local\Doubao\User Data\Default\sandbox_envs_dir\envs\d21d026b-5ee9-430b-ab19-4efc2b884e8f\override_dlcs;" + $env:PATH
$env:DOUBAO_OFFICE_CLI_TOKEN = "MZEHUKXDJXTvBmFqafLykChYCyRXlqeyOTud8VwMMSRcPADcvqbmfMZwp957p_VbI3-XdIDpYtY4kFWaIU2f"
$env:DOUBAO_OFFICE_USER_ACCESS_TOKEN = "MZEHUKXDJXTvBmFqafLykChYCyRXlqeyOTud8VwMMSRcPADcvqbmfMZwp957p_VbI3-XdIDpYtY4kFWaIU2f"
$env:DOUBAO_OFFICE_FORWARD_PROXY = "https://www.doubao.com/alice/office/sandbox/lark_cli/proxy"
$env:DOUBAO_OFFICE_CLI_FORWARD_PROXY = "https://www.doubao.com/alice/office/sandbox/cli/proxy"
$env:DOUBAO_OFFICE_AGENT_NAME = "doubao_moa"
$env:DOUBAO_OFFICE_APP_ID = "582478"
$env:DOUBAO_OFFICE_EDITION = "public"
$env:DOUBAO_OFFICE_MARKET = "cn"
$env:DOUBAO_OFFICE_PLATFORM_APP_ID = "582478"
$env:LARKSUITE_CLI_AGENT_NAME = "doubao_moa"
"env set" | Out-File -FilePath $logFile -Append -Encoding ascii
$python = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
$output = & $python "learning_system.py" "--poll" 2>&1
$exitCode = $LASTEXITCODE
"python exit: $exitCode" | Out-File -FilePath $logFile -Append -Encoding ascii
$output | Out-File -FilePath $logFile -Append -Encoding ascii
exit $exitCode
