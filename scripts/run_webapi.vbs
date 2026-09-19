' run_webapi.vbs — 无窗口启动 webapi 常驻服务（开机自启用）
' 读 webapi_secrets.env 设环境变量，再用 pythonw 静默启动 webapi.py
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dir

envPath = dir & "\webapi_secrets.env"
If fso.FileExists(envPath) Then
  Set f = fso.OpenTextFile(envPath, 1)
  Do Until f.AtEndOfStream
    line = Trim(f.ReadLine)
    If InStr(line, "=") > 0 And Left(line, 1) <> "#" Then
      k = Trim(Left(line, InStr(line, "=") - 1))
      v = Trim(Mid(line, InStr(line, "=") + 1))
      sh.Environment("Process")(k) = v
    End If
  Loop
  f.Close
End If

pyw = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\pythonw.exe"
cmd = """" & pyw & """ """ & dir & "\webapi.py"" --port 8765"
sh.Run cmd, 0, False
