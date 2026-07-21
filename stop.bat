@echo off
setlocal enabledelayedexpansion
title TaskM Stopper

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

:: Read current ports from settings.json (best-effort, fall back to defaults)
set "BACKEND_PORT=8002"
set "FRONTEND_PORT=5176"
for /f "tokens=2 delims=:," %%a in ('findstr /i "backend_port" "%ROOT%\backend\settings.json" 2^>nul') do set "BACKEND_PORT=%%a"
for /f "tokens=2 delims=:," %%a in ('findstr /i "frontend_port" "%ROOT%\backend\settings.json" 2^>nul') do set "FRONTEND_PORT=%%a"
set "BACKEND_PORT=%BACKEND_PORT: =%"
set "FRONTEND_PORT=%FRONTEND_PORT: =%"

echo ========================================
echo   TaskM -- Stopping Services
echo ========================================
echo.
echo   !!! SAFE MODE: only TaskM's own backend/frontend are targeted.
echo   !!! No tree kills, no system-wide process kills.
echo.

rem ---- Step 1: Stop backend by listening port (precise single PID, no tree) ----
echo [1/3] Stopping backend on port %BACKEND_PORT%...
set "KILLED=0"
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr "LISTENING" ^| findstr ":%BACKEND_PORT% "') do (
    taskkill /F /PID %%p >nul 2>nul
    echo   [OK] Killed backend listener PID %%p
    set "KILLED=1"
)
if "!KILLED!"=="0" echo   [~] No process listening on port %BACKEND_PORT%

rem ---- Step 2: Stop frontend (Vite) dev server by listening port ----
echo [2/3] Stopping frontend on port %FRONTEND_PORT%...
set "KILLED=0"
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr "LISTENING" ^| findstr ":%FRONTEND_PORT% "') do (
    taskkill /F /PID %%p >nul 2>nul
    echo   [OK] Killed frontend listener PID %%p
    set "KILLED=1"
)
if "!KILLED!"=="0" echo   [~] No process listening on port %FRONTEND_PORT%

rem ---- Step 3: Safety net — kill only THIS project's own backend/frontend by command line ----
echo [3/3] Safety net (TaskM-specific processes only)...
rem Backend: pythonw/python running backend\run.py (no tree kill)
for /f "skip=1 tokens=2" %%p in ('wmic process where "name='pythonw.exe' and commandline like '%%backend\\run.py%%'" get processid 2^>nul') do taskkill /F /PID %%p >nul 2>nul
for /f "skip=1 tokens=2" %%p in ('wmic process where "name='python.exe' and commandline like '%%backend\\run.py%%'" get processid 2^>nul') do taskkill /F /PID %%p >nul 2>nul
rem Frontend: node running vite from THIS project's frontend dir (no tree kill)
for /f "skip=1 tokens=2" %%p in ('wmic process where "name='node.exe' and commandline like '%%TaskM\\frontend%%vite%%'" get processid 2^>nul') do taskkill /F /PID %%p >nul 2>nul
echo   [OK] Safety net applied.

rem ---- Remove stale PID file (do NOT kill by its contents) ----
if exist "%ROOT%\taskm.pid" del "%ROOT%\taskm.pid" >nul 2>nul

echo.
echo ========================================
echo   TaskM services stopped
echo ========================================
echo.
timeout /t 2 /nobreak >nul
