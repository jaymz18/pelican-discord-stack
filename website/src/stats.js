'use strict';

const db = require('./db');

const HEARTBEAT_TIMEOUT_MS = 3 * 60 * 1000;

async function getTotals() {
  const [row] = await db.query(
    `SELECT
       (SELECT COUNT(*) FROM guilds WHERE active = 1)      AS guilds,
       (SELECT COUNT(*) FROM levels)                       AS members,
       (SELECT COALESCE(SUM(messages), 0) FROM levels)     AS messages,
       (SELECT COUNT(*) FROM command_log)                  AS commands,
       (SELECT COUNT(*) FROM warnings)                     AS warnings`,
    [],
    [{}],
  );
  return {
    guilds: Number(row.guilds || 0),
    members: Number(row.members || 0),
    messages: Number(row.messages || 0),
    commands: Number(row.commands || 0),
    warnings: Number(row.warnings || 0),
  };
}

async function getBotStatus() {
  const [row] = await db.query('SELECT * FROM bot_status WHERE id = 1');
  if (!row) return { online: false, known: false };
  const last = new Date(row.last_heartbeat);
  return {
    known: true,
    online: Date.now() - last.getTime() < HEARTBEAT_TIMEOUT_MS,
    name: row.bot_name,
    avatar: row.bot_avatar,
    guildCount: row.guild_count,
    userCount: row.user_count,
    latency: row.latency_ms,
    startedAt: row.started_at,
    lastHeartbeat: last,
  };
}

function getGuilds(limit = 50) {
  return db.query(
    `SELECT g.guild_id, g.name, g.icon_url, g.member_count,
            (SELECT COUNT(*) FROM levels l WHERE l.guild_id = g.guild_id) AS tracked
       FROM guilds g
      WHERE g.active = 1
      ORDER BY g.member_count DESC
      LIMIT ?`,
    [limit],
  );
}

async function getGuild(guildId) {
  const [row] = await db.query(
    'SELECT guild_id, name, icon_url, member_count, joined_at FROM guilds WHERE guild_id = ? AND active = 1',
    [guildId],
  );
  return row || null;
}

function getTopCommands(limit = 8, days = 30) {
  return db.query(
    `SELECT command, COUNT(*) AS uses
       FROM command_log
      WHERE used_at >= UTC_TIMESTAMP() - INTERVAL ? DAY
      GROUP BY command
      ORDER BY uses DESC
      LIMIT ?`,
    [days, limit],
  );
}

function getRecentEvents(limit = 10, guildId = null) {
  const where = guildId ? 'WHERE e.guild_id = ?' : '';
  const params = guildId ? [guildId, limit] : [limit];
  return db.query(
    `SELECT e.event, e.username, e.created_at, g.name AS guild_name
       FROM member_events e
       LEFT JOIN guilds g ON g.guild_id = e.guild_id
       ${where}
      ORDER BY e.created_at DESC
      LIMIT ?`,
    params,
  );
}

function getLeaderboard(guildId, limit = 50) {
  return db.query(
    `SELECT user_id, username, avatar_url, xp, messages
       FROM levels
      WHERE guild_id = ?
      ORDER BY xp DESC
      LIMIT ?`,
    [guildId, limit],
  );
}

async function getCommands() {
  const rows = await db.query(
    `SELECT c.name, c.category, c.description, c.options, c.permissions,
            c.guild_only, c.prefix_supported, COALESCE(u.uses, 0) AS uses
       FROM bot_commands c
       LEFT JOIN (SELECT command, COUNT(*) AS uses FROM command_log GROUP BY command) u
              ON u.command = c.name
      ORDER BY c.sort_order, c.name`,
  );
  const categories = new Map();
  for (const row of rows) {
    let options = [];
    try {
      options = JSON.parse(row.options || '[]');
    } catch {
      options = [];
    }
    const cmd = {
      name: row.name,
      description: row.description,
      options,
      permissions: row.permissions,
      guildOnly: Boolean(row.guild_only),
      prefix: Boolean(row.prefix_supported),
      uses: Number(row.uses),
    };
    if (!categories.has(row.category)) categories.set(row.category, []);
    categories.get(row.category).push(cmd);
  }
  return { total: rows.length, categories: [...categories.entries()].map(([name, commands]) => ({ name, commands })) };
}

module.exports = {
  getCommands,
  getTotals,
  getBotStatus,
  getGuilds,
  getGuild,
  getTopCommands,
  getRecentEvents,
  getLeaderboard,
};
