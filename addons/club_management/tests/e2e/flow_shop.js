const { execSync } = require('child_process');
const { launch, login, openAction, shot, sleep, text, DB, REPO } = require('./lib');

const sql = (q) => execSync(
  `docker compose exec -T db psql -U odoo -d ${DB} -tAc "${q.replace(/"/g, '\\"')}"`,
  { cwd: REPO }).toString().trim();

const clickText = async (page, selector, regex) => {
  const ok = await page.evaluate((sel, re) => {
    const el = [...document.querySelectorAll(sel)]
      .filter((e) => new RegExp(re, 'i').test(e.innerText) && e.offsetParent !== null)
      .sort((a, b) => a.innerText.length - b.innerText.length)[0];
    if (el) { el.click(); return true; }
    return false;
  }, selector, regex);
  if (!ok) {
    console.log('visible buttons:', await text(page, 'button'));
    throw new Error(`no visible ${selector} matching ${regex}`);
  }
};

(async () => {
  const { browser, page, log } = await launch();
  const result = [];
  const check = (name, ok, extra = '') => { result.push(ok); console.log(`${ok ? 'PASS' : 'FAIL'}  ${name} ${extra}`); };
  try {
    await login(page);
    const stockOf = (name) => Number(sql(`select coalesce(sum(q.quantity),0) from stock_quant q join product_product p on p.id=q.product_id join product_template t on t.id=p.product_tmpl_id join stock_location l on l.id=q.location_id where t.name->>'en_US'='${name}' and l.usage='internal'`));
    const ordersBefore = Number(sql("select count(*) from club_order where channel='shop'"));
    const stockBefore = stockOf('Cricket Bat (English Willow)');

    await openAction(page, 'club_management.action_club_shop_ui', '.cc-product-card');
    await sleep(1200);
    const cards = await text(page, '.cc-product-card');
    const batCard = cards.find((c) => c.includes('Cricket Bat'));
    console.log('bat card:', batCard);
    check('catalog shows real stock for the bat', /8 in stock/.test(batCard || ''), `(db stock ${stockBefore})`);
    check('catalog shows the Gold price from the server (₹3,360)', /₹3,360/.test(batCard || ''));

    await page.evaluate(() => [...document.querySelectorAll('.cc-product-card')].find((c) => c.innerText.includes('Cricket Bat')).click());
    await sleep(600);
    await shot(page, 's1_detail');
    await clickText(page, 'button', 'add to cart');
    await sleep(500);
    await clickText(page, 'button, .cc-cart-btn, [class*="cart"]', '^\\s*.{0,3}cart\\b');
    await sleep(600);
    await shot(page, 's2_cart');
    await clickText(page, 'button', 'checkout');
    await sleep(600);
    await shot(page, 's3_checkout');
    await clickText(page, 'button', 'place order|confirm order|complete');
    await sleep(2500);
    await shot(page, 's4_done');

    const done = (await text(page, '.o_action_manager'))[0];
    const ref = (done.match(/ORD\/\d+/) || [])[0];
    console.log('confirmation mentions order:', ref, '| total shown:', (done.match(/₹3,360\.00|₹3,360/) || [])[0]);
    check('confirmation shows a real order number from Odoo', !!ref);

    const row = sql(`select name||'|'||channel||'|'||customer_name||'|'||subtotal||'|'||discount||'|'||total||'|'||coalesce(fulfillment,'') from club_order where channel='shop' order by id desc limit 1`);
    console.log('order in DB:', row);
    check('order saved with the member, 20% discount and totals', /Chitt Hirpara\|4200\.00\|840\.00\|3360\.00/.test(row));
    check('exactly one new shop order', Number(sql("select count(*) from club_order where channel='shop'")) === ordersBefore + 1);
    const stockAfter = stockOf('Cricket Bat (English Willow)');
    check('inventory was deducted in Odoo stock', stockAfter === stockBefore - 1, `(${stockBefore} -> ${stockAfter})`);

    await openAction(page, 'club_management.action_club_shop_ui', '.cc-product-card');
    await sleep(1200);
    const batAfter = (await text(page, '.cc-product-card')).find((c) => c.includes('Cricket Bat'));
    check('reloaded catalog shows the reduced stock', /7 in stock/.test(batAfter || ''), `(${batAfter && batAfter.match(/\d+ in stock/)})`);

    console.log('\nconsole warnings/errors:', JSON.stringify(log.console));
    console.log('page errors:', JSON.stringify(log.errors));
    console.log('bad responses:', JSON.stringify(log.badResponses));
    console.log(`\n${result.filter(Boolean).length}/${result.length} checks passed`);
  } catch (e) {
    console.log('SCRIPT ERROR', e.message);
    await shot(page, 's_error');
  } finally {
    await browser.close();
  }
})();
