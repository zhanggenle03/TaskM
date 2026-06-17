@echo off
chcp 65001 >nul 2>nul
cd /d "%~dp0"

:: Kill old backend via PID file
if exist "taskm.pid" (
    for /f "usebackq" %%p in ("taskm.pid") do (
        taskkill /F /PID %%p >nul 2>nul
    )
    del "taskm.pid" 2>nul
    timeout /t 1 /nobreak >nul
)

:: Clean previous frontend process
echo Cleaning old frontend...
taskkill /F /IM node.exe 2>nul

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
echo Starting backend...
start "" /b "%PYTHONW%" -X utf8 backend\run.py

:: Start frontend (VBS hidden window)
echo Starting frontend...
echo Set WshShell = CreateObject("WScript.Shell") > %temp%\fe.vbs
echo WshShell.Run "cmd /c cd /d """"%~dp0frontend"""" && npm run dev", 0, False >> %temp%\fe.vbs
cscript //nologo %temp%\fe.vbs
del %temp%\fe.vbs

echo TaskM 启动完成 — 右键系统托盘图标打开浏览器
timeout /t 2 >nul
exit
