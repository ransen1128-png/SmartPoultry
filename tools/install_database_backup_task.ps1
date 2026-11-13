$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\pythonw.exe'
$backupScript = Join-Path $PSScriptRoot 'backup_database.py'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Project Python environment not found.' }
$taskAction = New-ScheduledTaskAction -Execute $pythonPath -Argument ('"{0}" --verify-restore' -f $backupScript) -WorkingDirectory $projectRoot
$taskTrigger = New-ScheduledTaskTrigger -Daily -At '2:00AM'
$taskIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$taskPrincipal = New-ScheduledTaskPrincipal -UserId $taskIdentity -LogonType Interactive -RunLevel Limited
$taskSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
try {
    Register-ScheduledTask -TaskName 'SmartPoultry Database Backup' -Action $taskAction -Trigger $taskTrigger -Principal $taskPrincipal -Settings $taskSettings -Description 'Daily desktop PostgreSQL backup with isolated restore verification. Runs while this Windows account is logged in; catches up after a missed schedule.' -Force -ErrorAction Stop | Select-Object TaskName,State
} catch {
    $startupFolder = [Environment]::GetFolderPath('Startup')
    $shortcutPath = Join-Path $startupFolder 'SmartPoultry Database Backup.lnk'
    $shortcutShell = New-Object -ComObject WScript.Shell
    $shortcut = $shortcutShell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $pythonPath
    $shortcut.Arguments = '"{0}"' -f (Join-Path $PSScriptRoot 'database_backup_scheduler.py')
    $shortcut.WorkingDirectory = $projectRoot
    $shortcut.WindowStyle = 7
    $shortcut.Description = 'Daily 2AM local PostgreSQL backups with isolated restore verification; catches up after login.'
    $shortcut.Save()
    Write-Output 'Task Scheduler registration unavailable; installed current-user Startup backup scheduler instead.'
}
