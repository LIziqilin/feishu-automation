@echo off
chcp 65001 >nul
set "PATH=C:\Users\Administrator\AppData\Local\hermes\node;%PATH%"
set "PYTHONIOENCODING=utf-8"
cd /d "D:\AI-Tools\feishu\V13方案增强\scripts"
"C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe" weekly_review.py >> "D:\AI-Tools\feishu\V13方案增强\scripts\weekly_review_scheduler.log" 2>&1
