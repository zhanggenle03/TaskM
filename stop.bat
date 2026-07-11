@echo off
setlocal enabledelayedexpansion
title TaskM Stopper

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

:: Read current ports from settings.json (best-effort, fall back to defaults)
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=5173"
for /f "tokens=2 delims=:," %%a in ('findstr /i "backend_port" "%ROOT%\backend\settings.json" 2^>nul') do set "BACKEND_PORT=%%a"
for /f "tokens=2 delims=:," %%a in ('findstr /i "frontend_port" "%ROOT%\backend\settings.json" 2^>nul') do set "FRONTEND_PORT=%%a"
set "BACKEND_PORT=%BACKEND_PORT: =%"
set "FRONTEND_PORT=%FRONTEND_PORT: =%"

set "PID_FILE=%ROOT%\taskm.pid"

echo ========================================
echo   TaskM -- Stopping Services
echo ========================================
echo.

rem ---- Step 1: Stop backend by PID file (kill whole tree) ----
echo [1/4] Stopping backend (PID file, port %BACKEND_PORT%)...
if exist "%PID_FILE%" (
    set /p OLD_PID=<"%PID_FILE%"
    if defined OLD_PID (
        taskkill /F /T /PID !OLD_PID! >nul 2>nul
        echo   [OK] Killed PID !OLD_PID! (process tree)
    )
    del "%PID_FILE%" >nul 2>nul
) else (
    echo   [~] No PID file, will resolve by port
)
echo.

rem ---- Step 2: Kill anything still listening on backend port (tree) ----
echo [2/4] Freeing backend port %BACKEND_PORT%...
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr "0.0.0.0:%BACKEND_PORT% "') do (
    taskkill /F /T /PID %%p >nul 2>nul
    echo   [OK] Killed listener PID %%p (tree)
)
echo.

rem ---- Step 3: Kill frontend (Vite) dev server tree, and any TaskM node ----
echo [3/4] Freeing frontend port %FRONTEND_PORT% (dev)...
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":%FRONTEND_PORT% " ^| findstr "LISTENING"') do (
    taskkill /F /T /PID %%p >nul 2>nul
    echo   [OK] Killed frontend listener PID %%p (tree)
)
rem Best-effort: kill node processes that belong to THIS TaskM frontend
rem (avoids leaving an orphaned npm parent). Precise: matches command line.
wmic process where "name='node.exe' and commandline like '%%TaskM%%frontend%%'" call terminate >nul 2>nul
echo.

rem ---- Step 4: Verify ports are free ----
echo [4/4] Verifying ports ...
set "ALL_FREE=1"
netstat -ano 2>nul | findstr "0.0.0.0:%BACKEND_PORT% " >nul && (
    echo   [!] Port %BACKEND_PORT% still in use
    set "ALL_FREE=0"
) || (
    echo   [OK] Port %BACKEND_PORT% freed
)
netstat -ano 2>nul | findstr "LISTENING" | findstr ":%FRONTEND_PORT% " >nul && (
    echo   [!] Port %FRONTEND_PORT% still in use
    set "ALL_FREE=0"
) || (
    echo   [OK] Port %FRONTEND_PORT% freed
)
echo.

if "!ALL_FREE!"=="1" (
    echo ========================================
    echo   All TaskM services stopped
    echo ========================================
) else (
    echo ========================================
    echo   [!] Some ports still in use, check Task Manager
    echo ========================================
)

echo.
timeout /t 3 /nobreak >nul
