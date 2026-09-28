Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")
appRoot = fso.GetParentFolderName(WScript.ScriptFullName)
exePath = fso.BuildPath(appRoot, "live\app\Engel.exe")
Set procEnv = WshShell.Environment("PROCESS")
memoryRoot = "F:\ENGEL_APP_MEMORY"
If Not fso.DriveExists("F:") Then
    memoryRoot = fso.BuildPath(appRoot, "runtime\engel_memory")
End If
If Not fso.FolderExists(memoryRoot) Then fso.CreateFolder(memoryRoot)
If Not fso.FolderExists(fso.BuildPath(memoryRoot, "engel-home")) Then fso.CreateFolder(fso.BuildPath(memoryRoot, "engel-home"))
If Not fso.FolderExists(fso.BuildPath(memoryRoot, "runpod")) Then fso.CreateFolder(fso.BuildPath(memoryRoot, "runpod"))
If Not fso.FolderExists(fso.BuildPath(memoryRoot, "secrets")) Then fso.CreateFolder(fso.BuildPath(memoryRoot, "secrets"))
If procEnv("ENGEL_HOME") = "" Then procEnv("ENGEL_HOME") = fso.BuildPath(memoryRoot, "engel-home")
If procEnv("ENGEL_RUNPOD_ROOT") = "" Then procEnv("ENGEL_RUNPOD_ROOT") = fso.BuildPath(memoryRoot, "runpod")
If procEnv("ENGEL_RUNPOD_API_KEY_FILE") = "" Then procEnv("ENGEL_RUNPOD_API_KEY_FILE") = fso.BuildPath(memoryRoot, "secrets\runpod_api_key.txt")
WshShell.Run Chr(34) & exePath & Chr(34), 1, False
