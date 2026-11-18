#!/bin/bash
# Startet Discord-Bot und Website parallel im selben Pelican-Server.
# Beendet sich ein Dienst, werden alle gestoppt – so erkennt Pelican Abstürze.
# Stop (^C / SIGINT / SIGTERM) wird an beide Dienste weitergereicht.

# Job-Control: jeder Dienst bekommt eine eigene Prozessgruppe und SIGINT wird
# für Hintergrundprozesse nicht ignoriert.
set -m

ROOT=/home/container
pids=()
names=()

log() { echo -e "\033[1m\033[35m[stack]\033[0m $*"; }

start_service() {
    local name=$1 dir=$2
    shift 2
    if [[ ! -d "${ROOT}/${dir}" ]]; then
        log "Ordner '${dir}' fehlt – ${name} wird nicht gestartet (Server neu installieren?)."
        return
    fi
    (cd "${ROOT}/${dir}" && exec "$@") &
    pids+=("$!")
    names+=("${name}")
    log "${name} gestartet (PID $!)"
}

stop_all() {
    local signal=${1:-INT}
    for pid in "${pids[@]}"; do
        kill -s "${signal}" "${pid}" 2>/dev/null
    done
}

shutdown() {
    log "Stoppe Dienste ..."
    stop_all INT
    wait
    log "Alle Dienste beendet."
    exit 0
}
trap shutdown INT TERM

if [[ "${ENABLE_WEBSITE:-1}" == "1" ]]; then
    start_service "Website" website node "${WEBSITE_FILE:-server.js}"
fi
if [[ "${ENABLE_BOT:-1}" == "1" ]]; then
    start_service "Bot" bot python "${BOT_FILE:-main.py}"
fi

if (( ${#pids[@]} == 0 )); then
    log "Weder Bot noch Website aktiviert (ENABLE_BOT / ENABLE_WEBSITE)."
    exit 1
fi

wait -n "${pids[@]}"
code=$?
log "Ein Dienst wurde beendet (Exit-Code ${code}) – stoppe alle Dienste ..."
stop_all INT
sleep 5
stop_all KILL
wait
exit "${code}"
