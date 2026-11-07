#!/usr/bin/env bash
set -euo pipefail
umask 077
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

case "${RESTIC_REPOSITORY:-}" in
    s3:*|sftp:*|rest:https://*|b2:*|azure:*|gs:*) ;;
    *) printf '%s\n' 'Set RESTIC_REPOSITORY to the approved off-site backup destination.' >&2; exit 1 ;;
esac

compose=(docker compose --env-file .env -f compose.yaml)
state=$(mktemp -d)
stopped=0
cleanup() {
    local status=$?
    if (( stopped )); then
        "${compose[@]}" start odoo || status=1
    fi
    rm -rf -- "$state"
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
exec 9> .backup.lock
flock -n 9

# Quiesce all application writers while taking a consistent database/filestore pair.
stopped=1
"${compose[@]}" stop odoo
"${compose[@]}" exec -T db sh -ec 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -U postgres -Fc field_crm' > "$state/database.dump"
"${compose[@]}" run --rm --no-deps -T --entrypoint tar odoo \
    -C /var/lib/odoo -cf - filestore/field_crm > "$state/filestore.tar"
"${compose[@]}" start odoo
stopped=0

(cd "$state" && restic backup --tag field-crm database.dump filestore.tar)
