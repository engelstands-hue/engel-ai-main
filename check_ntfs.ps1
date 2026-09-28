$acl = Get-Acl 'D:\b.WorkSpace'
$acl.Access | Format-Table IdentityReference, FileSystemRights, AccessControlType -AutoSize