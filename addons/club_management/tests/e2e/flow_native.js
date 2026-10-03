const { execSync } = require('child_process');
const { launch, login, shot, sleep, text, BASE, DB, REPO } = require('./lib');

const sql = (q) => execSync(
  `docker compose exec -T db psql -U odoo -d ${DB} -tAc "${q.replace(/"/g, '\\"')}"`,
  { cwd: REPO }).toString().trim();

(async () => {
  const { browser, page, log } = await launch();
  const result = [];
  const check = (name, ok, extra = '') => { result.push(ok); console.log(`${ok ? 'PASS' : 'FAIL'}  ${name} ${extra}`); };
  const go = async (hash, sel) => {
    log.console.length = 0; log.errors.length = 0; log.badResponses.length = 0;
    await page.goto(`${BASE}/web#${hash}`, { waitUntil: 'networkidle2' });
    if (sel) await page.waitForSelector(sel, { timeout: 20000 });
    await sleep(1200);
  };
  const clean = (name) => {
    const noise = log.console.filter((m) => !/favicon|DevTools|Download the React/i.test(m));
    check(`${name}: no console errors / page errors / bad responses`,
      noise.length === 0 && log.errors.length === 0 && log.badResponses.length === 0,
      noise.length || log.errors.length || log.badResponses.length ? JSON.stringify({ noise, errors: log.errors, bad: log.badResponses }) : '');
  };
  try {
    await login(page);

    // Member form with QR code
    const arjun = sql("select id from res_partner where name='Arjun Mehta'");
    await go(`id=${arjun}&model=res.partner&view_type=form`, '.o_form_view');
    await page.evaluate(() => [...document.querySelectorAll('.nav-link')].find((e) => /Club Membership/.test(e.innerText))?.click());
    await sleep(800);
    await shot(page, 'n1_member');
    const qrOk = await page.evaluate(() => {
      const img = document.querySelector('.o_field_image img, .o_field_widget[name=qr_code] img');
      return img ? { w: img.naturalWidth, h: img.naturalHeight, src: img.src.slice(0, 40) } : null;
    });
    console.log('QR image:', JSON.stringify(qrOk));
    check('member form shows the QR code image', !!qrOk && qrOk.w > 50);
    const vals = await page.evaluate(() => ({ plan: document.querySelector('div[name=plan_id] input')?.value, id: document.querySelector('div[name=member_id]')?.innerText.trim(), state: document.querySelector('div[name=member_state]')?.innerText.trim() }));
    console.log('member fields:', JSON.stringify(vals));
    check('member form shows tier, member id and state', vals.plan === 'Gold' && /^CC-[0-9]+/.test(vals.id) && vals.state === 'Active');
    clean('member form');

    // Bookings list, form, reschedule wizard
    await go('action=club_management.action_club_booking', '.o_list_view');
    await shot(page, 'n2_bookings');
    const rows = await page.$$eval('.o_data_row', (r) => r.length);
    check('bookings list shows demo bookings', rows > 10, `(${rows} rows)`);
    clean('bookings list');

    const bk = sql("select id||'|'||name from club_booking where state='confirmed' and booking_date > current_date and partner_id is not null order by id limit 1").split('|');
    await go(`id=${bk[0]}&model=club.booking&view_type=form`, '.o_form_view');
    await page.evaluate(() => [...document.querySelectorAll('button')].find((b) => /Reschedule/.test(b.innerText))?.click());
    await page.waitForSelector('.modal .o_form_view', { timeout: 10000 });
    await sleep(800);
    await shot(page, 'n3_wizard');
    const wizard = (await text(page, '.modal'))[0];
    check('reschedule wizard opens with current start, court and new start', /Current Start/.test(wizard) && /New Start/.test(wizard) && /Court/.test(wizard));
    // submit an off-grid time to see the server's rule message
    const input = await page.$('.modal div[name=new_start] input');
    await input.click({ clickCount: 3 });
    await input.type('10/04/2026 09:15:00');
    await page.keyboard.press('Enter');
    await page.evaluate(() => [...document.querySelectorAll('.modal button')].find((b) => /^Reschedule$/.test(b.innerText.trim()))?.click());
    await sleep(1500);
    await shot(page, 'n4_wizard_error');
    const dialogs = await text(page, '.modal'); const errorDialog = dialogs.find((d) => /Validation Error/.test(d)) || '';
    console.log('dialog:', errorDialog.slice(0, 220));
    check('off-grid reschedule is rejected with the booking rule message', /hour or half hour/.test(errorDialog));
    log.badResponses.length = 0;
    for (let i = 0; i < 3; i++) { await page.keyboard.press('Escape'); await sleep(400); }
    await page.evaluate(() => [...document.querySelectorAll('.modal button')].forEach((b) => /Close|Discard/.test(b.innerText) && b.click()));
    await sleep(500);

    // Reporting
    await go('action=club_management.action_club_booking_revenue', '.o_pivot, .o_graph_view, .o_content');
    await shot(page, 'n5_revenue');
    const pivotText = (await text(page, '.o_content'))[0] || '';
    check('revenue pivot renders with courts and totals', /Total/.test(pivotText) && /Tennis Court/.test(pivotText), `(${pivotText.slice(0, 120)})`);
    clean('revenue report');
    await page.evaluate(() => document.querySelector('.o_cp_switch_buttons .o_switch_view.o_graph')?.click());
    await sleep(1500);
    await shot(page, 'n6_revenue_graph');
    check('revenue graph renders', !!(await page.$('.o_graph_canvas_container canvas')));
    clean('revenue graph');

    await go('action=club_management.action_club_booking_peak_hours', '.o_content');
    await sleep(1000);
    await shot(page, 'n7_peak');
    check('peak hours graph renders', !!(await page.$('.o_graph_canvas_container canvas')));

    // Orders list
    await go('action=club_management.action_club_order', '.o_list_view');
    await shot(page, 'n8_orders');
    const orders = await page.$$eval('.o_data_row', (r) => r.length);
    check('Bar & Shop Orders list shows the orders taken in the UI', orders >= 3, `(${orders} rows)`);
    clean('orders list');

    // Members, plans, courts, CRM
    await go('action=club_management.action_club_members', '.o_list_view');
    const members = await page.$$eval('.o_data_row', (r) => r.length);
    check('Members list shows members', members >= 10, `(${members})`);
    clean('members list');
    await go('action=club_management.action_club_membership_plan', '.o_list_view');
    clean('plans list');
    await go('action=club_management.action_club_court', '.o_list_view');
    clean('courts list');

    console.log(`\n${result.filter(Boolean).length}/${result.length} checks passed`);
  } catch (e) {
    console.log('SCRIPT ERROR', e.message);
    await shot(page, 'n_error');
  } finally {
    await browser.close();
  }
})();
