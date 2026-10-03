# Real-browser checks

The Python tests cover the server. These scripts drive the actual screens in headless
Chrome against a live Odoo, so they catch what Python cannot: a screen quietly falling
back to mock data, a template error, a filter the browser cannot evaluate, a menu that
never reaches the site.

They book courts, check out in the shop, pay bar tabs, work the CRM and browse the public
website, then check the **database** to prove each action really happened. They change
data, so run them on a throwaway demo database.

| Script | What it proves |
|---|---|
| `smoke.js` | the four custom screens load live data with no console warnings |
| `flow_booking.js` | book, price, persist, list and cancel a court |
| `flow_shop.js` | shop checkout: member price, order, stock deducted |
| `flow_bar.js` | bar POS: member pricing, payment, stock, shift totals, history |
| `flow_native.js` | member QR, reschedule wizard, reports, order list |
| `flow_crm.js` | staff CRM: pipeline, lead form, quote, accept, member created |
| `flow_website.js` | the public site as an anonymous visitor, incl. the enquiry form and mobile width |
| `flow_journey.js` | the whole story: visitor enquiry > CRM > quote > won > member > court, shop, bar |

## Run

```bash
# 1. a fresh demo database and a server on it (from the repo root)
docker compose build db            # first time: Postgres image with legacy timezone names
docker compose exec -T db dropdb -U odoo --if-exists club_demo
docker compose run --rm odoo odoo -d club_demo -i club_management,club_website --stop-after-init
docker compose run -d --service-ports --name club-web odoo odoo -d club_demo --db-filter='^club_demo$'

# 2. the checks (needs Node and Chrome on the host)
cd addons/club_management/tests/e2e
npm install
npm run all
```

Each script prints `PASS`/`FAIL` lines and saves screenshots to `out/`. The booking, shop,
bar and CRM checks expect the untouched demo data (for example 8 cricket bats in stock),
and `flow_journey.js` creates a member, so rebuild the database between full runs.

| Variable | Default |
|---|---|
| `ODOO_URL` | `http://localhost:8069` |
| `ODOO_DB` | `club_demo` |
| `CHROME_PATH` | `C:/Program Files/Google/Chrome/Application/chrome.exe` |
| `REPO` | the repository root (where `docker-compose.yml` lives) |

Login is `admin` / `admin` (the default for a database Odoo created itself).
