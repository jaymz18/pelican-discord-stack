'use strict';

const express = require('express');
const db = require('../db');
const stats = require('../stats');
const { levelInfo } = require('../helpers');

const router = express.Router();
const SNOWFLAKE = /^\d{15,21}$/;

router.get('/health', async (req, res) => {
  const database = await db.ping();
  res.status(database ? 200 : 503).json({ status: database ? 'ok' : 'degraded', database });
});

router.get('/stats', async (req, res) => {
  const [totals, bot, topCommands] = await Promise.all([
    stats.getTotals(),
    stats.getBotStatus(),
    stats.getTopCommands(),
  ]);
  res.json({ bot, totals, topCommands: topCommands.map((c) => ({ command: c.command, uses: Number(c.uses) })) });
});

router.get('/guilds', async (req, res) => {
  const guilds = await stats.getGuilds();
  res.json(guilds.map((g) => ({ id: g.guild_id, name: g.name, icon: g.icon_url, members: g.member_count })));
});

router.get('/guilds/:id/leaderboard', async (req, res) => {
  if (!SNOWFLAKE.test(req.params.id)) return res.status(400).json({ error: 'invalid_guild_id' });
  const limit = Math.min(Math.max(Number.parseInt(req.query.limit, 10) || 25, 1), 100);
  const rows = await stats.getLeaderboard(req.params.id, limit);
  return res.json(
    rows.map((r, i) => ({
      rank: i + 1,
      userId: r.user_id,
      username: r.username,
      avatar: r.avatar_url,
      xp: r.xp,
      level: levelInfo(r.xp).level,
      messages: r.messages,
    })),
  );
});

router.use((req, res) => res.status(404).json({ error: 'not_found' }));

module.exports = router;
