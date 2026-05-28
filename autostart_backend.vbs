' TaskM Auto-Start (both services, no browser)
Set WshShell = CreateObject("WScript.Shell")
' Start backend
WshShell.Run "D:\python310\pythonw.EXE ""D:\Desktop\Projects\git\TaskM\backend\run.py""", 0, False
' Start frontend
WshShell.Run "cmd /c cd /d ""D:\Desktop\Projects\git\TaskM\frontend"" && ""D:\Node\npx.cmd"" vite", 0, False
