Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")
strPath = objFSO.GetParentFolderName(WScript.ScriptFullName)
strPythonPath = strPath & "\python\python.exe"
strScriptPath = strPath & "\y1_updater.py"

If objFSO.FileExists(strPythonPath) Then
    If objFSO.FileExists(strScriptPath) Then
        objShell.Run """" & strPythonPath & """ """ & strScriptPath & """", 1, False
    Else
        MsgBox "y1_updater.py not found in current directory.", 16, "Error"
    End If
Else
    MsgBox "Python executable not found at: " & strPythonPath, 16, "Error"
End If 