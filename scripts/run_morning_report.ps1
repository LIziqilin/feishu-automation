$ErrorActionPreference = "Continue"
Set-Location "D:\AI-Tools\feishu\V13方案增强\scripts"
python learning_system.py --status 2>&1 | Out-File -FilePath "morning_report.log" -Append -Encoding utf8
