' TaskM Backend Auto-Start (backend only)
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "D:\python310\pythonw.EXE ""D:\Desktop\Projects\git\TaskM\backend\run.py""", 0, False
