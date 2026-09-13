@echo off
chcp 65001 >nul
cd /d "D:\AI-Tools\feishu\V13方案增强\scripts"
python review_derive.py --all >> maintenance.log 2>&1
python final_health_check.py >> maintenance.log 2>&1
