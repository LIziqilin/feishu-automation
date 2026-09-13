@echo off
chcp 65001 >nul
cd /d "D:\AI-Tools\feishu\V13方案增强\scripts"
python learning_system.py --morning-report >> morning_report.log 2>&1
