$ErrorActionPreference = "Continue"
Set-Location "D:\AI-Tools\feishu\V13方案增强\scripts"
python review_derive.py --all 2>&1 | Out-File -FilePath "maintenance.log" -Append -Encoding utf8
python final_health_check.py 2>&1 | Out-File -FilePath "maintenance.log" -Append -Encoding utf8
