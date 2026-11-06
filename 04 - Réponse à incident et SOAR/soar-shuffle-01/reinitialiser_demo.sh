#!/bin/bash
# Sur l'hôte Proxmox : remet c_dupont / c.dupont en état après une démo du playbook Shuffle.
set -euo pipefail
pct exec 210 -- /usr/local/sbin/soar-verrou-db.sh c_dupont deverrouiller
echo 'Enable-ADAccount -Identity c.dupont; "AD c.dupont actif : " + (Get-ADUser c.dupont).Enabled' > /tmp/reactiver.ps1
/root/winrun.sh 201 /tmp/reactiver.ps1 120 | grep -v '^$'
rm -f /tmp/reactiver.ps1
