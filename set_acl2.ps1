$acl = Get-Acl "D:\b.WorkSpace"
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("Everyone","Modify","ContainerInherit,ObjectInherit","None","Allow")
$acl.AddAccessRule($rule)
Set-Acl "D:\b.WorkSpace" $acl
Write-Host "OK"