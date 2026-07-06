$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $Root "scripts\launch_windows.ps1")
