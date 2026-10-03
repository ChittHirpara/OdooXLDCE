// Staff side of the CRM: pipeline, lead form, quote, accept, member (Odoo backend screens).
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
    const noise = log.console.filter((m) => !/favicon|DevTools/i.test(m));
    check(`${name}: no console errors / page errors / bad responses`,
      !noise.length && !log.errors.length && !log.badResponses.length,
      noise.length || log.errors.length || log.badResponses.length ? JSON.stringify({ noise, errors: log.errors, bad: log.badResponses }) : '');
  };
  const clickButton = (name) => page.evaluate((n) => {
    const b = document.querySelector(`button[name="${n}"]`);
    if (b && b.offsetParent !== null) { b.click(); return true; }
    return false;
  }, name);

  try {
    await login(page);

    // 1. pipeline kanban
    await go('action=club_management.action_club_enquiries', '.o_kanban_view');
    await shot(page, 'c1_pipeline');
    const columns = await text(page, '.o_kanban_group .o_column_title');
    console.log('columns:', columns);
    check('pipeline shows the club stages in order',
      JSON.stringify(columns.slice(0, 5)) === JSON.stringify(['New', 'Contacted', 'Interested', 'Quote Sent', 'Negotiation']), `(${columns})`);
    const cards = await text(page, '.o_kanban_record');
    check('pipeline has the demo enquiries', cards.length >= 7, `(${cards.length} cards)`);
    check('cards show the interested plan', cards.some((c) => /Gold|Silver|Junior/.test(c)));
    check('cards show follow-up activities', (await page.$$('.o_kanban_record .o_ActivityButton, .o_kanban_record .o_mail_activity, .o_kanban_record [class*="activity"]')).length > 0);
    clean('pipeline');

    // 2. lead form: club fields + quote button
    const lead = sql("select id from crm_lead where email_from='kavita.shah@example.com'");
    await go(`id=${lead}&model=crm.lead&view_type=form`, '.o_form_view');
    await shot(page, 'c2_lead');
    const hasQuote = await page.$('button[name="action_create_membership_quote"]');
    check('lead form has the Create Membership Quote button', !!hasQuote);
    await page.evaluate(() => [...document.querySelectorAll('.nav-link')].find((e) => /Club Enquiry/.test(e.innerText))?.click());
    await sleep(600);
    await shot(page, 'c3_club_tab');
    const tab = await page.evaluate(() => ({
      plan: document.querySelector('div[name=interested_plan_id] input')?.value,
      ref: document.querySelector('div[name=enquiry_ref]')?.innerText.trim(),
      source: document.querySelector('div[name=enquiry_source] select, div[name=enquiry_source]')?.innerText.trim(),
      follow: document.querySelector('div[name=follow_up_date]')?.innerText.trim(),
    }));
    console.log('club tab:', JSON.stringify(tab));
    check('Club Enquiry tab shows plan, reference, source and next follow-up',
      tab.plan === 'Junior' && /^ENQ-\d+/.test(tab.ref) && /Website/.test(tab.source) && /\d{2}\/\d{2}\/\d{4}/.test(tab.follow));
    clean('lead form');

    // 3. create the quote from the lead
    check('Create Membership Quote button clicked', await clickButton('action_create_membership_quote'));
    await page.waitForSelector('.o_form_view .o_statusbar_status button.o_arrow_button, .o_form_view [name=order_line]', { timeout: 15000 });
    await sleep(1500);
    await shot(page, 'c4_quote');
    const so = (await text(page, '.o_form_view'))[0];
    check('a quotation opens with the Junior membership line', /Junior Membership/.test(so) && /1,500\.00/.test(so), `(${so.match(/S\d+/)})`);
    const quoteRow = sql(`select o.state||'|'||o.amount_untaxed||'|'||(select name->>'en_US' from crm_stage where id=l.stage_id) from sale_order o join crm_lead l on l.id=o.opportunity_id where l.id=${lead}`);
    console.log('quote in DB:', quoteRow);
    check('quote saved as draft, 1500, lead moved to Quote Sent', quoteRow === 'draft|1500.00|Quote Sent');

    // 4. customer accepts: confirm the quotation
    check('Confirm clicked', await clickButton('action_confirm'));
    await sleep(3000);
    await shot(page, 'c5_confirmed');
    const after = sql(`select (select name->>'en_US' from crm_stage where id=l.stage_id)||'|'||l.probability||'|'||l.member_activated from crm_lead l where l.id=${lead}`);
    console.log('lead after confirm:', after);
    check('confirming the quote wins the lead (stage Won, 100%, member activated)', after === 'Won|100|true');
    const member = sql("select p.member_id||'|'||p.member_state||'|'||(select name from club_membership_plan where id=p.plan_id)||'|'||p.is_member from res_partner p where p.email='kavita.shah@example.com' order by p.id desc limit 1");
    console.log('member:', member);
    check('the customer is now an active Junior member with an ID', /^CC-\d+\|active\|Junior\|true$/.test(member));
    check('a welcome email was queued', Number(sql("select count(*) from mail_mail m join mail_message g on g.id=m.mail_message_id where g.subject like 'Welcome to The Champions Club%'")) >= 2);

    // 5. back on the lead: Member smart button and Won stage
    await go(`id=${lead}&model=crm.lead&view_type=form`, '.o_form_view');
    await shot(page, 'c6_won_lead');
    const memberBtn = await page.evaluate(() => (document.querySelector('.o-form-buttonbox, .oe_button_box') || {}).innerText || '');
    check('lead shows the Member smart button with the member ID', /CC-\d+/.test(memberBtn), `(${memberBtn})`);
    const stageBar = (await text(page, '.o_statusbar_status .o_arrow_button.o_arrow_button_current, .o_statusbar_status .o_arrow_button.o_arrow_button_current_ancestors'))[0] || '';
    check('status bar is on Won', /Won/.test(await page.$eval('.o_statusbar_status', (e) => e.innerText)));
    clean('won lead');

    // 6. the member record carries everything
    const partner = sql("select id from res_partner where email='kavita.shah@example.com' order by id desc limit 1");
    await go(`id=${partner}&model=res.partner&view_type=form`, '.o_form_view');
    await page.evaluate(() => [...document.querySelectorAll('.nav-link')].find((e) => /Club Membership/.test(e.innerText))?.click());
    await sleep(600);
    const pf = await page.evaluate(() => ({
      plan: document.querySelector('div[name=plan_id] input')?.value,
      state: document.querySelector('div[name=member_state]')?.innerText.trim(),
      qr: !!document.querySelector('div[name=qr_code] img'),
    }));
    check('member form: Junior, Active, with QR code', pf.plan === 'Junior' && pf.state === 'Active' && pf.qr, JSON.stringify(pf));

    // 7. list + funnel report
    await go('action=club_management.action_club_enquiries&view_type=list', '.o_list_view, .o_kanban_view');
    await page.evaluate(() => document.querySelector('.o_switch_view.o_list')?.click());
    await sleep(1200);
    await shot(page, 'c7_list');
    const header = (await text(page, '.o_list_table thead'))[0] || '';
    check('pipeline list shows reference, plan and follow-up columns', /Enquiry Ref/.test(header) && /Interested Plan/.test(header) && /Next Follow-up/.test(header));
    clean('pipeline list');

    await go('action=club_management.action_club_enquiry_funnel', '.o_pivot, .o_content');
    await sleep(1000);
    await shot(page, 'c8_funnel');
    const pivot = (await text(page, '.o_content'))[0] || '';
    check('funnel pivot counts leads by stage and plan', /Won/.test(pivot) && /Silver/.test(pivot) && /Total/.test(pivot), `(${pivot.slice(0, 100)})`);
    clean('funnel');

    console.log(`\n${result.filter(Boolean).length}/${result.length} checks passed`);
  } catch (e) {
    console.log('SCRIPT ERROR', e.message);
    await shot(page, 'c_error');
  } finally {
    await browser.close();
  }
})();
