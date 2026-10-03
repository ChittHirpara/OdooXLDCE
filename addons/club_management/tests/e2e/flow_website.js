// The public website, as an anonymous visitor in a real browser (no login).
const { execSync } = require('child_process');
const { launch, shot, sleep, text, BASE, DB, REPO } = require('./lib');

const sql = (q) => execSync(
  `docker compose exec -T db psql -U odoo -d ${DB} -tAc "${q.replace(/"/g, '\\"')}"`,
  { cwd: REPO }).toString().trim();

(async () => {
  const { browser, page, log } = await launch();
  const result = [];
  const check = (name, ok, extra = '') => { result.push(ok); console.log(`${ok ? 'PASS' : 'FAIL'}  ${name} ${extra}`); };
  const go = async (path, sel) => {
    log.console.length = 0; log.errors.length = 0; log.badResponses.length = 0;
    await page.goto(BASE + path, { waitUntil: 'networkidle2' });
    if (sel) await page.waitForSelector(sel, { timeout: 15000 });
    await sleep(500);
  };
  const clean = (name) => {
    const noise = log.console.filter((m) => !/favicon|DevTools|Failed to load resource.*(fonts|gstatic|googleapis)|ERR_NAME_NOT_RESOLVED|ERR_INTERNET/i.test(m));
    const bad = log.badResponses.filter((r) => !/fonts\.|gstatic|googleapis/.test(r));
    check(`${name}: no console errors / page errors / bad responses`, !noise.length && !log.errors.length && !bad.length,
      noise.length || log.errors.length || bad.length ? JSON.stringify({ noise, errors: log.errors, bad }) : '');
  };
  const bodyText = () => page.$eval('#wrapwrap', (e) => e.innerText.replace(/\s+/g, ' '));

  try {
    // ---- Home
    await go('/', '.club-home');
    await shot(page, 'w1_home');
    const nav = await page.$$eval('header a.nav-link', (a) => a.map((x) => x.innerText.trim()).filter(Boolean));
    console.log('nav:', nav);
    check('navigation: Home, Membership, Courts, Shop, About, Contact, Join the Club',
      JSON.stringify(nav.slice(0, 7)) === JSON.stringify(['Home', 'Membership', 'Courts', 'Shop', 'About', 'Contact', 'Join the Club']), `(${nav})`);
    let body = await bodyText();
    check('home: hero, features, plans, open courts, shop preview, CTA',
      /Where champions train/.test(body) && /Tennis/.test(body) && /Padel/.test(body) && /Gold/.test(body)
      && /Open courts today/.test(body) && /From the Pro-Shop/.test(body) && /Ready to join the club/.test(body));
    check('home: shows 3 plans and 4 products', (await page.$$('.club-plan')).length === 3 && (await page.$$('.club-product')).length === 4);
    clean('home');

    // ---- Membership: view Gold, then join Gold
    await page.evaluate(() => [...document.querySelectorAll('header a.nav-link')].find((a) => a.innerText.trim() === 'Membership').click());
    await page.waitForSelector('.club-membership .club-plan', { timeout: 10000 });
    await sleep(500);
    await shot(page, 'w2_membership');
    body = await bodyText();
    check('membership: Gold ₹5,000, Silver ₹3,000, Junior ₹1,500 from the database',
      /₹\s?5,000/.test(body) && /₹\s?3,000/.test(body) && /₹\s?1,500/.test(body));
    check('membership: comparison table', /Compare the plans/.test(body) && (await page.$$('.club-compare tbody tr')).length >= 5);
    await page.evaluate(() => document.querySelector('.club-plan[data-plan="gold"] a.btn').click());
    await page.waitForSelector('.club-join form', { timeout: 10000 });
    const preselected = await page.$eval('select[name=plan]', (s) => s.value);
    check('"Join Gold" opens the form with Gold preselected', preselected === 'gold', `(${preselected})`);
    clean('membership');

    // ---- Courts: the live availability grid
    await go('/courts', '.club-court-row');
    await shot(page, 'w3_courts');
    const tomorrow = sql("select value from ir_config_parameter where key='club_management.demo_busy_day'");
    await page.$eval('.js-date', (el, v) => { el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); }, tomorrow);
    await sleep(2000);
    await shot(page, 'w4_courts_busy');
    const rows = await page.$$eval('.club-court-row', (r) => r.map((x) => ({
      court: x.querySelector('h5').innerText,
      free: x.querySelectorAll('.club-slot-free').length,
      booked: x.querySelectorAll('.club-slot-booked').length,
    })));
    console.log('busy day', tomorrow, rows.map((r) => `${r.court}: ${r.booked} booked / ${r.free} free`).join(' | '));
    const dbBusy = sql(`select count(*) from club_booking where booking_date='${tomorrow}' and state<>'cancelled'`);
    check('busy evening shows many booked slots from the real bookings', rows.reduce((s, r) => s + r.booked, 0) >= 20, `(db has ${dbBusy} bookings that day)`);
    const tennis1 = rows.find((r) => r.court === 'Tennis Court 1');
    check('a fully booked evening court has booked slots and morning slots still free', tennis1 && tennis1.booked > 0 && tennis1.free > 0, JSON.stringify(tennis1));

    // sport filter
    await page.select('.js-sport', 'cricket');
    await sleep(1500);
    const cricket = await page.$$eval('.club-court-row h5', (h) => h.map((x) => x.innerText));
    check('sport filter shows only cricket nets', cricket.length >= 2 && cricket.every((n) => /Cricket Net/.test(n)), `(${cricket})`);
    await page.select('.js-sport', '');
    await sleep(1200);

    // Friday social play: places left
    const friday = sql("select value from ir_config_parameter where key='club_management.demo_social_day'");
    await page.$eval('.js-date', (el, v) => { el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); }, friday);
    await sleep(2000);
    await shot(page, 'w5_courts_friday');
    const note = await page.$eval('.js-note', (e) => ({ hidden: e.classList.contains('d-none'), text: e.innerText }));
    const leftBadges = await page.$$eval('.club-slot-free small', (s) => s.length);
    check('Friday shows the social-play note and places left per slot', !note.hidden && /social play/i.test(note.text) && leftBadges > 0, `(${leftBadges} slots with places left)`);
    const fullSlots = await page.$$eval('.club-court-row', (r) => r.map((x) => ({ c: x.querySelector('h5').innerText, booked: x.querySelectorAll('.club-slot-booked').length })));
    check('a full Friday court (8 of 8 at 19:00) shows booked slots', fullSlots.find((x) => x.c === 'Tennis Court 1').booked >= 2);

    // request a free slot -> prefilled enquiry
    await page.$eval('.js-date', (el, v) => { el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); }, tomorrow);
    await sleep(1800);
    await page.evaluate(() => document.querySelector('.club-slot-free').click());
    await page.waitForSelector('.club-join form', { timeout: 10000 });
    const prefill = await page.evaluate(() => ({ type: document.querySelector('select[name=type]').value, msg: document.querySelector('textarea[name=message]').value }));
    check('clicking a free slot opens the enquiry prefilled with court, date and time',
      prefill.type === 'court' && /I would like to request .+ on \d{4}-\d{2}-\d{2} at \d{2}:\d{2}/.test(prefill.msg), JSON.stringify(prefill));
    clean('courts');

    // ---- Shop
    await go('/club-shop', '.club-product');
    await shot(page, 'w6_shop');
    const products = await page.$$eval('.club-product-name', (e) => e.map((x) => x.innerText));
    check('shop lists the pro-shop products only', products.length >= 8 && !products.some((n) => /Latte|Coffee|Sandwich|Membership/.test(n)), `(${products.length} products)`);
    const lowStock = await bodyText();
    check('shop shows live stock ("Only 3 left" for tennis balls)', /Only 3 left/.test(lowStock));
    await page.type('input[name=q]', 'towel');
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle2' }), page.click('.club-shop-search button')]);
    const found = await page.$$eval('.club-product-name', (e) => e.map((x) => x.innerText));
    check('search narrows the grid', found.length === 1 && /Towel/.test(found[0]), `(${found})`);
    await page.evaluate(() => document.querySelector('.club-product').click());
    await page.waitForSelector('.club-product-page', { timeout: 10000 });
    await shot(page, 'w7_product');
    body = await bodyText();
    check('product page: price, stock and member prices per tier', /₹350/.test(body) && /Member prices/.test(body) && /₹280/.test(body) && /₹315/.test(body), '');
    await page.evaluate(() => [...document.querySelectorAll('a.btn')].find((a) => /Reserve/.test(a.innerText)).click());
    await page.waitForSelector('.club-join form', { timeout: 10000 });
    const reserve = await page.evaluate(() => ({ type: document.querySelector('select[name=type]').value, msg: document.querySelector('textarea[name=message]').value }));
    check('"Reserve for pickup" opens a shop enquiry for that product', reserve.type === 'shop' && /reserve: Club Towel/.test(reserve.msg), JSON.stringify(reserve));
    clean('shop');

    // ---- Join: submit the enquiry for real
    const before = Number(sql("select count(*) from crm_lead where enquiry_ref is not null"));
    await go('/join?type=membership&plan=gold&sport=tennis', '.club-join form');
    await page.type('input[name=name]', 'Playwright Visitor');
    await page.type('input[name=email]', 'visitor.e2e@example.com');
    await page.type('input[name=phone]', '+91 90000 77777');
    await page.type('textarea[name=message]', 'I would like a Gold membership. Do you offer coaching?');
    await shot(page, 'w8_form');
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle2' }), page.click('.club-form button[type=submit]')]);
    await shot(page, 'w9_success');
    body = await bodyText();
    const ref = (body.match(/ENQ-\d{5}/) || [])[0];
    check('success page thanks the visitor and shows a reference', /Thank you, Playwright Visitor/.test(body) && !!ref, `(${ref})`);
    const lead = sql(`select l.enquiry_ref||'|'||l.contact_name||'|'||l.email_from||'|'||coalesce(l.enquiry_source,'')||'|'||coalesce((select name from club_membership_plan where id=l.interested_plan_id),'')||'|'||(select name->>'en_US' from crm_stage where id=l.stage_id)||'|'||coalesce(u.login,'') from crm_lead l left join res_users u on u.id=l.user_id where l.email_from='visitor.e2e@example.com'`);
    console.log('lead in DB:', lead);
    check('a CRM lead was created: website source, Gold, stage New, assigned', new RegExp(`^${ref}\\|Playwright Visitor\\|visitor.e2e@example.com\\|website\\|Gold\\|New\\|.+`).test(lead));
    check('exactly one new lead', Number(sql("select count(*) from crm_lead where enquiry_ref is not null")) === before + 1);
    check('a follow-up call is scheduled for the assignee', Number(sql("select count(*) from mail_activity a join crm_lead l on l.id=a.res_id and a.res_model='crm.lead' where l.email_from='visitor.e2e@example.com'")) === 1);
    check('the acknowledgment email is queued', Number(sql("select count(*) from mail_mail m join mail_message g on g.id=m.mail_message_id where g.subject like 'We received your enquiry " + ref + "%'")) === 1);

    // status link from the success page
    await page.evaluate(() => [...document.querySelectorAll('a')].find((a) => /Check the status/.test(a.innerText)).click());
    await page.waitForSelector('.club-timeline', { timeout: 10000 });
    await shot(page, 'w10_status');
    body = await bodyText();
    check('status page shows the reference, "New" and a 6-step timeline', body.includes(ref) && /New/.test(body) && (await page.$$('.club-step')).length === 6);
    check('status page shows nothing internal', !/visitor\.e2e@example\.com|Mitchell Admin/.test(body));
    clean('join + status');

    // ---- validation and honeypot in the browser
    await go('/join', '.club-join form');
    await page.type('input[name=name]', 'No Contact');
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle2' }), page.click('.club-form button[type=submit]')]);
    body = await bodyText();
    check('a form without email/phone shows a clear message and keeps the name', /email address or a phone number/.test(body) && (await page.$eval('input[name=name]', (e) => e.value)) === 'No Contact');
    const hpVisible = await page.$eval('.club-hp', (e) => { const r = e.getBoundingClientRect(); return r.right > 0 && r.left < window.innerWidth && r.width > 5; });
    check('the honeypot field is not visible to people', !hpVisible);

    // ---- other pages + mobile
    for (const [path, needle] of [['/about', 'Play, shop, unwind'], ['/contact', 'Get in touch']]) {
      await go(path, '.club-site');
      check(`${path} renders`, (await bodyText()).includes(needle));
      clean(path);
    }
    await page.setViewport({ width: 390, height: 800, isMobile: true });
    for (const path of ['/', '/membership', '/courts', '/club-shop', '/join']) {
      await go(path, '.club-site');
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      check(`mobile 390px: ${path} has no sideways scrolling`, overflow <= 1, `(overflow ${overflow}px)`);
    }
    await go('/courts', '.club-court-row');
    await shot(page, 'w11_mobile_courts');

    console.log(`\n${result.filter(Boolean).length}/${result.length} checks passed`);
  } catch (e) {
    console.log('SCRIPT ERROR', e.message);
    await shot(page, 'w_error');
  } finally {
    await browser.close();
  }
})();
