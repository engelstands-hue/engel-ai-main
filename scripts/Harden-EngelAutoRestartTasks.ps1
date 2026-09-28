# Harden-EngelAutoRestartTasks.ps1  (2026-07-09 audit follow-up)
#
# Root cause of the 07-09 04:35 outage: EngelRogGpuModelServer / EngelRogGpuTunnel /
# EngelMainServerPersistentLink had ONLY a logon trigger, so anything that killed them
# mid-session (sleep, shutdown, 0xC000013A) left the whole GPU+bridge tier dead until
# the next logon.
#
# This script gives every Engel service task the same durable shape:
#   - triggers : AtLogOn  +  keep-alive (repeats every 5 min forever; with
#                MultipleInstances=IgnoreNew a live process makes it a no-op,
#                a dead one relaunches within <=5 min — survives sleep/kill/reboot)
#   - settings : AllowStartIfOnBatteries, Dont