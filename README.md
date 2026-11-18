# pelican-discord-stack

Ein Discord-Bot in **Python** und ein Web-Dashboard in **Node.js**, die sich eine **MariaDB** teilen. Beide laufen zusammen in **einem** Pelican-Server, gestartet aus **einem** Docker-Image mit **einem** Egg. GitHub Actions baut das Image automatisch und pusht es in die GitHub Container Registry (GHCR).

[![Docker Image](https://github.com/jaymz18/pelican-discord-stack/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/jaymz18/pelican-discord-stack/actions/workflows/docker-publish.yml)
[![CI](https://github.com/jaymz18/pelican-discord-stack/actions/workflows/ci.yml/badge.svg)](https://github.com/jaymz18/pelican-discord-stack/actions/workflows/ci.yml)

```
┌──────────────── Pelican-Server (Egg: Discord Bot + Website) ───────────────┐
│                                                                            │
│   ┌────────────────┐                          ┌──────────────────────┐     │
│   │ Discord-Bot    │                          │ Website (Node.js)    │     │
│   │ bot/ (Python)  │                          │ website/ · Port      │     │
│   └───────┬────────┘                          └──────────┬───────────┘     │
└───────────┼──────────────────────────────────────────────┼─────────────────┘
            │ schreibt          ┌───────────┐       liest  │
            └─────────────────▶ │  MariaDB  │ ◀────────────┘
                                │ (Pelican  │
                                │ Database) │
                                └───────────┘
```

## Inhalt

| Pfad | Beschreibung |
|---|---|
| `docker/Dockerfile` | Image mit Python 3.13 **und** Node.js 24 |
| `docker/entrypoint.sh` | Pelican-Entrypoint: Auto-Update, Abhängigkeiten, Startbefehl |
| `docker/start-stack.sh` | Startet Bot und Website parallel (im Image als `start-stack`) |
| `eggs/egg-discord-stack.json` | Das Pelican-Egg |
| `bot/` | Quellcode des Discord-Bots |
| `website/` | Quellcode der Website |
| `.github/workflows/docker-publish.yml` | Baut das Image und pusht es nach GHCR (amd64 + arm64) |
| `.github/workflows/ci.yml` | Prüft das Egg sowie Python- und JS-Code |
| `docker-compose.yml` | Lokale Entwicklungsumgebung inkl. MariaDB |

## Docker-Image

```
ghcr.io/jaymz18/pelican-discord-stack:latest
```

Das Image basiert auf `python:3.13-slim-bookworm`. Node.js 24 und npm werden aus dem offiziellen Image `node:24-bookworm-slim` übernommen. Es ist Pelican-kompatibel: Benutzer `container`, Arbeitsverzeichnis `/home/container`, `tini` als Init-Prozess und `STOPSIGNAL SIGINT`.

Beim Start passiert Folgendes:

1. Ist `AUTO_UPDATE=1` gesetzt, werden `bot/` und `website/` aus `GIT_REPO`/`GIT_BRANCH` aktualisiert.
2. Die Abhängigkeiten werden installiert (`pip install --user -r bot/requirements.txt` und `npm install` in `website/`).
3. `start-stack` startet die Website (`node website/server.js`) und den Bot (`python bot/main.py`) parallel.
   - Mit `ENABLE_BOT` bzw. `ENABLE_WEBSITE` lässt sich jeder Dienst abschalten.
   - Beendet sich einer der beiden Dienste, stoppt `start-stack` auch den anderen. So erkennt Pelican einen Absturz.
   - Der Stop-Befehl aus Pelican (`^C`) wird an beide Dienste weitergereicht, die dann sauber herunterfahren.

### Workflow → GitHub Container Registry

`.github/workflows/docker-publish.yml` baut das Image und pusht es nach `ghcr.io/<owner>/pelican-discord-stack`. Die Anmeldung läuft über den eingebauten `GITHUB_TOKEN`, Secrets sind nicht nötig. Der Workflow läuft:

- bei jedem Push auf `main`, der etwas unter `docker/` ändert → Tag `latest` und `sha-xxxxxxx`
- bei Git-Tags `v*` (z. B. `v1.2.0`) → zusätzlich die Tags `1.2.0` und `1.2`
- jeden Montag (Rebuild für Sicherheitsupdates der Basis-Images)
- bei manuellem Start (*Actions → Docker Image → Run workflow*)
- bei Pull Requests: Das Image wird nur gebaut, nicht gepusht.

## Installation in Pelican

### 1. Egg importieren
Im Admin-Bereich unter **Eggs → Import** das Egg per URL importieren:

```
https://raw.githubusercontent.com/jaymz18/pelican-discord-stack/main/eggs/egg-discord-stack.json
```

Das Egg liegt im Format `PTDL_v2` vor, das Pelican direkt importiert. Über die hinterlegte `update_url` lässt es sich später im Panel aktualisieren.

### 2. Database Host einrichten (einmalig)
Unter **Admin → Database Hosts** einen MariaDB-Server eintragen. Läuft MariaDB auf dem Node selbst, ist der Container über das Docker-Gateway erreichbar, meist `172.18.0.1`. MariaDB muss dafür auf dieser Adresse lauschen (`bind-address`).

### 3. Server erstellen
1. Einen Server mit dem Egg *Discord Bot + Website* anlegen. Die Allocation (der Port) ist der Port der Website.
2. Im Server-Tab **Datenbanken** eine neue Datenbank erstellen.
3. Unter **Startup** den `DISCORD_TOKEN` und die Datenbank-Zugangsdaten eintragen: `DB_HOST`, `DB_PORT`, `DB_DATABASE`, `DB_USERNAME` und `DB_PASSWORD`.
4. Den Server starten. Die Tabellen legt der Bot beim ersten Start automatisch an.

Nach der Installation liegt der Code auf dem Server in `bot/` und `website/`.

### Egg-Variablen

| Gruppe | Variablen |
|---|---|
| Dienste | `ENABLE_BOT`, `ENABLE_WEBSITE` (jeweils `1`/`0`) |
| Bot | `DISCORD_TOKEN`, `DEV_GUILD_ID` (optional, synchronisiert Slash-Commands sofort auf einem Test-Server), `BOT_PREFIX`, `LOG_LEVEL`, `BOT_FILE` |
| Website | `SITE_TITLE`, `BOT_INVITE_URL`, `SITE_TIMEZONE`, `WEBSITE_FILE`. Den Port stellt Pelican über `SERVER_PORT` bereit. |
| Datenbank | `DB_HOST`, `DB_PORT`, `DB_DATABASE`, `DB_USERNAME`, `DB_PASSWORD` |
| Updates | `GIT_REPO`, `GIT_BRANCH`, `AUTO_UPDATE` |

## Discord-Bot einrichten

1. Im [Discord Developer Portal](https://discord.com/developers/applications) eine Anwendung erstellen und unter **Bot** den Token kopieren.
2. Unter **Privileged Gateway Intents** den **Server Members Intent** und den **Message Content Intent** aktivieren.
3. Den Bot über **OAuth2 → URL Generator** einladen. Scopes: `bot` und `applications.commands`. Berechtigungen: *Send Messages*, *Embed Links*, *Add Reactions*, *Read Message History*, *Manage Messages*, *Kick Members* und *Moderate Members*.

### Commands

| Kategorie | Befehle |
|---|---|
| Allgemein (Slash **und** Prefix, z. B. `!ping`) | `/ping`, `/help`, `/serverinfo`, `/userinfo`, `/avatar`, `/botinfo` |
| Level-System | `/rank`, `/leaderboard` |
| Moderation | `/warn`, `/warnings`, `/clearwarnings`, `/kick`, `/timeout`, `/purge` |
| Fun | `/roll`, `/coinflip`, `/8ball`, `/poll` |
| Einstellungen | `/setup welcome`, `/setup welcome-message`, `/setup logs`, `/setup disable`, `/setup show` |

### Events

| Event | Funktion |
|---|---|
| `on_ready` | Server in der DB registrieren, Status setzen |
| `on_message` | XP vergeben (Cooldown 60 s) und Level-Up melden |
| `on_member_join` / `on_member_remove` | Willkommensnachricht, Log-Eintrag, Join/Leave-Statistik |
| `on_message_delete` / `on_message_edit` | Log-Kanal |
| `on_guild_join` / `on_guild_remove` / `on_guild_update` | Server-Liste in der DB pflegen |
| `on_app_command_completion` / `on_command_completion` | Nutzungsstatistik der Commands |
| Heartbeat (alle 60 s) | Bot-Status für die Website |
| Fehler-Handler | Verständliche Fehlermeldungen bei fehlenden Rechten, Cooldowns usw. |

## Website

- **`/`**: Bot-Status (online/offline), Gesamtstatistiken, Server-Liste, beliebteste Befehle und letzte Aktivität
- **`/guild/:id`**: Leaderboard und Aktivität eines Servers
- **`/commands`**: Alle Befehle des Bots, gruppiert nach Kategorie, mit Optionen, benötigten Rechten und Nutzungszahlen. Der Bot schreibt die Liste bei jedem Start in die Tabelle `bot_commands`, neue Befehle erscheinen also automatisch.

Eine öffentliche JSON-API gibt es nicht.

## Datenbank

Das Schema steht in [`bot/schema.sql`](bot/schema.sql). Es enthält die Tabellen `guilds`, `levels`, `warnings`, `command_log`, `member_events`, `bot_status` und `bot_commands`. Der Bot legt sie beim Start automatisch an (`CREATE TABLE IF NOT EXISTS`). Alle Zeitstempel werden in UTC gespeichert. Die Website rechnet sie in `SITE_TIMEZONE` um.

## Lokale Entwicklung

```bash
docker compose up --build   # MariaDB + Website auf http://localhost:3000
```

Um zusätzlich den Bot zu starten, im Projektroot eine `.env` mit `DISCORD_TOKEN=...` und `ENABLE_BOT=1` anlegen.

Die Compose-Umgebung nutzt dasselbe Image und denselben `STARTUP`-Mechanismus (`start-stack`) wie Pelican.

## Lizenz

MIT
