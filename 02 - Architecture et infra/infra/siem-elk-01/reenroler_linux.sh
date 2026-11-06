#!/bin/bash
# Réenrôle les agents des LXC (déjà installés, enrôlés dans le Fleet cloud) vers le Fleet on-prem.
# À lancer sur l'hôte Proxmox. Prérequis dans /root/soc-enroll :
#   soc-ca.crt   certificat de la CA du SOC (copie de /root/elastic/pki/ca/ca.crt sur siem-elk-01)
#   tokens.txt   lignes « <id de politique> <jeton d'enrôlement> » (Fleet > Enrollment tokens)
# Usage : reenroler_linux.sh 210:<id pol-linux-db> 211:<id pol-linux-web> 212:<id pol-linux-bastion>
set -euo pipefail
FLEET=https://10.40.0.10:8220
D=/root/soc-enroll
for arg in "$@"; do
  ct=${arg%%:*}; pol=${arg#*:}
  tok=$(awk -v p="$pol" '$1==p{print $2}' $D/tokens.txt)
  [ -n "$tok" ] || { echo "pas de jeton pour $pol"; exit 1; }
  echo "== CT $ct -> politique $pol"
  pct exec "$ct" -- mkdir -p /etc/azurbank-ca
  pct push "$ct" $D/soc-ca.crt /etc/azurbank-ca/soc-ca.crt --perms 644
  # enroll sur un agent déjà installé : il quitte l'ancien Fleet et rejoint le nouveau (--force : sans question)
  pct exec "$ct" -- elastic-agent enroll --url="$FLEET" --enrollment-token="$tok" \
      --certificate-authorities=/etc/azurbank-ca/soc-ca.crt --force
  sleep 5
  pct exec "$ct" -- elastic-agent status | head -5
done
