'use strict';

const TIMEZONE = process.env.SITE_TIMEZONE || 'Europe/Berlin';

const numberFmt = new Intl.NumberFormat('de-DE');
const dateFmt = new Intl.DateTimeFormat('de-DE', { dateStyle: 'medium', timeStyle: 'short', timeZone: TIMEZONE });
const relFmt = new Intl.RelativeTimeFormat('de-DE', { numeric: 'auto' });

const DEFAULT_AVATAR = 'https://cdn.discordapp.com/embed/avatars/0.png';

function number(value) {
  return numberFmt.format(Number(value || 0));
}

function date(value) {
  return value ? dateFmt.format(new Date(value)) : '–';
}

function relative(value) {
  if (!value) return '–';
  const seconds = Math.round((new Date(value).getTime() - Date.now()) / 1000);
  const units = [
    ['year', 31536000],
    ['month', 2592000],
    ['day', 86400],
    ['hour', 3600],
    ['minute', 60],
  ];
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) return relFmt.format(Math.round(seconds / size), unit);
  }
  return relFmt.format(seconds, 'second');
}

/** Gleiche Level-Kurve wie im Bot: Level L ab 100 * L² XP. */
function levelInfo(xp) {
  const total = Number(xp || 0);
  const level = Math.floor(Math.sqrt(total / 100));
  const floor = 100 * level * level;
  const ceil = 100 * (level + 1) * (level + 1);
  return {
    level,
    current: total - floor,
    needed: ceil - floor,
    percent: Math.round(((total - floor) / (ceil - floor)) * 100),
  };
}

function avatar(url) {
  return url || DEFAULT_AVATAR;
}

function initials(name) {
  return String(name || '?')
    .split(/\s+/)
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();
}

function slug(value) {
  return String(value || '')
    .toLowerCase()
    .normalize('NFKD')
    .replace(/\p{Diacritic}/gu, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '');
}

module.exports = { number, date, relative, levelInfo, avatar, initials, slug };
