|(t|true)|(t|true)$/.test(row)// A visitor sends the join form; the admin sees it in Club > Enquiries and presses Join.
|(t|true)|(t|true)$/.test(row)const { execSync } = require('child_process');
|(t|true)|(t|true)$/.test(row)const { launch, login, shot, sleep, BASE, DB, REPO } = require('./lib');
|(t|true)|(t|true)$/.test(row)const sql = (q) => execSync(`docker compose exec -T db psql -U odoo -d ${DB} -tAc "${q.replace(/"/g, '\\"')}"`, { cwd: REPO }).toString().trim();
|(t|true)|(t|true)$/.test(row)
|(t|true)|(t|true)$/.test(row)(async () => {
|(t|true)|(t|true)$/.test(row)  const { browser, page } = await launch();
|(t|true)|(t|true)$/.test(row)  const result = [];
|(t|true)|(t|true)$/.test(row)  const check = (name, ok, extra = '') => { result.push(ok); console.log(`${ok ? 'PASS' : 'FAIL'}  ${name} ${extra}`); };
|(t|true)|(t|true)$/.test(row)  const stamp = Date.now().toString().slice(-6);
|(t|true)|(t|true)$/.test(row)  const NAME = `Join Tester ${stamp}`, EMAIL = `join.${stamp}@example.com`;
|(t|true)|(t|true)$/.test(row)  try {
|(t|true)|(t|true)$/.test(row)    // 1. visitor sends the join form
|(t|true)|(t|true)$/.test(row)    await page.goto(`${BASE}/join?plan=silver`, { waitUntil: 'networkidle2' });
|(t|true)|(t|true)$/.test(row)    await page.type('input[name=name]', NAME);
|(t|true)|(t|true)$/.test(row)    await page.type('input[name=email]', EMAIL);
|(t|true)|(t|true)$/.test(row)    await page.type('input[name=phone]', '+91 90000 77700');
|(t|true)|(t|true)$/.test(row)    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle2' }), page.click('.club-form button[type=submit]')]);
|(t|true)|(t|true)$/.test(row)    const body = await page.$eval('#wrapwrap', (e) => e.innerText.replace(/\s+/g, ' '));
|(t|true)|(t|true)$/.test(row)    const ref = (body.match(/ENQ-\d+/) || [])[0];
|(t|true)|(t|true)$/.test(row)    check('the visitor gets an enquiry reference', !!ref, `(${ref})`);
|(t|true)|(t|true)$/.test(row)    check('the lead is in the same database the admin uses', sql(`select count(*) from crm_lead where enquiry_ref='${ref}'`) === '1');
|(t|true)|(t|true)$/.test(row)
|(t|true)|(t|true)$/.test(row)    // 2. admin sees it in the enquiries pipeline
|(t|true)|(t|true)$/.test(row)    const ctx = await browser.createBrowserContext();
|(t|true)|(t|true)$/.test(row)    const admin = await ctx.newPage();
|(t|true)|(t|true)$/.test(row)    await admin.setViewport({ width: 1500, height: 1000 });
|(t|true)|(t|true)$/.test(row)    await login(admin);
|(t|true)|(t|true)$/.test(row)    await admin.goto(`${BASE}/web#action=club_management.action_club_enquiries`, { waitUntil: 'networkidle2' });
|(t|true)|(t|true)$/.test(row)    await admin.waitForSelector('.o_kanban_view', { timeout: 20000 });
|(t|true)|(t|true)$/.test(row)    await sleep(1500);
|(t|true)|(t|true)$/.test(row)    const kanban = await admin.$eval('.o_kanban_view', (e) => e.innerText);
|(t|true)|(t|true)$/.test(row)    check('the new enquiry shows on the admin pipeline', kanban.includes(NAME));
|(t|true)|(t|true)$/.test(row)    await shot(admin, 'j1_pipeline');
|(t|true)|(t|true)$/.test(row)
|(t|true)|(t|true)$/.test(row)    // 3. open it and press Join the Club
|(t|true)|(t|true)$/.test(row)    await admin.evaluate((n) => [...document.querySelectorAll('.o_kanban_record')].find((r) => r.innerText.includes(n)).click(), NAME);
|(t|true)|(t|true)$/.test(row)    await admin.waitForSelector('.o_form_view', { timeout: 15000 });
|(t|true)|(t|true)$/.test(row)    await sleep(1000);
|(t|true)|(t|true)$/.test(row)    check('the lead form has a "Join the Club" button', !!(await admin.$('button[name=action_join_club]')));
|(t|true)|(t|true)$/.test(row)    await shot(admin, 'j2_lead_form');
|(t|true)|(t|true)$/.test(row)    await admin.click('button[name=action_join_club]');
|(t|true)|(t|true)$/.test(row)    await admin.waitForSelector('.modal-footer .btn-primary', { timeout: 8000 });
|(t|true)|(t|true)$/.test(row)    await admin.click('.modal-footer .btn-primary');          // confirm dialog
|(t|true)|(t|true)$/.test(row)    await sleep(3000);
|(t|true)|(t|true)$/.test(row)    await shot(admin, 'j3_joined');
|(t|true)|(t|true)$/.test(row)    const row = sql(`select p.member_state||'|'||p.member_id||'|'||coalesce(pl.code,'')||'|'||l.member_activated||'|'||s.is_won from crm_lead l join res_partner p on p.id=l.partner_id left join club_membership_plan pl on pl.id=p.plan_id join crm_stage s on s.id=l.stage_id where l.enquiry_ref='${ref}'`);
|(t|true)|(t|true)$/.test(row)    console.log('lead/member in DB:', row);
|(t|true)|(t|true)$/.test(row)    check('one click made them an active Silver member and marked the lead Won', /^active\|CC-\d+\|silver\|t\|t$/.test(row));
|(t|true)|(t|true)$/.test(row)    check('the form now shows the member smart button and no Join button',
|(t|true)|(t|true)$/.test(row)      !!(await admin.$('.oe_stat_button')) && !(await admin.$('button[name=action_join_club]')));
|(t|true)|(t|true)$/.test(row)    check('the welcome e-mail is queued', Number(sql(`select count(*) from mail_mail where email_to='${EMAIL}'`)) >= 1);
|(t|true)|(t|true)$/.test(row)    console.log(`\n${result.filter(Boolean).length}/${result.length} checks passed`);
|(t|true)|(t|true)$/.test(row)  } catch (e) {
|(t|true)|(t|true)$/.test(row)    console.log('SCRIPT ERROR', e.message);
|(t|true)|(t|true)$/.test(row)    await shot(page, 'j_error');
|(t|true)|(t|true)$/.test(row)  } finally { await browser.close(); }
|(t|true)|(t|true)$/.test(row)})();
