// A visitor books a court and orders from the shop on the website, instantly, with no enquiry.
// Real browser, anonymous visitor; the database is checked after every step.
const { execSync } = require('child_process');
const { launch, login, shot, sleep, text, BASE, DB, REPO } = require('./lib');

const sql = (q) => execSync(
  `docker compose exec -T db psql -U odoo -d ${DB} -tAc "${q.replace(/"/g, '\\"')}"`,
  { cwd: REPO }).toString().trim();

(async () => {
  const { browser, page, log } = await launch();
  const result = [];
  const check = (name, ok, extra = '') => { result.push(ok); console.log(`${ok ? 'PASS' : 'FAIL'}  ${name} ${extra}`); };
  page.on('dialog', (d) => d.accept());          // the "Cancel this booking?" confirmation
  const go = async (path, sel) => {
    log.console.length = 0; log.errors.length = 0; log.badResponses.length = 0;
    await page.goto(BASE + path, { waitUntil: 'networkidle2' });
    if (sel) await page.waitForSelector(sel, { timeout: 15000 });
    await sleep(500);
  };
  const clean = (name) => {
    const noise = log.console.filter((m) => !/favicon|DevTools|Failed to load resource.*(fonts|gstatic|googleapis)|ERR_NAME_NOT_RESOLVED|ERR_INTERNET/i.test(m));
    const bad = log.badResponses.filter((r) => !/fonts\.|gstatic|googleapis|^400 .*\/(book|club-shop)/.test(r));
    check(`${name}: no console errors / page errors / bad responses`, !noise.length && !log.errors.length && !bad.length,
      noise.length || log.errors.length || bad.length ? JSON.stringify({ noise, errors: log.errors, bad }) : '');
  };
  const body = () => page.$eval('#wrapwrap', (e) => e.innerText.replace(/\s+/g, ' '));
  const fill = async (sel, value) => { await page.click(sel, { clickCount: 3 }); await page.type(sel, value); };
  const submit = () => Promise.all([page.waitForNavigation({ waitUntil: 'networkidle2' }), page.click('.club-form button[type=submit]')]);
  const slotFree = (court, time) => page.evaluate((c, t) => {
    const row = [...document.querySelectorAll('.club-court-row')].find((r) => r.querySelector('h5').innerText === c);
    const a = row && [...row.querySelectorAll('.club-slot-free')].find((x) => x.innerText.trim().startsWith(t));
    return !!a;
  }, court, time);
  const clickSlot = (court, time) => page.evaluate((c, t) => {
    const row = [...document.querySelectorAll('.club-court-row')].find((r) => r.querySelector('h5').innerText === c);
    [...row.querySelectorAll('.club-slot-free')].find((x) => x.innerText.trim().startsWith(t)).click();
  }, court, time);
  const pickDate = async (value) => {
    await page.$eval('.js-date', (el, v) => { el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); }, value);
    await sleep(1800);
  };

  try {
    const day = sql("select value from ir_config_parameter where key='club_management.demo_busy_day'");
    const COURT = 'Tennis Court 3 (Floodlit)';

    // ============ 1. A guest books a court
    await go('/courts', '.club-court-row');
    await pickDate(day);
    check('the slot is free on the live grid', await slotFree(COURT, '07:00'));
    await clickSlot(COURT, '07:00');
    await page.waitForSelector('.club-book form', { timeout: 10000 });
    await shot(page, 'o1_book_form');
    let b = await body();
    check('the booking page shows the court, the time and the guest price (₹900)',
      /Tennis Court 3/.test(b) && /07:00 to 08:00/.test(b) && /₹900/.test(b) && /Confirm booking/.test(b));
    check('no enquiry or staff step is needed: there is a Confirm booking button', !!(await page.$('.club-form button[type=submit]')));

    // an empty form shows a clear message and keeps the page
    await submit();
    b = await body();
    check('submitting an empty form explains what is missing', /tell us your name/.test(b));
    await shot(page, 'o2_book_error');

    await fill('input[name=name]', 'Browser Guest');
    await fill('input[name=phone]', '+91 90000 11122');
    await fill('input[name=email]', 'browser.guest@example.com');
    await submit();
    await shot(page, 'o3_booked');
    b = await body();
    const ref = (b.match(/BK\/\d{5}/) || [])[0];
    check('"You are booked!" with a reference, instantly', /You are booked!/.test(b) && !!ref, `(${ref})`);
    check('the page shows the court, time, name, price and guest rate',
      /Tennis Court 3/.test(b) && /07:00 to 08:00/.test(b) && /Browser Guest/.test(b) && /₹900/.test(b) && /guest rate/.test(b));
    const row = sql(`select state||'|'||price||'|'||tier||'|'||booking_source||'|'||coalesce(guest_email,'') from club_booking where name='${ref}'`);
    console.log('booking in DB:', row);
    check('the booking is confirmed in Odoo: ₹900, guest, source website', row === 'confirmed|900.00|guest|website|browser.guest@example.com');
    check('a confirmation e-mail is queued', Number(sql(`select count(*) from mail_mail m join mail_message g on g.id=m.mail_message_id where g.subject like 'Court booked:%${ref}%'`)) === 1);
    check('a follow-up lead was filed so the club can offer a membership',
      Number(sql("select count(*) from crm_lead where email_from='browser.guest@example.com' and enquiry_type='court'")) === 1);
    const bookingUrl = page.url();

    // the grid now shows it as booked
    await go('/courts', '.club-court-row');
    await pickDate(day);
    check('the same slot is now booked on the live grid', !(await slotFree(COURT, '07:00')));
    clean('guest booking');

    // ============ 2. Cancel from the private link
    await page.goto(bookingUrl, { waitUntil: 'networkidle2' });
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle2' }), page.click('form[action$="/cancel"] button')]);
    await shot(page, 'o4_cancelled');
    b = await body();
    check('cancelling from the link works and says so', /Booking cancelled/.test(b) && /has been cancelled/.test(b));
    check('the booking is cancelled in Odoo', sql(`select state from club_booking where name='${ref}'`) === 'cancelled');
    await go('/courts', '.club-court-row');
    await pickDate(day);
    check('the slot is free again on the grid', await slotFree(COURT, '07:00'));

    // ============ 3. A member books at their tier price
    const otherDay = sql("select to_char(current_date + 6, 'YYYY-MM-DD')");   // CC-00001 is already at 2/day on the busy day
    await pickDate(otherDay);
    await clickSlot(COURT, '07:30');
    await page.waitForSelector('.club-book form', { timeout: 10000 });
    await page.click('.club-member-box summary');
    const wrong = await (async () => {
      await fill('input[name=member_ref]', 'CC-00001');
      await fill('input[name=member_email]', 'not.the.email@example.com');
      await submit();
      return body();
    })();
    check('a wrong member e-mail is refused with one vague message', /could not verify/.test(wrong));
    check('the member box stays open and the form is kept', (await page.$eval('.club-member-box', (e) => e.open)) === true);
    const memberEmail = sql("select email from res_partner where member_id='CC-00001'");
    await fill('input[name=member_ref]', 'cc-00001');
    await fill('input[name=member_email]', memberEmail.toUpperCase());
    await submit();
    await shot(page, 'o5_member_booked');
    b = await body();
    const mref = (b.match(/BK\/\d{5}/) || [])[0];
    check('the member is booked and shown at the Gold rate: ₹0', /You are booked!/.test(b) && /Gold member rate/.test(b) && /₹0/.test(b), `(${mref})`);
    check('the booking is against the real member record, tier gold, price 0',
      sql(`select p.member_id||'|'||b.tier||'|'||b.price||'|'||b.booking_source from club_booking b join res_partner p on p.id=b.partner_id where b.name='${mref}'`) === 'CC-00001|gold|0.00|website');

    // ============ 4. Staff see online bookings
    // (checked after the shop below)

    // ============ 5. The shop: cart, checkout, order
    await go('/club-shop', '.club-product');
    await page.evaluate(() => [...document.querySelectorAll('.club-product')].find((c) => c.innerText.includes('Cricket Bat')).click());
    await page.waitForSelector('.club-add-form', { timeout: 10000 });
    await shot(page, 'o6_product');
    check('the product page has quantity and Add to cart (no "reserve")', /Add to cart/.test(await body()) && !/Reserve for pickup/.test(await body()));
    const batStock = Number(sql("select coalesce(sum(q.quantity),0) from stock_quant q join product_product p on p.id=q.product_id join product_template t on t.id=p.product_tmpl_id join stock_location l on l.id=q.location_id where t.name->>'en_US'='Cricket Bat (English Willow)' and l.usage='internal'"));
    await fill('input[name=qty]', '2');
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle2' }), page.click('.club-add-form button[type=submit]')]);
    await shot(page, 'o7_cart');
    b = await body();
    check('the cart shows 2 × Cricket Bat at ₹4,200 = ₹8,400', /Cricket Bat/.test(b) && /₹4,200/.test(b) && /₹8,400/.test(b));
    await go('/club-shop', '.club-product');
    check('the shop shows the cart count', /Cart \(2\)/.test(await body()));
    await go('/club-shop/cart', 'table');
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle2' }), page.evaluate(() => [...document.querySelectorAll('a.btn')].find((a) => /Checkout/.test(a.innerText)).click())]);
    await page.waitForSelector('.club-form', { timeout: 10000 });

    await fill('input[name=name]', 'Shop Browser');
    await fill('input[name=phone]', '+91 90000 33344');
    await fill('input[name=email]', 'shop.browser@example.com');
    await page.click('#co-delivery');
    await submit();
    b = await body();
    check('home delivery without an address is refused', /delivery address/.test(b));
    await fill('textarea[name=address]', '14 Linking Road, Bandra, Mumbai 400050');
    await submit();
    await shot(page, 'o8_order');
    b = await body();
    const oref = (b.match(/ORD\/\d{5}/) || [])[0];
    check('the order is confirmed with a reference, ₹8,400, delivery address', /Thank you, Shop Browser/.test(b) && !!oref && /₹8,400/.test(b) && /14 Linking Road/.test(b), `(${oref})`);
    const order = sql(`select channel||'|'||source||'|'||total||'|'||fulfillment||'|'||coalesce(customer_email,'') from club_order where name='${oref}'`);
    check('saved as a website shop order for Browser customer', order === 'shop|website|8400.00|Home Delivery|shop.browser@example.com', `(${order})`);
    const after = Number(sql("select coalesce(sum(q.quantity),0) from stock_quant q join product_product p on p.id=q.product_id join product_template t on t.id=p.product_tmpl_id join stock_location l on l.id=q.location_id where t.name->>'en_US'='Cricket Bat (English Willow)' and l.usage='internal'"));
    check('stock was deducted in Odoo', after === batStock - 2, `(${batStock} -> ${after})`);
    check('the order confirmation e-mail is queued', Number(sql(`select count(*) from mail_mail m join mail_message g on g.id=m.mail_message_id where g.subject like 'Your Champions Club order ${oref}%'`)) === 1);
    await go('/club-shop', '.club-product');
    check('the cart is empty after ordering', !/Cart \(\d/.test(await body()));

    // member discount in the shop
    await go('/club-shop', '.club-product');
    await page.evaluate(() => [...document.querySelectorAll('.club-product')].find((c) => c.innerText.includes('Club Towel')).click());
    await page.waitForSelector('.club-add-form', { timeout: 10000 });
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle2' }), page.click('.club-add-form button[type=submit]')]);
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle2' }), page.evaluate(() => [...document.querySelectorAll('a.btn')].find((a) => /Checkout/.test(a.innerText)).click())]);
    await page.click('.club-member-box summary');
    await fill('input[name=member_ref]', 'CC-00001');
    await fill('input[name=member_email]', memberEmail);
    await submit();
    b = await body();
    check('a member gets the Gold shop discount: Club Towel ₹350 - 20% = ₹280', /Member discount \(Gold\)/.test(b) && /-₹70/.test(b) && /₹280/.test(b));
    clean('shop');

    // ============ 6. Phone width
    await page.setViewport({ width: 390, height: 800, isMobile: true });
    await go('/club-shop/cart', '.club-site');
    for (const path of ['/club-shop/cart', '/join', bookingUrl.replace(BASE, '')]) {
      await go(path, '.club-site');
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      check(`mobile 390px: ${path.slice(0, 22)} has no sideways scrolling`, overflow <= 1, `(overflow ${overflow}px)`);
    }
    await page.setViewport({ width: 1500, height: 1000 });

    // ============ 7. Staff see it all in Odoo
    const staffContext = await browser.createBrowserContext();
    const staff = await staffContext.newPage();
    await staff.setViewport({ width: 1500, height: 1000 });
    await login(staff);
    await staff.goto(`${BASE}/web#action=club_management.action_club_booking`, { waitUntil: 'networkidle2' });
    await staff.waitForSelector('.o_list_view', { timeout: 20000 });
    await sleep(1000);
    const bookings = await staff.$eval('.o_list_view', (e) => e.innerText.replace(/\s+/g, ' '));
    await shot(staff, 'o9_staff_bookings');
    check('staff see the online bookings in Club > Bookings with source Website', bookings.includes(mref) && /Website/.test(bookings));
    await staff.goto(`${BASE}/web#action=club_management.action_club_order`, { waitUntil: 'networkidle2' });
    await staff.waitForSelector('.o_list_view', { timeout: 20000 });
    await sleep(1000);
    const orders = await staff.$eval('.o_list_view', (e) => e.innerText.replace(/\s+/g, ' '));
    await shot(staff, 'o10_staff_orders');
    check('staff see the online orders in Club > Bar & Shop Orders with source Website', orders.includes(oref) && /Website/.test(orders));

    console.log(`\n${result.filter(Boolean).length}/${result.length} checks passed`);
  } catch (e) {
    console.log('SCRIPT ERROR', e.message);
    await shot(page, 'o_error');
  } finally {
    await browser.close();
  }
})();
