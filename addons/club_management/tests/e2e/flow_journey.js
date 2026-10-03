// The complete visitor-to-member journey from the specification, in a real browser.
// Visitor (anonymous) -> website enquiry -> CRM (staff, logged in) -> quote -> won ->
// member -> court booking, shop order, bar order -> accounting records.
const { execSync } = require('child_process');
const { launch, login, shot, sleep, text, BASE, DB, REPO } = require('./lib');

const sql = (q) => execSync(
  `docker compose exec -T db psql -U odoo -d ${DB} -tAc "${q.replace(/"/g, '\\"')}"`,
  { cwd: REPO }).toString().trim();

const EMAIL = 'journey.e2e@example.com';
const NAME = 'Journey Visitor';

(async () => {
  const { browser, page: visitor, log: visitorLog } = await launch();
  const staffContext = await browser.createBrowserContext();
  const staff = await staffContext.newPage();
  await staff.setViewport({ width: 1500, height: 1000 });
  const staffLog = { console: [], errors: [] };
  staff.on('console', (m) => ['error'].includes(m.type()) && staffLog.console.push(m.text().slice(0, 200)));
  staff.on('pageerror', (e) => staffLog.errors.push(String(e).slice(0, 200)));

  const result = [];
  const step = (n, title) => console.log(`\n--- ${n}. ${title}`);
  const check = (name, ok, extra = '') => { result.push(ok); console.log(`${ok ? 'PASS' : 'FAIL'}  ${name} ${extra}`); };
  const body = (p) => p.$eval('#wrapwrap, .o_action_manager', (e) => e.innerText.replace(/\s+/g, ' '));
  const clickByText = (p, selector, regex) => p.evaluate((sel, re) => {
    const el = [...document.querySelectorAll(sel)].filter((e) => new RegExp(re, 'i').test(e.innerText) && e.offsetParent !== null)
      .sort((a, b) => a.innerText.length - b.innerText.length)[0];
    if (!el) return false;
    el.click();
    return true;
  }, selector, regex);
  const rpc = (p, model, method, args, kwargs = {}) => p.evaluate(async (m, me, a, k) => {
    const r = await fetch(`/web/dataset/call_kw/${m}/${me}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: { model: m, method: me, args: a, kwargs: k } }),
    });
    const j = await r.json();
    return j.result ?? { error: j.error && j.error.data && j.error.data.message };
  }, model, method, args, kwargs);
  const leadStage = () => sql(`select (select name->>'en_US' from crm_stage where id=l.stage_id)||'|'||coalesce(l.probability,0)||'|'||coalesce(l.member_activated,false) from crm_lead l where l.email_from='${EMAIL}'`);

  try {
    // ============ 1-4. The visitor
    step(1, 'Visitor opens the website, views Gold, checks availability, submits the enquiry');
    await visitor.goto(BASE + '/', { waitUntil: 'networkidle2' });
    await visitor.evaluate(() => [...document.querySelectorAll('header a.nav-link')].find((a) => a.innerText.trim() === 'Membership').click());
    await visitor.waitForSelector('.club-plan', { timeout: 10000 });
    check('visitor sees the Gold plan', /Gold/.test(await body(visitor)) && /₹\s?5,000/.test(await body(visitor)));
    await visitor.goto(BASE + '/courts', { waitUntil: 'networkidle2' });
    await visitor.waitForSelector('.club-court-row', { timeout: 15000 });
    check('visitor checks court availability (live grid)', (await visitor.$$('.club-slot-free')).length > 20);
    await visitor.goto(BASE + '/join?type=membership&plan=gold&sport=tennis', { waitUntil: 'networkidle2' });
    await visitor.type('input[name=name]', NAME);
    await visitor.type('input[name=email]', EMAIL);
    await visitor.type('input[name=phone]', '+91 90000 88888');
    await visitor.type('textarea[name=message]', 'I want the Gold membership for tennis.');
    await Promise.all([visitor.waitForNavigation({ waitUntil: 'networkidle2' }), visitor.click('.club-form button[type=submit]')]);
    const success = await body(visitor);
    const ref = (success.match(/ENQ-\d{5}/) || [])[0];
    const statusUrl = await visitor.$eval('a[href^="/club/enquiry/status/"]', (a) => a.getAttribute('href'));
    check('enquiry accepted, reference shown', !!ref, `(${ref})`);

    step(5, 'A CRM lead is created automatically');
    const parts = {
      stage: /^New\|/.test(leadStage()),
      source: Number(sql(`select count(*) from crm_lead where email_from='${EMAIL}' and enquiry_source='website' and user_id is not null and interested_plan_id is not null`)) === 1,
      call: Number(sql(`select count(*) from mail_activity a join crm_lead l on l.id=a.res_id and a.res_model='crm.lead' where l.email_from='${EMAIL}'`)) === 1,
    };
    check('lead in stage New, website source, Gold, assigned, follow-up call scheduled', Object.values(parts).every(Boolean), JSON.stringify(parts) + ' ' + leadStage());

    // ============ 6-8. Staff in the CRM
    step(6, 'Staff open the CRM pipeline and find the lead');
    await login(staff);
    await staff.goto(`${BASE}/web#action=club_management.action_club_enquiries`, { waitUntil: 'networkidle2' });
    await staff.waitForSelector('.o_kanban_view', { timeout: 20000 });
    await sleep(1200);
    const newColumn = await staff.$$eval('.o_kanban_group', (g) => {
      const first = g.find((x) => /New/.test(x.querySelector('.o_column_title')?.innerText || ''));
      return first ? [...first.querySelectorAll('.o_kanban_record')].map((r) => r.innerText.replace(/\s+/g, ' ')) : [];
    });
    check('the new lead is in the New column of the pipeline', newColumn.some((c) => c.includes(NAME) && /Gold/.test(c)), `(${newColumn.length} cards in New)`);
    await shot(staff, 'j1_pipeline');
    const leadId = sql(`select id from crm_lead where email_from='${EMAIL}'`);
    await staff.goto(`${BASE}/web#id=${leadId}&model=crm.lead&view_type=form`, { waitUntil: 'networkidle2' });
    await staff.waitForSelector('.o_form_view', { timeout: 15000 });
    await sleep(1000);
    check('lead shows the planned follow-up call', /Contact new enquiry/.test(await body(staff)));

    step(7, 'Staff contact the visitor and move the lead to Contacted, then Interested');
    for (const stage of ['Contacted', 'Interested']) {
      check(`clicked ${stage}`, await clickByText(staff, '.o_statusbar_status button', `^${stage}`));
      await sleep(1800);
      check(`lead is now ${stage} in the database`, leadStage().startsWith(stage + '|'), `(${leadStage()})`);
      await visitor.goto(BASE + statusUrl, { waitUntil: 'networkidle2' });
      const status = await body(visitor);
      check(`the visitor's status page follows: ${stage}`, status.includes(stage) && (await visitor.$$('.club-step.done')).length >= (stage === 'Contacted' ? 1 : 2));
    }
    await shot(visitor, 'j2_status_interested');

    step(9, 'Staff create the quotation (Membership product, price)');
    check('Create Membership Quote clicked', await staff.evaluate(() => { const b = document.querySelector('button[name="action_create_membership_quote"]'); if (b) { b.click(); return true; } return false; }));
    await staff.waitForSelector('.o_form_view [name=order_line]', { timeout: 15000 });
    await sleep(1500);
    await shot(staff, 'j3_quote');
    const quote = await body(staff);
    check('quotation opens: Gold Membership, 5,000', /Gold Membership/.test(quote) && /5,000\.00/.test(quote));
    check('lead moved to Quote Sent', leadStage().startsWith('Quote Sent|'), `(${leadStage()})`);
    await visitor.goto(BASE + statusUrl, { waitUntil: 'networkidle2' });
    check('the visitor is told a quote was sent', /membership quote/i.test(await body(visitor)));

    step(10, 'The customer accepts: the quotation is confirmed');
    check('Confirm clicked', await staff.evaluate(() => { const b = document.querySelector('button[name="action_confirm"]'); if (b) { b.click(); return true; } return false; }));
    await sleep(3500);
    await shot(staff, 'j4_confirmed');

    step(11, 'Lead -> WON -> customer -> member -> membership active');
    check('lead is Won at 100% with the member activated', leadStage() === 'Won|100|true', `(${leadStage()})`);
    const member = sql(`select p.id||'|'||p.member_id||'|'||p.member_state||'|'||(select name from club_membership_plan where id=p.plan_id)||'|'||p.is_member from res_partner p where p.email='${EMAIL}' order by p.id desc limit 1`);
    console.log('member:', member);
    const [memberId, memberCode] = member.split('|');
    check('a Gold member exists with an ID and an active membership', /^\d+\|CC-\d+\|active\|Gold\|true$/.test(member));
    check('the welcome email is queued', Number(sql(`select count(*) from mail_mail m join mail_message g on g.id=m.mail_message_id where g.subject like 'Welcome to The Champions Club, ${NAME}%'`)) === 1);
    check('the member gets the Gold tier pricelist', sql(`select count(*) from ir_property p where p.name='property_product_pricelist' and p.res_id='res.partner,${memberId}' and p.value_reference like 'product.pricelist,%'`) === '1');
    await visitor.goto(BASE + statusUrl, { waitUntil: 'networkidle2' });
    await shot(visitor, 'j5_status_won');
    check('the visitor\'s status page now welcomes them as a member', /Welcome to the club/.test(await body(visitor)));

    // ============ 14-16. The member uses the platform
    step(14, 'The member books a court (the same call the booking screen makes)');
    const busyDay = sql("select value from ir_config_parameter where key='club_management.demo_busy_day'");
    const booked = await rpc(staff, 'club.booking', 'create_booking_api', [sql("select id from club_court where name='Tennis Court 2'"), busyDay, '07:00', Number(memberId)]);
    check('court booked for the member', booked.success === true, JSON.stringify(booked.booking || booked));
    check('Gold member pays ₹0 for the court', booked.booking && booked.booking.price === '₹0');
    check('the booking is in Odoo against this member',
      Number(sql(`select count(*) from club_booking where partner_id=${memberId} and tier='gold' and price=0 and state='confirmed'`)) === 1);

    step(15, 'The member buys a product (shop order, 20% Gold discount)');
    const towel = sql("select pp.id from product_product pp join product_template t on t.id=pp.product_tmpl_id where t.name->>'en_US'='Club Towel'");
    const shop = await rpc(staff, 'club.shop.order', 'place_order', [{ partner_id: Number(memberId), items: [{ product_id: Number(towel), qty: 2 }] }]);
    check('shop order placed: 2 towels, 700 - 140 = ₹560', shop.success === true && shop.total === '₹560.00', JSON.stringify(shop).slice(0, 160));

    step(16, 'The member orders at the bar (the real POS screen, 15% Gold discount)');
    await staff.goto(`${BASE}/web#action=club_management.action_club_bar_pos_ui`, { waitUntil: 'networkidle2' });
    await staff.waitForSelector('.cc-pos-product-card', { timeout: 20000 });
    await sleep(1500);
    await staff.evaluate(() => document.querySelector('.cc-member-selector-box').click());
    await sleep(500);
    check('the new member appears in the POS customer list', await clickByText(staff, '.cc-member-selector-box', NAME));
    await sleep(1200);
    check('Cold Coffee added', await clickByText(staff, '.cc-pos-product-card', 'Cold Coffee'));
    await sleep(1200);
    const pricing = await body(staff);
    check('POS prices the basket from the member\'s tier: ₹180 - 15% = ₹153.00', /₹180\.00/.test(pricing) && /₹153\.00/.test(pricing) && /Gold Member Discount \(15%\)/.test(pricing));
    await staff.click('.cc-btn-pay-now');
    await sleep(500);
    await clickByText(staff, '.cc-pay-method-btn', 'upi');
    await staff.click('.cc-btn-confirm-payment');
    await sleep(2500);
    await shot(staff, 'j6_bar_paid');
    check('payment success with an order reference', /Payment Successful/.test(await body(staff)) && /ORD\/\d+/.test(await body(staff)));

    // ============ 17. Everything flowed into Odoo for this one person
    step(17, 'Transactions flow into Odoo');
    const orders = sql(`select string_agg(channel||':'||total, ', ' order by id) from club_order where partner_id=${memberId}`);
    console.log('orders:', orders);
    check('one shop order (560) and one bar order (153) for the member', orders === 'shop:560.00, bar:153.00');
    check('the confirmed membership quote is a sales order of 5,000', sql(`select o.state||'|'||o.amount_untaxed from sale_order o join crm_lead l on l.id=o.opportunity_id where l.email_from='${EMAIL}'`) === 'sale|5000.00');
    check('one person, one record across CRM, membership, court, shop and bar',
      sql(`select (select count(*) from crm_lead where partner_id=${memberId} and member_activated)::text || (select count(*) from club_booking where partner_id=${memberId})::text || (select count(*) from club_order where partner_id=${memberId} and channel='shop')::text || (select count(*) from club_order where partner_id=${memberId} and channel='bar')::text`) === '1111');

    // the reports pick it up
    await staff.goto(`${BASE}/web#action=club_management.action_club_enquiry_funnel`, { waitUntil: 'networkidle2' });
    await sleep(2500);
    await shot(staff, 'j7_funnel');
    check('the enquiry funnel report counts the won lead', /Won/.test(await body(staff)));
    check('no browser errors on the staff side', staffLog.errors.length === 0 && !staffLog.console.filter((m) => !/favicon/i.test(m)).length, JSON.stringify(staffLog));

    console.log(`\n${result.filter(Boolean).length}/${result.length} checks passed`);
  } catch (e) {
    console.log('SCRIPT ERROR', e.message);
    await shot(visitor, 'j_error_visitor');
    await shot(staff, 'j_error_staff');
  } finally {
    await browser.close();
  }
})();
