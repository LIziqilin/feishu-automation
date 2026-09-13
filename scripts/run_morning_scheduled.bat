@echo off
set PATH=C:\Users\Administrator\AppData\Local\hermes\node;%PATH%
set PYTHONIOENCODING=utf-8
C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe "D:\AI-Tools\feishu\V13方案增强\scripts\run_morning_wrapper.py" >> "C:\Windows\Temp\morning_task_scheduler.log" 2>&1
