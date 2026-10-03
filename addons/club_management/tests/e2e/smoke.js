const { launch, login, openAction, shot, sleep } = require('./lib');

const SCREENS = [
  ['club_management.action_club_membership_plans_ui', 'plans'],
  ['club_management.action_club_court_booking_ui', 'booking'],
  ['club_management.action_club_shop_ui', 'shop'],
  ['club_management.action_club_bar_pos_ui', 'bar'],
];

(async () => {
  const { browser, page, log } = await launch();
  try {
    await login(page);
    for (const [xmlid, name] of SCREENS) {
      log.console.length = 0; log.errors.length = 0; log.badResponses.length = 0;
      await openAction(page, xmlid, '[class*="cc-"]');
      await sleep(2500);
      await shot(page, 'x_' + name);
      const body = await page.$eval('.o_action_manager', (e) => e.innerText.replace(/\s+/g, ' ').slice(0, 700));
      console.log(`\n=== ${name}\n${body}`);
      console.log('console warnings/errors:', JSON.stringify(log.console, null, 1));
      console.log('page errors:', JSON.stringify(log.errors));
      console.log('bad responses:', JSON.stringify(log.badResponses));
    }
  } catch (e) {
    console.log('SCRIPT ERROR', e.message);
    await shot(page, 'x_error');
  } finally {
    await browser.close();
  }
})();
