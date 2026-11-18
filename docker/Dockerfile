# Pelican-/Pterodactyl-kompatibles Runtime-Image für Discord-Bot (Python) UND Website (Node.js)
FROM node:24-bookworm-slim AS node

FROM python:3.13-slim-bookworm

LABEL org.opencontainers.image.description="Pelican runtime image for pelican-discord-stack: Python Discord bot + Node.js website"
LABEL org.opencontainers.image.licenses="MIT"

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl git iproute2 libstdc++6 tini tzdata \
 && rm -rf /var/lib/apt/lists/* \
 && useradd -m -d /home/container -s /bin/bash container

# Node.js + npm aus dem offiziellen Node-Image übernehmen (beide basieren auf Debian bookworm)
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
 && node --version && npm --version

COPY entrypoint.sh /entrypoint.sh
COPY start-stack.sh /usr/local/bin/start-stack
RUN sed -i 's/\r$//' /entrypoint.sh /usr/local/bin/start-stack \
 && chmod +x /entrypoint.sh /usr/local/bin/start-stack

USER container
ENV USER=container \
    HOME=/home/container \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    NODE_ENV=production \
    NPM_CONFIG_UPDATE_NOTIFIER=false \
    NPM_CONFIG_FUND=false \
    NPM_CONFIG_AUDIT=false \
    PATH=/home/container/.local/bin:$PATH
WORKDIR /home/container

STOPSIGNAL SIGINT
ENTRYPOINT ["/usr/bin/tini", "-g", "--"]
CMD ["/entrypoint.sh"]
