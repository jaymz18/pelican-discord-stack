-- Database schema for pelican-discord-stack
-- Created automatically when the bot starts (CREATE TABLE IF NOT EXISTS).
-- The website reads the same tables.

CREATE TABLE IF NOT EXISTS guilds (
    guild_id           BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    name               VARCHAR(100)    NOT NULL,
    icon_url           VARCHAR(255)    NULL,
    member_count       INT UNSIGNED    NOT NULL DEFAULT 0,
    welcome_channel_id BIGINT UNSIGNED NULL,
    welcome_message    VARCHAR(500)    NULL,
    log_channel_id     BIGINT UNSIGNED NULL,
    active             TINYINT(1)      NOT NULL DEFAULT 1,
    joined_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS levels (
    guild_id   BIGINT UNSIGNED NOT NULL,
    user_id    BIGINT UNSIGNED NOT NULL,
    username   VARCHAR(100)    NOT NULL,
    avatar_url VARCHAR(255)    NULL,
    xp         INT UNSIGNED    NOT NULL DEFAULT 0,
    level      INT UNSIGNED    NOT NULL DEFAULT 0,
    messages   INT UNSIGNED    NOT NULL DEFAULT 0,
    last_xp_at DATETIME        NULL,
    PRIMARY KEY (guild_id, user_id),
    INDEX idx_levels_xp (guild_id, xp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS warnings (
    id           INT UNSIGNED    NOT NULL AUTO_INCREMENT PRIMARY KEY,
    guild_id     BIGINT UNSIGNED NOT NULL,
    user_id      BIGINT UNSIGNED NOT NULL,
    moderator_id BIGINT UNSIGNED NOT NULL,
    reason       VARCHAR(500)    NOT NULL,
    created_at   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_warnings_user (guild_id, user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS command_log (
    id       BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    guild_id BIGINT UNSIGNED NULL,
    user_id  BIGINT UNSIGNED NOT NULL,
    command  VARCHAR(100)    NOT NULL,
    used_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_command_log_time (used_at),
    INDEX idx_command_log_cmd (command)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS member_events (
    id         BIGINT UNSIGNED       NOT NULL AUTO_INCREMENT PRIMARY KEY,
    guild_id   BIGINT UNSIGNED       NOT NULL,
    user_id    BIGINT UNSIGNED       NOT NULL,
    username   VARCHAR(100)          NOT NULL,
    event      ENUM('join', 'leave') NOT NULL,
    created_at DATETIME              NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_member_events_guild (guild_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS bot_status (
    id             TINYINT UNSIGNED NOT NULL PRIMARY KEY,
    bot_name       VARCHAR(100)     NOT NULL,
    bot_avatar     VARCHAR(255)     NULL,
    guild_count    INT UNSIGNED     NOT NULL DEFAULT 0,
    user_count     INT UNSIGNED     NOT NULL DEFAULT 0,
    latency_ms     INT UNSIGNED     NULL,
    started_at     DATETIME         NOT NULL,
    last_heartbeat DATETIME         NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS bot_commands (
    name             VARCHAR(100)     NOT NULL PRIMARY KEY,
    category         VARCHAR(50)      NOT NULL,
    description      VARCHAR(200)     NOT NULL,
    options          TEXT             NULL,
    permissions      VARCHAR(200)     NULL,
    guild_only       TINYINT(1)       NOT NULL DEFAULT 0,
    prefix_supported TINYINT(1)       NOT NULL DEFAULT 0,
    sort_order       INT UNSIGNED     NOT NULL DEFAULT 0,
    updated_at       DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Leveling v2 (migration for existing installs, MariaDB syntax)
ALTER TABLE levels ADD COLUMN IF NOT EXISTS voice_minutes INT UNSIGNED NOT NULL DEFAULT 0 AFTER messages;

CREATE TABLE IF NOT EXISTS level_settings (
    guild_id            BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    announce            TINYINT(1)      NOT NULL DEFAULT 1,
    announce_channel_id BIGINT UNSIGNED NULL,
    levelup_message     VARCHAR(500)    NULL,
    xp_multiplier       DECIMAL(4, 2)   NOT NULL DEFAULT 1.00,
    voice_xp            TINYINT(1)      NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS level_rewards (
    guild_id BIGINT UNSIGNED NOT NULL,
    level    INT UNSIGNED    NOT NULL,
    role_id  BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (guild_id, level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS level_ignored_channels (
    guild_id   BIGINT UNSIGNED NOT NULL,
    channel_id BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (guild_id, channel_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
