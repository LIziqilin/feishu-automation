$ErrorActionPreference = "Continue"

# 设置lark-cli路径
$larkPath = "C:\Users\Administrator\AppData\Local\Doubao\User Data\Default\sandbox_envs_dir\envs\d21d026b-5ee9-430b-ab19-4efc2b884e8f\override_dlcs"
$env:PATH = "$larkPath;$env:PATH"

# 设置Doubao Office代理环境变量（lark-cli认证所需）
$env:DOUBAO_OFFICE_AGENT_NAME = "doubao_moa"
$env:DOUBAO_OFFICE_APP_ID = "582478"
$env:DOUBAO_OFFICE_CLI_FORWARD_PROXY = "https://www.doubao.com/alice/office/sandbox/cli/proxy"
$env:DOUBAO_OFFICE_CLI_TOKEN = "MZEHUKXDJXTvBmFqafLykChYCyRXlqeyOTud8VwMMSRcPADcvqbmfMZwp957p_VbI3-XdIDpYtY4kFWaIU2f"
$env:DOUBAO_OFFICE_EDITION = "public"
$env:DOUBAO_OFFICE_FORWARD_PROXY = "https://www.doubao.com/alice/office/sandbox/lark_cli/proxy"
$env:DOUBAO_OFFICE_LOG_ID = "202609110858277A5DB721FD4A4ED582AA"
$env:DOUBAO_OFFICE_MARKET = "cn"
$env:DOUBAO_OFFICE_PLATFORM_APP_ID = "582478"
$env:DOUBAO_OFFICE_USER_ACCESS_TOKEN = "MZEHUKXDJXTvBmFqafLykChYCyRXlqeyOTud8VwMMSRcPADcvqbmfMZwp957p_VbI3-XdIDpYtY4kFWaIU2f"
$env:LARKSUITE_CLI_AGENT_NAME = "doubao_moa"

# 设置工作目录
Set-Location "D:\AI-Tools\feishu\V13方案增强\scripts"

# 运行python脚本
$pythonPath = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
& $pythonPath "learning_system.py" "--poll"
exit $LASTEXITCODE
