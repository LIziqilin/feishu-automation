$ErrorActionPreference = "Continue"
$logFile = "D:\AI-Tools\feishu\V13方案增强\scripts\task_scheduler_debug.log"

function Log($msg) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$timestamp - $msg" | Out-File -FilePath $logFile -Append -Encoding utf8
}

Log "=== 任务计划开始运行 ==="
Log "当前用户: $(whoami)"
Log "当前目录: $(Get-Location)"
Log "脚本目录: $PSScriptRoot"

# 设置工作目录
$workDir = "D:\AI-Tools\feishu\V13方案增强\scripts"
Set-Location $workDir
Log "设置工作目录后: $(Get-Location)"

# 检查python
$pythonPath = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
Log "Python路径: $pythonPath"
Log "Python存在: $(Test-Path $pythonPath)"

# 检查lark-cli
$larkPath = "C:\Users\Administrator\AppData\Local\Doubao\User Data\Default\sandbox_envs_dir\envs\d21d026b-5ee9-430b-ab19-4efc2b884e8f\override_dlcs"
Log "lark-cli路径: $larkPath"
Log "lark-cli存在: $(Test-Path "$larkPath\lark-cli.exe")"

# 设置PATH
$env:PATH = "$larkPath;$env:PATH"
Log "PATH已设置"
Log "lark-cli可执行: $(Get-Command lark-cli -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source)"

# 检查脚本文件
$scriptPath = "$workDir\learning_system.py"
Log "脚本路径: $scriptPath"
Log "脚本存在: $(Test-Path $scriptPath)"

# 运行python脚本
Log "开始运行python learning_system.py --poll"
try {
    $output = & $pythonPath $scriptPath "--poll" 2>&1
    $exitCode = $LASTEXITCODE
    Log "Python退出码: $exitCode"
    Log "Python输出:"
    $output | ForEach-Object { Log "  $_" }
    exit $exitCode
} catch {
    Log "异常: $_"
    Log "异常详情: $($_.Exception.Message)"
    exit 1
}
