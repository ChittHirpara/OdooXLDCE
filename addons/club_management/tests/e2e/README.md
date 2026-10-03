# Real-browser checks

The Python tests cover the server. These scripts drive the actual screens in headless
Chrome against a live Odoo, so they catch what Python cannot: a screen quietly falling
back to mock data, a template error, a filter the browser cannot evaluate.

They book courts, check out in the shop, pay bar tabs and open every report, then check
the **database** to prove each action really happened. They change data, so run them on a
throwaway demo database.

## Run

```bash
# 1. a fresh demo database and a server on it (from the repo root)
docker compose exec -T db dropdb -U odoo --if-exists club_demo
docker compose run --rm odoo odoo -d club_demo -i club_management --stop-after-init
docker compose run -d --service-ports --name club-web odoo odoo -d club_demo --db-filter='^club_demo$'

# 2. the checks (needs Node and Chrome on the host)
cd addons/club_management/tests/e2e
npm install
npm run all
```

Each script prints `PASS`/`FAIL` lines and saves screenshots to `out/`. The booking, shop
and bar checks expect the untouched demo data (for example 8 cricket bats in stock), so
rebuild the database between runs.

| Variable | Default |
|---|---|
| `ODOO_URL` | `http://localhost:8069` |
| `ODOO_DB` | `club_demo` |
| `CHROME_PATH` | `C:/Program Files/Google/Chrome/Application/chrome.exe` |
| `REPO` | the repository root (where `docker-compose.yml` lives) |

Login is `admin` / `admin` (the default for a database Odoo created itself).
