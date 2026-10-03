// A visitor sends the join form; the admin sees it in Club > Enquiries and presses Join.
const { execSync } = require('child_process');
const { launch, login, shot, sleep, BASE, DB, REPO } = require('./lib');
const sql = (q) => execSync(`docker compose exec -T db psql -U odoo -d ${DB} -tAc "${q.replace(/"/g, '\\"')}"`, { cwd: REPO }).toString().trim();

(async () => {
  const { browser, page } = await launch();
  const result = [];
  const check = (name, ok, extra = '') => { result.push(ok); console.log(`${ok ? 'PASS' : 'FAIL'}  ${name} ${extra}`); };
  const stamp = Date.now().toString().slice(-6);
  const NAME = `Join Tester ${stamp}`, EMAIL = `join.${stamp}@example.com`;
  try {
    // 1. visitor sends the join form
    await page.goto(`${BASE}/join?plan=silver`, { waitUntil: 'networkidle2' });
    await page.type('input[name=name]', NAME);
    await page.type('input[name=email]', EMAIL);
    await page.type('input[name=phone]', '+91 90000 77700');
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle2' }), page.click('.club-form button[type=submit]')]);
    const body = await page.$eval('#wrapwrap', (e) => e.innerText.replace(/\s+/g, ' '));
    const ref = (body.match(/ENQ-\d+/) || [])[0];
    check('the visitor gets an enquiry reference', !!ref, `(${ref})`);
    check('the lead is in the same database the admin uses', sql(`select count(*) from crm_lead where enquiry_ref='${ref}'`) === '1');

    // 2. admin sees it in the enquiries pipeline
    const ctx = await browser.createBrowserContext();
    const admin = await ctx.newPage();
    await admin.setViewport({ width: 1500, height: 1000 });
    await login(admin);
    await admin.goto(`${BASE}/web#action=club_management.action_club_enquiries`, { waitUntil: 'networkidle2' });
    await admin.waitForSelector('.o_kanban_view', { timeout: 20000 });
    await sleep(1500);
    const kanban = await admin.$eval('.o_kanban_view', (e) => e.innerText);
    check('the new enquiry shows on the admin pipeline', kanban.includes(NAME));
    await shot(admin, 'j1_pipeline');

    // 3. open it and press Join the Club
    await admin.evaluate((n) => [...document.querySelectorAll('.o_kanban_record')].find((r) => r.innerText.includes(n)).click(), NAME);
    await admin.waitForSelector('.o_form_view', { timeout: 15000 });
    await sleep(1000);
    check('the lead form has a "Join the Club" button', !!(await admin.$('button[name=action_join_club]')));
    await shot(admin, 'j2_lead_form');
    await admin.click('button[name=action_join_club]');
    await admin.waitForSelector('.modal-footer .btn-primary', { timeout: 8000 });
    await admin.click('.modal-footer .btn-primary');          // confirm dialog
    await sleep(3000);
    await shot(admin, 'j3_joined');
    const row = sql(`select p.member_state||'|'||p.member_id||'|'||coalesce(pl.code,'')||'|'||l.member_activated||'|'||s.is_won from crm_lead l join res_partner p on p.id=l.partner_id left join club_membership_plan pl on pl.id=p.plan_id join crm_stage s on s.id=l.stage_id where l.enquiry_ref='${ref}'`);
    console.log('lead/member in DB:', row);
    check('one click made them an active Silver member and marked the lead Won', /^active\|CC-\d+\|silver\|(t|true)\|(t|true)$/.test(row));
    check('the form now shows the member smart button and no Join button',
      !!(await admin.$('.oe_stat_button')) && !(await admin.$('button[name=action_join_club]')));
    check('the welcome e-mail is queued', Number(sql(`select count(*) from mail_mail where email_to='${EMAIL}'`)) >= 1);
    console.log(`\n${result.filter(Boolean).length}/${result.length} checks passed`);
  } catch (e) {
    console.log('SCRIPT ERROR', e.message);
    await shot(page, 'j_error');
  } finally { await browser.close(); }
})();
