# pelican-discord-stack

Ein Discord-Bot in **Python** und ein Web-Dashboard in **Node.js**. Beide nutzen eine gemeinsame **MariaDB**. Für beide gibt es ein **Docker-Image** und ein **Egg** für das [Pelican Panel](https://pelican.dev). Die Images baut GitHub Actions automatisch und veröffentlicht sie in der GitHub Container Registry (GHCR).

[![Docker Images](https://github.com/jaymz18/pelican-discord-stack/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/jaymz18/pelican-discord-stack/actions/workflows/docker-publish.yml)
[![CI](https://github.com/jaymz18/pelican-discord-stack/actions/workflows/ci.yml/badge.svg)](https://github.com/jaymz18/pelican-discord-stack/actions/workflows/ci.yml)

```
┌────────────────┐        ┌───────────┐        ┌──────────────────┐
│ Discord-Bot    │ ─────▶ │  MariaDB  │ ◀───── │ Website (Node.js)│
│ (discord.py)   │ schreibt│           │ liest  │ Express + EJS    │
└────────────────┘        └───────────┘        └──────────────────┘
   Pelican-Server            Pelican              Pelican-Server
   (Egg: Bot)              Database Host          (Egg: Website)
```

## Inhalt

| Pfad | Beschreibung |
|---|---|
| `docker/bot/` | Dockerfile + Entrypoint für das Bot-Image (Python 3.13) |
| `docker/website/` | Dockerfile + Entrypoint für das Website-Image (Node.js 24) |
| `eggs/egg-discord-bot.json` | Pelican-Egg für den Bot |
| `eggs/egg-website.json` | Pelican-Egg für die Website |
| `bot/` | Quellcode des Discord-Bots |
| `website/` | Quellcode der Website |
| `.github/workflows/docker-publish.yml` | Baut und pusht beide Images nach GHCR (amd64 + arm64) |
| `.github/workflows/ci.yml` | Prüft Eggs, Python- und JS-Code |
| `docker-compose.yml` | Lokale Entwicklungsumgebung inkl. MariaDB |

## Docker-Images

| Image | Basis |
|---|---|
| `ghcr.io/jaymz18/pelican-discord-stack-bot:latest` | `python:3.13-slim-bookworm` |
| `ghcr.io/jaymz18/pelican-discord-stack-website:latest` | `node:24-bookworm-slim` |

Die Images sind Pelican-kompatibel: Benutzer `container`, Arbeitsverzeichnis `/home/container`, `tini` als Init-Prozess und `STOPSIGNAL SIGINT`. Beim Start passiert Folgendes:

1. Ist `AUTO_UPDATE=1` gesetzt, wird der aktuelle Code aus `GIT_REPO`/`GIT_BRANCH` geholt.
2. Die Abhängigkeiten werden installiert (`pip install --user -r requirements.txt` bzw. `npm install`).
3. Der Startbefehl aus dem Egg (`STARTUP` mit `{{VARIABLEN}}`) wird aufgelöst und ausgeführt.

Neue Images entstehen bei jedem Push auf `main`, der etwas unter `docker/` ändert, außerdem einmal pro Woche (für Sicherheitsupdates der Basis-Images) und bei manuellem Start in GitHub Actions.

> **Wichtig:** Neue GHCR-Pakete sind zunächst **privat**. Stelle sie nach dem ersten Build einmal auf *Public*: GitHub → Profil → *Packages* → Paket → *Package settings* → *Change visibility*. Sonst kann Pelican die Images nicht ohne Zugangsdaten herunterladen.

## Installation in Pelican

### 1. Eggs importieren
Im Admin-Bereich unter **Eggs → Import** die Eggs per URL importieren:

```
https://raw.githubusercontent.com/jaymz18/pelican-discord-stack/main/eggs/egg-discord-bot.json
https://raw.githubusercontent.com/jaymz18/pelican-discord-stack/main/eggs/egg-website.json
```

Die Eggs liegen im Format `PTDL_v2` vor, das Pelican direkt importiert. Über die hinterlegte `update_url` lassen sie sich später im Panel aktualisieren.

### 2. Database Host einrichten (einmalig)
Unter **Admin → Database Hosts** einen MariaDB-Server eintragen. Läuft MariaDB auf dem Node selbst, ist der Container über das Docker-Gateway erreichbar, meist `172.18.0.1`. MariaDB muss dafür auf dieser Adresse lauschen (`bind-address`).

### 3. Server erstellen
1. **Bot-Server** mit dem Egg *Discord Bot (Python)* anlegen und den Discord-Token eintragen.
2. Im Server-Tab **Datenbanken** eine neue Datenbank erstellen.
3. Die angezeigten Zugangsdaten unter **Startup** eintragen: `DB_HOST`, `DB_PORT`, `DB_DATABASE`, `DB_USERNAME` und `DB_PASSWORD`.
4. **Website-Server** mit dem Egg *Bot Website (Node.js)* anlegen. Er braucht eine Allocation mit freiem Port. Dort **dieselben** Datenbank-Zugangsdaten eintragen, denn Bot und Website teilen sich die Datenbank.
5. Beide Server starten. Die Tabellen legt der Bot beim ersten Start automatisch an.

### Egg-Variablen

**Bot:** `DISCORD_TOKEN`, `DEV_GUILD_ID` (optional, synchronisiert Slash-Commands sofort auf einem Test-Server), `BOT_PREFIX`, `LOG_LEVEL`, `BOT_FILE`, `DB_*`, `GIT_REPO`, `GIT_BRANCH`, `AUTO_UPDATE`

**Website:** `SITE_TITLE`, `BOT_INVITE_URL`, `SITE_TIMEZONE`, `MAIN_FILE`, `DB_*`, `GIT_REPO`, `GIT_BRANCH`, `AUTO_UPDATE`. Den Port stellt Pelican über `SERVER_PORT` bereit.

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
- **API:** `/api/health`, `/api/stats`, `/api/guilds`, `/api/guilds/:id/leaderboard?limit=25`

## Datenbank

Das Schema steht in [`bot/schema.sql`](bot/schema.sql). Es enthält die Tabellen `guilds`, `levels`, `warnings`, `command_log`, `member_events` und `bot_status`. Der Bot legt sie beim Start automatisch an (`CREATE TABLE IF NOT EXISTS`). Alle Zeitstempel werden in UTC gespeichert. Die Website rechnet sie in `SITE_TIMEZONE` um.

## Lokale Entwicklung

```bash
docker compose up --build                 # MariaDB + Website auf http://localhost:3000
cp bot/.env.example bot/.env              # DISCORD_TOKEN eintragen
docker compose --profile bot up --build   # zusätzlich den Bot starten
```

Die Compose-Umgebung nutzt dieselben Images und denselben `STARTUP`-Mechanismus wie Pelican.

## Lizenz

MIT
