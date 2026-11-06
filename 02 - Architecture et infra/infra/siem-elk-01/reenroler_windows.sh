#!/bin/bash
# Sur l'hôte Proxmox : réenrôle les agents Windows (VM 201 srv-dc01, 202 ws-agence) vers le Fleet on-prem.
# Usage : reenroler_windows.sh <id pol-windows> 201 202
set -euo pipefail
D=/root/soc-enroll
pol=$1; shift
tok=$(awk -v p="$pol" '$1==p{print $2}' $D/tokens.txt)
umask 077
python3 - "$tok" <<'EOF'
import sys
tok = sys.argv[1]
ca = open("/root/soc-enroll/soc-ca.crt").read().strip()
s = open("/root/soc-enroll/reenroler_windows.ps1").read().replace("__TOKEN__", tok).replace("__CA__", ca)
open("/root/soc-enroll/run-win.ps1", "w").write(s)
EOF
for vm in "$@"; do
  echo "== VM $vm"
  /root/winrun.sh "$vm" $D/run-win.ps1 300
done
rm -f $D/run-win.ps1
