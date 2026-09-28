@echo off
echo Creating EngelWorkspace share...
net share EngelWorkspace=D:\b.WorkSpace /GRANT:Everyone,FULL /REMARK:"Engel shared workspace"
if %errorlevel% equ 0 (
  echo Share created successfully.
  echo ENGEL_SHARE_SETUP_SUCCESS %date% %time% > D:\b.WorkSpace\_engel_share_setup_result.txt
  echo Share path: D:\b.WorkSpace >> D:\b.WorkSpace\_engel_share_setup_result.txt
  echo Network path: \%COMPUTERNAME%\EngelWorkspace >> D:\b.WorkSpace\_engel_share_setup_result.txt
) else (
  echo Failed to create share. Error: %errorlevel%
  echo ENGEL_SHARE_SETUP_FAILED %date% %time% > D:\b.WorkSpace\_engel_share_setup_result.txt
  echo Error code: %errorlevel% >> D:\b.WorkSpace\_engel_share_setup_result.txt
)
pause