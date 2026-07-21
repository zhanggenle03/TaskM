@echo off
chcp 65001 >nul 2>nul
cd /d "%~dp0"

:: Read current ports from settings.json
set "BP="
set "FP="
for /f "tokens=2 delims=:," %%a in ('findstr /i "backend_port" backend\settings.json') do set "BP=%%a"
for /f "tokens=2 delims=:," %%a in ('findstr /i "frontend_port" backend\settings.json') do set "FP=%%a"
if defined BP set "BP=%BP: =%"
if defined FP set "FP=%FP: =%"
if not defined BP set "BP=8000"
if not defined FP set "FP=5173"
set "VITE_API_TARGET=http://localhost:%BP%"
set "VITE_FRONTEND_PORT=%FP%"

:: Free backend port by actual listener (address-agnostic), so the new run.py
:: can always bind and load the latest code (Python does NOT hot-reload).
:: NOTE: kill only the precise listener PID — never /IM node.exe (would kill
:: every Node app on the machine) and never /T tree kill (collateral damage).
echo Freeing backend port %BP% by listener...
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr "LISTENING" ^| findstr ":%BP% "') do (
    taskkill /F /PID %%p >nul 2>nul
    echo   [OK] Killed listener PID %%p
)

:: Free frontend port (precise listener only)
echo Freeing frontend port %FP% by listener...
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr "LISTENING" ^| findstr ":%FP% "') do (
    taskkill /F /PID %%p >nul 2>nul
    echo   [OK] Killed frontend listener PID %%p
)
timeout /t 1 /nobreak >nul

:: Detect pythonw location (prefer system Python 3.10)
set "PYTHONW="
if exist "D:\python310\pythonw.exe" set "PYTHONW=D:\python310\pythonw.exe"
if not defined PYTHONW if exist "C:\python310\pythonw.exe" set "PYTHONW=C:\python310\pythonw.exe"
if not defined PYTHONW if exist "C:\Python310\pythonw.exe" set "PYTHONW=C:\Python310\pythonw.exe"
if not defined PYTHONW if exist "C:\Program Files\Python310\pythonw.exe" set "PYTHONW=C:\Program Files\Python310\pythonw.exe"
if not defined PYTHONW (
    where pythonw >nul 2>&1
    if errorlevel 1 (
        echo Error: pythonw not found!
        pause
        exit /b 1
    )
    set "PYTHONW=pythonw"
)

:: Start backend
echo Starting backend (port %BP%)...
start "" /b "%PYTHONW%" -X utf8 backend\run.py

:: Start frontend (VBS hidden window, pass env vars via set)
echo Starting frontend (port %FP%, proxy to %VITE_API_TARGET%)...
echo Set WshShell = CreateObject("WScript.Shell") > %temp%\fe.vbs
echo WshShell.Run "cmd /c cd /d """"%~dp0frontend"""" && set VITE_API_TARGET=%VITE_API_TARGET% && set VITE_FRONTEND_PORT=%VITE_FRONTEND_PORT% && npm run dev", 0, False >> %temp%\fe.vbs
cscript //nologo %temp%\fe.vbs
del %temp%\fe.vbs

echo TaskM 启动完成 — 右键系统托盘图标打开浏览器
timeout /t 2 >nul
exit
