' TaskM Auto-Start (both services with browser)
Set WshShell = CreateObject("WScript.Shell")
' Start backend
WshShell.Run "D:\python310\pythonw.EXE ""D:\Desktop\Projects\git\TaskM\backend\run.py""", 0, False
' Start frontend
WshShell.Run "cmd /c cd /d ""D:\Desktop\Projects\git\TaskM\frontend"" && ""D:\Node\npx.cmd"" vite", 0, False
' Wait for services to be ready
WScript.Sleep 10000
' Open browser
WshShell.Run "http://localhost:5173/", 1, False
