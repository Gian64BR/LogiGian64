param([Parameter(Mandatory=$true)][string]$ExecutablePath)
$ErrorActionPreference = 'Stop'
$targetPath = [IO.Path]::GetFullPath($ExecutablePath)
if ([IO.Path]::GetFileName($targetPath) -ine 'LogiGian64.exe') {
    throw 'La ruta debe identificar LogiGian64.exe.'
}

# Match the complete installation path, including both PyInstaller processes.
# Never terminate by image name alone or touch programs launched by a macro.
function Get-AppProcesses {
    @(Get-CimInstance Win32_Process -Filter "Name = 'LogiGian64.exe'" |
        Where-Object { $_.ExecutablePath -and
            [string]::Equals($_.ExecutablePath, $targetPath, [StringComparison]::OrdinalIgnoreCase) })
}

try {
    $appProcesses = @(Get-AppProcesses)
    if (!$appProcesses.Count) { exit 0 }
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class LogiGianShutdown {
    public delegate bool WindowCallback(IntPtr window, IntPtr data);
    [DllImport("user32.dll")] public static extern bool EnumWindows(WindowCallback callback, IntPtr data);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr window, out uint processId);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern uint RegisterWindowMessage(string message);
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr window, uint message, IntPtr wParam, IntPtr lParam);
}
'@
    $processIds = @($appProcesses | ForEach-Object { [uint32]$_.ProcessId })
    $shutdownMessage = [LogiGianShutdown]::RegisterWindowMessage('LogiGian64.Installer.Shutdown.v1')
    $callback = [LogiGianShutdown+WindowCallback] {
        param($window, $data)
        [uint32]$windowProcessId = 0
        [void][LogiGianShutdown]::GetWindowThreadProcessId($window, [ref]$windowProcessId)
        if ($processIds -contains $windowProcessId) {
            [void][LogiGianShutdown]::PostMessage($window, $shutdownMessage, [IntPtr]::Zero, [IntPtr]::Zero)
        }
        return $true
    }
    [void][LogiGianShutdown]::EnumWindows($callback, [IntPtr]::Zero)
    $deadline = [DateTime]::UtcNow.AddSeconds(10)
    do {
        Start-Sleep -Milliseconds 200
        $remaining = @(Get-AppProcesses)
    } while ($remaining.Count -and [DateTime]::UtcNow -lt $deadline)

    # Older builds and unresponsive workers may not handle the shutdown message.
    foreach ($appProcess in $remaining) {
        # Revalidate PID, path and creation time immediately before termination.
        $current = Get-CimInstance Win32_Process -Filter "ProcessId = $($appProcess.ProcessId)"
        if ($current -and $current.CreationDate -eq $appProcess.CreationDate -and
            [string]::Equals($current.ExecutablePath, $targetPath, [StringComparison]::OrdinalIgnoreCase)) {
            Stop-Process -Id $current.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
    $deadline = [DateTime]::UtcNow.AddSeconds(5)
    do {
        Start-Sleep -Milliseconds 200
        $remaining = @(Get-AppProcesses)
    } while ($remaining.Count -and [DateTime]::UtcNow -lt $deadline)
    if ($remaining.Count) { throw 'No se pudieron cerrar todos los procesos de LogiGian64.' }
    exit 0
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 1
}
