# Engel Startup Policy

## Safe Startup Order

1. Proxmox host `engel-spine-01` starts.
2. Confirm network spine is stable.
3. Confirm iSCSI session to PowerVault target `192.168.130.101:3260`.
4. Confirm `engel-vault-main` storage active.
5. Confirm CT 246 `engel-ai-main` starts.
6. Confirm `/opt/engel` fast runtime path.
7. Confirm `/mnt/engel-vault` exists/mounts before vault-dependent work.
8. Start Engel runtime only after storage and health checks pass.
9. ROG Queen connects UI/tunnels only after CT body is healthy.
10. Worker devices join only after explicit device health checks and approval.

## Boot Restrictions

- No autonomous swarms at boot.
- No uncontrolled loops at boot.
- No heavy worker startup without ROG/Josh approval.
- No destructive repair actions at boot.
- No automatic migration at boot.
- No PowerVault/iSCSI/multipath mutation at boot.
- No model training or GPU work at boot unless explicitly approved.

## Heavy Work Policy

Heavy workers require:

- Josh approval.
- ROG orchestration.
- Known device identity.
- Work scope.
- Stop condition.
- Receipt/log target.
- Health check before and after.

## Emergency Stop

ROG is the emergency fallback. If Engel runtime, CT, or workers behave unexpectedly, stop through the ROG control path and pause worker dispatch until Josh reviews state.

