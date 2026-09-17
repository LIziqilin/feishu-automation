' run_hidden.vbs - hidden launcher for scheduled tasks (fix: ASCII only, no encoding issues)
' Usage: wscript.exe run_hidden.vbs "<exe path>" "<arg1>" [arg2 ...]
' Window mode 0 = completely hidden console
Set sh = CreateObject("WScript.Shell")
If WScript.Arguments.Count < 2 Then
    WScript.Quit 1
End If
cmd = """" & WScript.Arguments(0) & """"
For i = 1 To WScript.Arguments.Count - 1
    cmd = cmd & " """ & WScript.Arguments(i) & """"
Next
sh.Run cmd, 0, False
