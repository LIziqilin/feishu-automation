$env:PATH = "C:\Users\Administrator\AppData\Local\hermes\node;$env:PATH"
$env:PYTHONIOENCODING = "utf-8"
$python = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
$script = "D:\AI-Tools\feishu\V13方案增强\scripts\run_morning_wrapper.py"
$log = "C:\Windows\Temp\morning_task_scheduler.log"
& $python $script *>> $log
