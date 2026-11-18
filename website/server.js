'use strict';

require('dotenv').config({ quiet: true });

const path = require('node:path');
const express = require('express');
const db = require('./src/db');
const helpers = require('./src/helpers');
const pagesRouter = require('./src/routes/pages');

const PORT = Number(process.env.SERVER_PORT || process.env.PORT || 3000);
const HOST = process.env.HOST || '0.0.0.0';

const app = express();
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.disable('x-powered-by');

app.locals.siteTitle = process.env.SITE_TITLE || 'Discord Bot Dashboard';
app.locals.inviteUrl = process.env.BOT_INVITE_URL || '';
app.locals.h = helpers;

app.use((req, res, next) => {
  res.set({
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
  });
  next();
});
app.use(express.static(path.join(__dirname, 'public'), { maxAge: '1h' }));

app.use('/', pagesRouter);

app.use((req, res) => {
  res.status(404).render('error', { title: '404', message: 'Diese Seite gibt es nicht.' });
});

// eslint-disable-next-line no-unused-vars
app.use((err, req, res, next) => {
  console.error('[error]', err);
  res.status(err.status || 500).render('error', {
    title: 'Fehler',
    message: db.isConnectionError(err)
      ? 'Die Datenbank ist gerade nicht erreichbar.'
      : 'Es ist ein unerwarteter Fehler aufgetreten.',
  });
});

async function start() {
  await db.init();

  const server = app.listen(PORT, HOST, () => {
    console.log(`Website listening on http://${HOST}:${PORT}`);
  });

  let stopping = false;
  const shutdown = (signal) => {
    if (stopping) return;
    stopping = true;
    console.log(`${signal} empfangen – Website wird beendet ...`);
    server.close(() => {
      db.close().finally(() => process.exit(0));
    });
    setTimeout(() => process.exit(0), 5000).unref();
  };
  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
}

start().catch((err) => {
  console.error('Start fehlgeschlagen:', err);
  process.exit(1);
});
