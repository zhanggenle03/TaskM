@echo off
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

:: Detect pythonw location
set "PYTHONW=pythonw"
where pythonw >nul 2>&1
if errorlevel 1 (
    if exist "D:\python310\pythonw.exe" set "PYTHONW=D:\python310\pythonw.exe"
    if exist "C:\python310\pythonw.exe" set "PYTHONW=C:\python310\pythonw.exe"
    if exist "C:\Python310\pythonw.exe" set "PYTHONW=C:\Python310\pythonw.exe"
    if exist "C:\Program Files\Python310\pythonw.exe" set "PYTHONW=C:\Program Files\Python310\pythonw.exe"
)

:: Start backend
echo Starting backend...
start "" /b "%PYTHONW%" backend\run.py

:: Start frontend (VBS hidden window)
echo Starting frontend...
echo Set WshShell = CreateObject("WScript.Shell") > %temp%\fe.vbs
echo WshShell.Run "cmd /c cd /d """"%~dp0frontend"""" && npm run dev", 0, False >> %temp%\fe.vbs
cscript //nologo %temp%\fe.vbs
del %temp%\fe.vbs

:: Wait, then open browser
echo Opening browser...
timeout /t 5 >nul
start http://localhost:5173/

echo Done!
timeout /t 2 >nul
exit
