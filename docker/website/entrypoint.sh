#!/bin/bash
# Pelican entrypoint für die Node.js-Website
cd /home/container || exit 1

INTERNAL_IP=$(ip route get 1 2>/dev/null | awk '{print $(NF-2);exit}')
export INTERNAL_IP

echo -e "\033[1m\033[36m[pelican]\033[0m Node.js $(node -v) | npm $(npm -v)"

# Optionales Auto-Update aus dem Git-Repository (Egg-Variable AUTO_UPDATE=1)
if [[ "${AUTO_UPDATE}" == "1" && -n "${GIT_REPO}" ]]; then
    echo -e "\033[1m\033[36m[pelican]\033[0m Auto-Update aus ${GIT_REPO} (${GIT_BRANCH:-main}) ..."
    rm -rf /tmp/src
    if git clone --quiet --depth 1 --branch "${GIT_BRANCH:-main}" "${GIT_REPO}" /tmp/src; then
        if [[ -d "/tmp/src/${GIT_SUBDIR}" ]]; then
            cp -r "/tmp/src/${GIT_SUBDIR}/." /home/container/
            echo -e "\033[1m\033[36m[pelican]\033[0m Update abgeschlossen."
        else
            echo -e "\033[1m\033[33m[pelican]\033[0m Unterordner '${GIT_SUBDIR}' nicht im Repository gefunden."
        fi
    else
        echo -e "\033[1m\033[33m[pelican]\033[0m Auto-Update fehlgeschlagen, starte mit vorhandenen Dateien."
    fi
    rm -rf /tmp/src
fi

# Node-Abhängigkeiten installieren/aktualisieren
if [[ -f package.json ]]; then
    echo -e "\033[1m\033[36m[pelican]\033[0m Installiere Abhängigkeiten (npm) ..."
    npm install --omit=dev --no-audit --no-fund --loglevel=error \
        || echo -e "\033[1m\033[33m[pelican]\033[0m npm install fehlgeschlagen."
fi

# Startbefehl aus dem Egg ({{VAR}} -> ${VAR}) auflösen und ausführen
PARSED=$(echo "${STARTUP}" | sed -e 's/{{/${/g' -e 's/}}/}/g' | eval echo "$(cat -)")
printf "\033[1m\033[33mcontainer@pelican~ \033[0m%s\n" "${PARSED}"

exec /bin/bash -c "${PARSED}"
