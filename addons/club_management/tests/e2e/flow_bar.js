const { execSync } = require('child_process');
const { launch, login, openAction, shot, sleep, text, DB, REPO } = require('./lib');

const sql = (q) => execSync(
  `docker compose exec -T db psql -U odoo -d ${DB} -tAc "${q.replace(/"/g, '\\"')}"`,
  { cwd: REPO }).toString().trim();

const clickWhere = async (page, selector, regex) => {
  const ok = await page.evaluate((sel, re) => {
    const el = [...document.querySelectorAll(sel)]
      .filter((e) => new RegExp(re, 'i').test(e.innerText) && e.offsetParent !== null)
      .sort((a, b) => a.innerText.length - b.innerText.length)[0];
    if (el) { el.click(); return true; }
    return false;
  }, selector, regex);
  if (!ok) throw new Error(`no visible ${selector} matching ${regex}`);
};

const stockOf = (name) => Number(sql(`select coalesce(sum(q.quantity),0) from stock_quant q join product_product p on p.id=q.product_id join product_template t on t.id=p.product_tmpl_id join stock_location l on l.id=q.location_id where t.name->>'en_US'='${name}' and l.usage='internal'`));

async function chooseMember(page, name) {
  await page.evaluate(() => document.querySelector('.cc-member-selector-box').click());   // top box opens the picker
  await sleep(500);
  await clickWhere(page, '.cc-member-selector-box', name);
  await sleep(1200);
}
async function addItem(page, name, times = 1) {
  for (let i = 0; i < times; i++) {
    await clickWhere(page, '.cc-pos-product-card', name);
    await sleep(400);
  }
  await sleep(1000);
}
const orderPanel = async (page) => (await text(page, '.o_action_manager'))[0];

(async () => {
  const { browser, page, log } = await launch();
  const result = [];
  const check = (name, ok, extra = '') => { result.push(ok); console.log(`${ok ? 'PASS' : 'FAIL'}  ${name} ${extra}`); };
  try {
    await login(page);
    const sandwichBefore = stockOf('Club Sandwich');
    const coffeeBefore = stockOf('Cold Coffee');
    const ordersBefore = Number(sql("select count(*) from club_order where channel='bar'"));

    await openAction(page, 'club_management.action_club_bar_pos_ui', '.cc-pos-product-card');
    await sleep(1500);
    const cards = await text(page, '.cc-pos-product-card');
    const shake = cards.find((c) => c.includes('Protein Shake'));
    check('out-of-stock item is flagged from real stock', /OUT OF STOCK/i.test(shake || ''));
    const stale = cards.filter((c) => /Artisanal Cappuccino|Espresso Single Origin|Smash Burger/.test(c));
    console.log('(teammate sample products present as real catalog rows:', stale.length, ')');
    const startPanel = await orderPanel(page);
    check('no leftover mock cart on load', !/Smash Burger x|Subtotal ₹530/.test(startPanel));

    // 1. Gold member
    await chooseMember(page, 'Arjun Mehta');
    await addItem(page, 'Cold Coffee', 2);
    await addItem(page, 'Club Sandwich', 1);
    await shot(page, 'p1_cart');
    let panel = await orderPanel(page);
    console.log('panel:', panel.match(/Subtotal.{0,200}/)?.[0]);
    check('server prices the basket: 15% Gold bar discount (₹580 -> ₹493.00)',
      /₹580\.00/.test(panel) && /₹493\.00/.test(panel) && /Gold Member Discount \(15%\)/.test(panel));

    await page.click('.cc-btn-pay-now');
    await sleep(600);
    await clickWhere(page, '.cc-pay-method-btn', 'upi');
    await shot(page, 'p2_pay');
    await page.click('.cc-btn-confirm-payment');
    await sleep(2500);
    await shot(page, 'p3_success');
    const success = await orderPanel(page);
    const ref = (success.match(/ORD\/\d+/) || [])[0];
    check('payment success shows a real order number', !!ref, `(${ref})`);

    const row = sql(`select o.name||'|'||o.customer_name||'|'||o.subtotal||'|'||o.discount||'|'||o.total||'|'||o.payment_method||'|'||coalesce(t.name,'-') from club_order o left join club_pos_table t on t.id=o.table_id where o.channel='bar' order by o.id desc limit 1`);
    console.log('order in DB:', row);
    check('order saved: Arjun Mehta, 580 - 87 = 493, UPI', /Arjun Mehta\|580\.00\|87\.00\|493\.00\|upi/.test(row));
    check('stock deducted for tracked products', stockOf('Club Sandwich') === sandwichBefore - 1 && stockOf('Cold Coffee') === coffeeBefore - 2,
      `(sandwich ${sandwichBefore}->${stockOf('Club Sandwich')}, coffee ${coffeeBefore}->${stockOf('Cold Coffee')})`);

    // 2. lapsed member gets no discount
    await page.click('.cc-btn-new-order');
    await sleep(800);
    await chooseMember(page, 'Karan Malhotra');
    await addItem(page, 'Cold Coffee', 1);
    panel = await orderPanel(page);
    check('lapsed member pays full price (₹180.00, no discount)',
      /₹180\.00/.test(panel) && !/Silver Member Discount/.test(panel), `(${panel.match(/No Discount|Member Discount \(\d+%\)/g)})`);

    // 3. walk-in + cash
    await chooseMember(page, 'Walk-in Guest');
    panel = await orderPanel(page);
    check('walk-in pays full price', /₹180\.00/.test(panel));
    await page.click('.cc-btn-pay-now');
    await sleep(500);
    await clickWhere(page, '.cc-pay-method-btn', 'cash');
    await page.click('.cc-btn-confirm-payment');
    await sleep(2500);
    const wrow = sql("select customer_name||'|'||total||'|'||payment_method from club_order where channel='bar' order by id desc limit 1");
    check('walk-in cash order saved at full price', /Walk-in Guest\|180\.00\|cash/.test(wrow), `(${wrow})`);
    await page.click('.cc-btn-new-order');
    await sleep(500);

    // 4. orders tab + shift panel come from real orders
    await clickWhere(page, '.cc-top-btn', 'orders|history');
    await sleep(800);
    await shot(page, 'p4_history');
    const hist = await orderPanel(page);
    check('Orders tab lists the real orders', hist.includes(ref) && /Walk-in Guest/.test(hist));
    await clickWhere(page, '.cc-top-btn', 'shift');
    await sleep(800);
    await shot(page, 'p5_shift');
    const shift = await orderPanel(page);
    console.log('shift:', shift.match(/Total.{0,160}/)?.[0]);
    const nOrders = Number(sql("select count(*) from club_order where channel='bar'")) - ordersBefore;
    check('shift panel is built from real orders (₹673 across 2 orders)', /₹673/.test(shift) && nOrders === 2, `(orders today ${nOrders})`);

    console.log('\nconsole warnings/errors:', JSON.stringify(log.console));
    console.log('page errors:', JSON.stringify(log.errors));
    console.log('bad responses:', JSON.stringify(log.badResponses));
    console.log(`\n${result.filter(Boolean).length}/${result.length} checks passed`);
  } catch (e) {
    console.log('SCRIPT ERROR', e.message);
    await shot(page, 'p_error');
  } finally {
    await browser.close();
  }
})();
