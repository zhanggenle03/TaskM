@echo off
setlocal enabledelayedexpansion
title TaskM Stopper

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

:: Read current ports from settings.json
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

rem ---- Step 1: Stop backend by PID file ----
echo [1/3] Stopping backend (port %BACKEND_PORT%)...
if exist "%PID_FILE%" (
    set /p OLD_PID=<"%PID_FILE%"
    taskkill /F /T /PID !OLD_PID! >nul 2>nul
    del "%PID_FILE%" 2>nul
    echo   [OK] Backend stopped via PID file
) else (
    for /f "tokens=5" %%p in ('netstat -ano ^| findstr "0.0.0.0:%BACKEND_PORT% "') do (
        taskkill /F /PID %%p >nul 2>nul
    )
)
timeout /t 1 /nobreak >nul
echo.

rem ---- Step 2: Clean up remaining processes ----
echo [2/3] Cleaning up residual processes ...
taskkill /F /IM pythonw.exe >nul 2>nul
taskkill /F /IM node.exe >nul 2>nul
echo   [OK] Cleanup done
echo.

rem ---- Step 3: Verify ports are free ----
echo [3/3] Verifying ports ...
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
