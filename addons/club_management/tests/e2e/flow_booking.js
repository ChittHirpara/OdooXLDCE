const { execSync } = require('child_process');
const { launch, login, openAction, shot, sleep, text, DB, REPO } = require('./lib');

const sql = (q) => execSync(
  `docker compose exec -T db psql -U odoo -d ${DB} -tAc "${q.replace(/"/g, '\\"')}"`,
  { cwd: REPO }).toString().trim();

const clickText = async (page, selector, regex) => {
  const ok = await page.evaluate((sel, re) => {
    const el = [...document.querySelectorAll(sel)].find((e) => new RegExp(re, 'i').test(e.innerText) && e.offsetParent !== null);
    if (el) { el.click(); return true; }
    return false;
  }, selector, regex);
  if (!ok) throw new Error(`no visible ${selector} matching ${regex}`);
};

(async () => {
  const { browser, page, log } = await launch();
  const result = [];
  const check = (name, ok, extra = '') => { result.push(ok); console.log(`${ok ? 'PASS' : 'FAIL'}  ${name} ${extra}`); };
  try {
    await login(page);
    await openAction(page, 'club_management.action_club_court_booking_ui', '.cc-slot-cell');
    await sleep(1500);

    const memberName = (await text(page, '.o_action_manager'))[0].match(/CH Chitt Hirpara|Chitt Hirpara/) ? 'Chitt Hirpara' : '?';
    const memberId = sql("select id from res_partner where name='Chitt Hirpara' and is_member limit 1");
    const before = sql(`select count(*) from club_booking where partner_id=${memberId} and state<>'cancelled'`);
    console.log(`member in UI: ${memberName}; partner id ${memberId}; active bookings before: ${before}`);

    // 1. take a free slot
    const title = 'Tennis Court 1 at 11:00';
    const slot = `.cc-slot-cell[title="${title}"]`;
    const wasOpen = await page.$eval(slot, (e) => e.classList.contains('available'));
    check('slot shows as available before booking', wasOpen);
    await page.click(slot);
    await sleep(300);
    await shot(page, 'b1_selected');
    console.log('primary buttons:', await text(page, 'button.cc-btn-primary'));
    await page.click('.cc-btn-primary');           // opens the review modal
    await sleep(1200);
    await shot(page, 'b2_modal');
    const modalText = (await text(page, '.cc-modal, .cc-modal-overlay, [class*="modal"]')).join(' | ').slice(0, 400);
    console.log('modal:', modalText);
    const priceShown = /₹\s*0\b/.test(modalText);
    check('Gold member sees a ₹0 court price from the server', priceShown, '(' + (modalText.match(/₹[\d,]+/g) || []).join(', ') + ')');

    await clickText(page, 'button', 'confirm');
    await sleep(2000);
    await shot(page, 'b3_confirmed');
    const dbRow = sql(`select name||'|'||state||'|'||price||'|'||tier from club_booking where partner_id=${memberId} and court_id=(select id from club_court where name='Tennis Court 1') and state<>'cancelled' order by id desc limit 1`);
    console.log('booking in DB:', dbRow);
    check('booking was really created in Odoo for the real member', /confirmed\|0/.test(dbRow) && dbRow.endsWith('gold'));
    const slotNow = await page.$eval(slot, (e) => e.classList.contains('booked')).catch(() => null);
    check('grid now shows the slot as booked', slotNow === true);

    // 2. reload: availability must come from the server and persist
    await openAction(page, 'club_management.action_club_court_booking_ui', '.cc-slot-cell');
    await sleep(1500);
    const persisted = await page.$eval(slot, (e) => e.classList.contains('booked'));
    check('after a page reload the slot is still booked (server state)', persisted);

    // 3. the same slot cannot be double booked even if forced
    const dup = sql(`select count(*) from club_booking where court_id=(select id from club_court where name='Tennis Court 1') and state<>'cancelled' and to_char(start_datetime + interval '5 hours 30 minutes','HH24:MI')='11:00' and booking_date=(select booking_date from club_booking where name='${dbRow.split('|')[0]}')`);
    check('exactly one booking holds that slot', dup === '1', `(count ${dup})`);

    // 4. My bookings tab and cancel
    await page.evaluate(() => [...document.querySelectorAll('[class*="cc-"]')].filter((e) => /^My Bookings/.test(e.innerText.trim())).sort((a, b) => a.innerText.length - b.innerText.length)[0].click());
    await sleep(800);
    await shot(page, 'b4_mybookings');
    const refs = await text(page, '.cc-booking-card');
    console.log('my bookings cards:', refs.length, refs.slice(0, 2));
    check('My Bookings lists real bookings from Odoo', refs.some((r) => r.includes(dbRow.split('|')[0])), `(looking for ${dbRow.split('|')[0]})`);

    await page.evaluate((ref) => {
      const card = [...document.querySelectorAll('.cc-booking-card')].find((c) => c.innerText.includes(ref));
      card.querySelector('.cc-btn-cancel-booking').click();
    }, dbRow.split('|')[0]);
    await sleep(500);
    await page.click('.cc-btn-danger');
    await sleep(1500);
    const stateAfter = sql(`select state from club_booking where name='${dbRow.split('|')[0]}'`);
    check('cancel button really cancels the booking in Odoo', stateAfter === 'cancelled', `(state ${stateAfter})`);

    console.log('\nconsole warnings/errors:', JSON.stringify(log.console));
    console.log('page errors:', JSON.stringify(log.errors));
    console.log('bad responses:', JSON.stringify(log.badResponses));
    console.log(`\n${result.filter(Boolean).length}/${result.length} checks passed`);
  } catch (e) {
    console.log('SCRIPT ERROR', e.message);
    await shot(page, 'b_error');
  } finally {
    await browser.close();
  }
})();
