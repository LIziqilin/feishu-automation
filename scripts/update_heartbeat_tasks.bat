@echo off
REM 更新3个心跳任务计划：删除旧任务，创建新任务指向新路径

set PYTHON=C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe
set SCRIPT=D:\AI-Tools\feishu\V13方案增强\scripts\heartbeat.py

echo ========================================
echo 更新心跳任务计划
echo ========================================

echo.
echo [1/3] Morning任务 (08:00)
schtasks /delete /tn "FeishuAssistant-Heartbeat-Morning" /f 2>nul
schtasks /create /tn "FeishuAssistant-Heartbeat-Morning" /tr "\"%PYTHON%\" \"%SCRIPT%\"" /sc daily /st 08:00 /ru Administrator /rl highest /f
echo.

echo [2/3] Noon任务 (14:00)
schtasks /delete /tn "FeishuAssistant-Heartbeat-Noon" /f 2>nul
schtasks /create /tn "FeishuAssistant-Heartbeat-Noon" /tr "\"%PYTHON%\" \"%SCRIPT%\"" /sc daily /st 14:00 /ru Administrator /rl highest /f
echo.

echo [3/3] Night任务 (22:00)
schtasks /delete /tn "FeishuAssistant-Heartbeat-Night" /f 2>nul
schtasks /create /tn "FeishuAssistant-Heartbeat-Night" /tr "\"%PYTHON%\" \"%SCRIPT%\"" /sc daily /st 22:00 /ru Administrator /rl highest /f
echo.

echo ========================================
echo 验证任务状态
echo ========================================
schtasks /query /tn "FeishuAssistant-Heartbeat-Morning" /v /fo LIST | findstr /i "Status Next Last Task To Run"
echo.
schtasks /query /tn "FeishuAssistant-Heartbeat-Noon" /v /fo LIST | findstr /i "Status Next Last Task To Run"
echo.
schtasks /query /tn "FeishuAssistant-Heartbeat-Night" /v /fo LIST | findstr /i "Status Next Last Task To Run"
echo.
echo 完成
