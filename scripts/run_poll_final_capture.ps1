$ErrorActionPreference = "Continue"
$logFile = "D:\AI-Tools\feishu\V13方案增强\scripts\task_final_debug.log"

function Log($msg) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$timestamp - $msg" | Out-File -FilePath $logFile -Append -Encoding ascii
}

Log "=== 任务计划开始 ==="

# 设置lark-cli路径
$larkPath = "C:\Users\Administrator\AppData\Local\Doubao\User Data\Default\sandbox_envs_dir\envs\d21d026b-5ee9-430b-ab19-4efc2b884e8f\override_dlcs"
$env:PATH = "$larkPath;$env:PATH"
Log "PATH已设置"

# 设置Doubao Office环境变量
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
Log "Doubao环境变量已设置"

# 测试lark-cli是否可用
Log "测试lark-cli..."
$larkTest = & lark-cli --version 2>&1
Log "lark-cli版本: $larkTest"

# 测试lark-cli base命令
Log "测试lark-cli base +table-list..."
$baseTest = & lark-cli base +table-list --base-token X8N1bvN3na99dFsyu0gcU8zTnHf --as user 2>&1
Log "base测试输出（前5行）:"
$baseTest | Select-Object -First 5 | ForEach-Object { Log "  $_" }

# 设置工作目录
Set-Location "D:\AI-Tools\feishu\V13方案增强\scripts"
Log "工作目录: $(Get-Location)"

# 运行python脚本
Log "开始运行python learning_system.py --poll"
$pythonPath = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
$output = & $pythonPath "learning_system.py" "--poll" 2>&1
$exitCode = $LASTEXITCODE
Log "Python退出码: $exitCode"
Log "Python输出:"
$output | ForEach-Object { Log "  $_" }

Log "=== 任务计划结束 ==="
exit $exitCode
