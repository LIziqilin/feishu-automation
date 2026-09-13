@echo off
chcp 65001 >nul
cd /d "D:\AI-Tools\feishu\V13方案增强\scripts"
python learning_system.py --poll >> poll.log 2>&1
