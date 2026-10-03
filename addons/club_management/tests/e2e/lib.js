const puppeteer = require('puppeteer-core');
const path = require('path');

const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const BASE = process.env.ODOO_URL || 'http://localhost:8069';
const DB = process.env.ODOO_DB || 'club_demo';
const REPO = process.env.REPO || path.resolve(__dirname, '../../../..');
const OUT = path.join(__dirname, 'out');
require('fs').mkdirSync(OUT, { recursive: true });

async function launch() {
  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: true,
    args: ['--no-sandbox', '--window-size=1500,1000'],
    defaultViewport: { width: 1500, height: 1000 },
  });
  const page = await browser.newPage();
  const log = { console: [], errors: [], badResponses: [] };
  page.on('console', (m) => {
    const t = m.type();
    if (['warning', 'error'].includes(t)) log.console.push(`[${t}] ${m.text()}`.slice(0, 300));
  });
  page.on('pageerror', (e) => log.errors.push(String(e).slice(0, 300)));
  page.on('response', (r) => {
    if (r.status() >= 400 && !r.url().includes('favicon')) log.badResponses.push(`${r.status()} ${r.url()}`.slice(0, 200));
  });
  return { browser, page, log };
}

async function login(page, user = 'admin', pass = 'admin') {
  await page.goto(`${BASE}/web/login?db=${DB}`, { waitUntil: 'networkidle2' });
  await page.type('input[name=login]', user);
  await page.type('input[name=password]', pass);
  await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle2' }), page.click('button[type=submit]')]);
}

async function openAction(page, xmlid, waitSelector) {
  await page.goto(`${BASE}/web#action=${xmlid}`, { waitUntil: 'networkidle2' });
  if (waitSelector) await page.waitForSelector(waitSelector, { timeout: 20000 });
  await new Promise((r) => setTimeout(r, 800));
}

const shot = (page, name) => page.screenshot({ path: path.join(OUT, name + '.png') });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const text = (page, sel) => page.$$eval(sel, (els) => els.map((e) => e.innerText.trim().replace(/\s+/g, ' ')));

module.exports = { launch, login, openAction, shot, sleep, text, BASE, DB, REPO };
