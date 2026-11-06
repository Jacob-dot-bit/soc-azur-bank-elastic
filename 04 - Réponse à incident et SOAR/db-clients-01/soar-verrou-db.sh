#!/bin/bash
# Action SOAR (appelée par Shuffle en SSH, compte svc-shuffle, via sudo) :
# verrouille un rôle PostgreSQL et coupe ses sessions.
# Usage : soar-verrou-db.sh <role>                 -> NOLOGIN + sessions coupées
#         soar-verrou-db.sh <role> deverrouiller   -> LOGIN (fin d'incident)
set -euo pipefail
role=${1:-}
[[ "$role" =~ ^[a-z][a-z0-9_]{1,30}$ ]] || { echo "role invalide"; exit 2; }
case "$role" in postgres|svc_*) echo "role protege : $role"; exit 3;; esac
cd /
if [ "${2:-}" = "deverrouiller" ]; then
  su postgres -c "psql -qAt -c \"ALTER ROLE $role LOGIN;\""
  logger -t soar "role PostgreSQL $role deverrouille"
  echo "role $role deverrouille"; exit 0
fi
n=$(su postgres -c "psql -qAt -c \"ALTER ROLE $role NOLOGIN;\" -c \"SELECT count(pg_terminate_backend(pid)) FROM pg_stat_activity WHERE usename = '$role';\"" | tail -1)
logger -t soar "role PostgreSQL $role verrouille par Shuffle ($n session(s) coupee(s))"
echo "role $role verrouille (NOLOGIN), $n session(s) coupee(s)"
