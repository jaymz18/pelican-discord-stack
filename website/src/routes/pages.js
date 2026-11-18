'use strict';

const express = require('express');
const stats = require('../stats');

const router = express.Router();
const SNOWFLAKE = /^\d{15,21}$/;

router.get('/', async (req, res) => {
  const [totals, bot, guilds, topCommands, events] = await Promise.all([
    stats.getTotals(),
    stats.getBotStatus(),
    stats.getGuilds(),
    stats.getTopCommands(),
    stats.getRecentEvents(),
  ]);
  const maxUses = Math.max(1, ...topCommands.map((c) => Number(c.uses)));
  res.render('index', { title: 'Übersicht', totals, bot, guilds, topCommands, maxUses, events });
});

router.get('/guild/:id', async (req, res, next) => {
  if (!SNOWFLAKE.test(req.params.id)) return next();
  const guild = await stats.getGuild(req.params.id);
  if (!guild) return next();

  const [leaderboard, events] = await Promise.all([
    stats.getLeaderboard(guild.guild_id),
    stats.getRecentEvents(15, guild.guild_id),
  ]);
  return res.render('guild', { title: guild.name, guild, leaderboard, events });
});

router.get('/commands', async (req, res) => {
  const commands = await stats.getCommands();
  res.render('commands', { title: 'Befehle', commands });
});

module.exports = router;
