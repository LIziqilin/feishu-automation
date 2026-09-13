# setup_auto_schedule.ps1 - Setup Windows Task Scheduler for V16 Learning System
# Run as Administrator

$ErrorActionPreference = "Stop"
$ScriptDir = "D:\AI-Tools\feishu\V13方案增强\scripts"
$PythonPath = "python"
$LogDir = "D:\AI-Tools\feishu\V13方案增强\logs"

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "V16 Learning System - Auto Schedule Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Task 1: Poll messages every 5 minutes
$taskName1 = "V16_LearningPoll"
$action1 = New-ScheduledTaskAction -Execute $PythonPath `
    -Argument "`"$ScriptDir\learning_system.py`" --poll" `
    -WorkingDirectory $ScriptDir
$trigger1 = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5)
$settings1 = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

# Task 2: Morning report at 07:30 daily
$taskName2 = "V16_MorningReport"
$action2 = New-ScheduledTaskAction -Execute $PythonPath `
    -Argument "`"$ScriptDir\learning_system.py`" --select" `
    -WorkingDirectory $ScriptDir
$trigger2 = New-ScheduledTaskTrigger -Daily -At 7:30
$settings2 = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 15)

# Task 3: Daily maintenance at 03:00
$taskName3 = "V16_DailyMaintenance"
$action3 = New-ScheduledTaskAction -Execute $PythonPath `
    -Argument "`"$ScriptDir\review_derive.py`" --all" `
    -WorkingDirectory $ScriptDir
$trigger3 = New-ScheduledTaskTrigger -Daily -At 3:00
$settings3 = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

$tasks = @(
    @{Name=$taskName1; Action=$action1; Trigger=$trigger1; Settings=$settings1; Desc="Poll group messages every 5 min, parse answers"},
    @{Name=$taskName2; Action=$action2; Trigger=$trigger2; Settings=$settings2; Desc="Push morning report at 07:30 daily"},
    @{Name=$taskName3; Action=$action3; Trigger=$trigger3; Settings=$settings3; Desc="Daily derive recalc at 03:00"}
)

foreach ($task in $tasks) {
    Write-Host "`nSetting up task: $($task.Name)" -ForegroundColor Yellow
    Write-Host "  Desc: $($task.Desc)"

    $existing = Get-ScheduledTask -TaskName $task.Name -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "  Task exists, updating..." -ForegroundColor Gray
        Unregister-ScheduledTask -TaskName $task.Name -Confirm:$false
    }

    Register-ScheduledTask -TaskName $task.Name `
        -Action $task.Action `
        -Trigger $task.Trigger `
        -Settings $task.Settings `
        -Description $task.Desc `
        -Force | Out-Null

    Write-Host "  OK: Task configured" -ForegroundColor Green
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Auto Schedule Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`n3 scheduled tasks configured:"
Write-Host "  1. V16_LearningPoll     - Every 5 min: poll & parse answers"
Write-Host "  2. V16_MorningReport    - Daily 07:30: push morning report"
Write-Host "  3. V16_DailyMaintenance - Daily 03:00: derive recalc"
Write-Host "`nCommands:"
Write-Host "  List:   Get-ScheduledTask -TaskName 'V16_*'"
Write-Host "  Run:    Start-ScheduledTask -TaskName 'V16_LearningPoll'"
Write-Host "  Remove: Unregister-ScheduledTask -TaskName 'V16_*' -Confirm:`$false"
