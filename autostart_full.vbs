' TaskM Auto-Start (both services with browser)
Set WshShell = CreateObject("WScript.Shell")
' Start backend
WshShell.Run "C:\Users\zhk\.workbuddy\binaries\python\versions\3.13.12\pythonw.EXE ""D:\Desktop\Projects\git\TaskM\backend\run.py""", 0, False
' Start frontend
WshShell.Run "cmd /c cd /d ""D:\Desktop\Projects\git\TaskM\frontend"" && ""C:\Users\zhk\.workbuddy\binaries\node\versions\22.22.2\npx.cmd"" vite", 0, False
' Wait for services to be ready
WScript.Sleep 10000
' Open browser
WshShell.Run "http://localhost:5173/", 1, False
