' TaskM Backend Auto-Start (full)
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "D:\python310\pythonw.EXE ""D:\Desktop\Projects\git\TaskM\backend\run.py""", 0, False
WScript.Sleep 8000
WshShell.Run "http://localhost:5173/", 1, False
