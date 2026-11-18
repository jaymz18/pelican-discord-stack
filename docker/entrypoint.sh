#!/bin/bash
# Pelican entrypoint für pelican-discord-stack (Bot + Website in einem Server)
cd /home/container || exit 1

INTERNAL_IP=$(ip route get 1 2>/dev/null | awk '{print $(NF-2);exit}')
export INTERNAL_IP

info() { echo -e "\033[1m\033[36m[pelican]\033[0m $*"; }
warn() { echo -e "\033[1m\033[33m[pelican]\033[0m $*"; }

info "$(python --version 2>&1) | Node.js $(node -v) | npm $(npm -v)"

# Optionales Auto-Update aus dem Git-Repository (Egg-Variable AUTO_UPDATE=1)
if [[ "${AUTO_UPDATE}" == "1" && -n "${GIT_REPO}" ]]; then
    info "Auto-Update aus ${GIT_REPO} (${GIT_BRANCH:-main}) ..."
    rm -rf /tmp/src
    if git clone --quiet --depth 1 --branch "${GIT_BRANCH:-main}" "${GIT_REPO}" /tmp/src; then
        for dir in bot website; do
            if [[ -d "/tmp/src/${dir}" ]]; then
                mkdir -p "/home/container/${dir}"
                cp -r "/tmp/src/${dir}/." "/home/container/${dir}/"
            fi
        done
        info "Update abgeschlossen."
    else
        warn "Auto-Update fehlgeschlagen, starte mit vorhandenen Dateien."
    fi
    rm -rf /tmp/src
fi

# Abhängigkeiten installieren/aktualisieren
if [[ "${ENABLE_BOT:-1}" == "1" && -f bot/requirements.txt ]]; then
    info "Installiere Python-Abhängigkeiten (bot/requirements.txt) ..."
    pip install --user --quiet --no-warn-script-location -r bot/requirements.txt \
        || warn "pip install fehlgeschlagen."
fi
if [[ "${ENABLE_WEBSITE:-1}" == "1" && -f website/package.json ]]; then
    info "Installiere Node-Abhängigkeiten (website/package.json) ..."
    (cd website && npm install --omit=dev --no-audit --no-fund --loglevel=error) \
        || warn "npm install fehlgeschlagen."
fi

# Startbefehl aus dem Egg ({{VAR}} -> ${VAR}) auflösen und ausführen
PARSED=$(echo "${STARTUP}" | sed -e 's/{{/${/g' -e 's/}}/}/g' | eval echo "$(cat -)")
printf "\033[1m\033[33mcontainer@pelican~ \033[0m%s\n" "${PARSED}"

exec /bin/bash -c "${PARSED}"
