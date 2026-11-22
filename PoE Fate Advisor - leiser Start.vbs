Option Explicit
Dim shell, fso, folder, pyw, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = folder
pyw = fso.BuildPath(folder, ".venv\Scripts\pythonw.exe")
If fso.FileExists(pyw) And fso.FileExists(fso.BuildPath(folder, ".venv\.dependencies-v13")) Then
    command = Chr(34) & pyw & Chr(34) & " " & Chr(34) & fso.BuildPath(folder, "app.py") & Chr(34)
    shell.Run command, 0, False
Else
    shell.Run Chr(34) & fso.BuildPath(folder, "start_windows.bat") & Chr(34), 1, False
End If
