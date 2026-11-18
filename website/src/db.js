'use strict';

const mysql = require('mysql2/promise');

let pool = null;

const CONNECTION_ERRORS = new Set([
  'ECONNREFUSED',
  'ENOTFOUND',
  'ETIMEDOUT',
  'EHOSTUNREACH',
  'PROTOCOL_CONNECTION_LOST',
  'ER_ACCESS_DENIED_ERROR',
  'ER_BAD_DB_ERROR',
]);

function isConnectionError(err) {
  return Boolean(err && CONNECTION_ERRORS.has(err.code));
}

function createPool() {
  return mysql.createPool({
    host: process.env.DB_HOST || '127.0.0.1',
    port: Number(process.env.DB_PORT || 3306),
    user: process.env.DB_USERNAME || '',
    password: process.env.DB_PASSWORD || '',
    database: process.env.DB_DATABASE || '',
    charset: 'utf8mb4',
    waitForConnections: true,
    connectionLimit: 5,
    enableKeepAlive: true,
    // Discord-IDs (Snowflakes) sind größer als Number.MAX_SAFE_INTEGER -> als String
    supportBigNumbers: true,
    bigNumberStrings: true,
    // Der Bot speichert alle Zeitstempel in UTC
    timezone: 'Z',
  });
}

/** Baut den Pool auf und prüft die Verbindung (mit Wiederholungen). Wirft nicht. */
async function init(retries = 10, delayMs = 3000) {
  pool = createPool();
  for (let attempt = 1; attempt <= retries; attempt += 1) {
    try {
      await pool.query('SELECT 1');
      console.log(`Mit MariaDB verbunden (${process.env.DB_HOST}:${process.env.DB_PORT || 3306}/${process.env.DB_DATABASE})`);
      return true;
    } catch (err) {
      console.warn(`DB-Verbindung fehlgeschlagen (Versuch ${attempt}/${retries}): ${err.code || err.message}`);
      if (attempt < retries) await new Promise((r) => setTimeout(r, delayMs));
    }
  }
  console.error('Keine Verbindung zur MariaDB – die Website startet trotzdem und versucht es bei jeder Anfrage erneut.');
  return false;
}

/**
 * Führt eine Query aus. Fehlende Tabellen (Bot noch nie gestartet) liefern `fallback`
 * statt eines Fehlers.
 */
async function query(sql, params = [], fallback = []) {
  try {
    const [rows] = await pool.query(sql, params);
    return rows;
  } catch (err) {
    if (err.code === 'ER_NO_SUCH_TABLE') return fallback;
    throw err;
  }
}

async function ping() {
  try {
    await pool.query('SELECT 1');
    return true;
  } catch {
    return false;
  }
}

async function close() {
  if (pool) await pool.end();
}

module.exports = { init, query, ping, close, isConnectionError };
