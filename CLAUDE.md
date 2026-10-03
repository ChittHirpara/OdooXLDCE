# Project: Sports Club Management System (Odoo Hackathon)

## Context
- 36-hour hackathon, team of 3. I am the BACKEND LEAD.
- Problem: unified Odoo platform for "The Champions Club" (tennis/cricket courts, gear shop, bar/cafeteria, 3 membership tiers: Gold, Silver, Junior).
- Teammates handle: POS/Inventory/eCommerce configuration (Person B) and Website/CRM UI/dashboards/pitch (Person C). I own all custom backend code.
- Detect the Odoo version from the repo (odoo-bin, __manifest__.py versions, docker files) and use matching syntax. Never assume.

## My scope (custom module `club_management`)
1. Membership plans: Gold, Silver, Junior with court rate, shop discount %, bar discount %, validity days.
2. Members: extend res.partner with tier, join/expiry dates, DOB (Junior = under 18), member ID, QR code, status (active/expired).
3. Courts and Bookings:
   - 1-hour sessions, start slots every 30 minutes
   - No overlapping bookings on the same court (Python constraint + SQL where possible)
   - Max 2 bookings per member per day
   - Friday social play: shared capacity per court (many players, one court)
   - Statuses: draft, confirmed, cancelled, done; cancel/reschedule supported
   - Walk-ins (no member) pay full price
4. Pricing: booking price derived from tier (Gold free/discounted, Silver standard, Junior discounted, walk-in full). Create invoice/sale line from booking.
5. Cron jobs: membership expiry reminder emails + auto-lapse.
6. Integration: member tier drives discounts in POS (bar) and website shop (via pricelists or loyalty) so ONE member record powers all three.
7. Website/API support: controllers for court availability and enquiry form that creates a crm.lead.
8. Reporting: pivot/graph views on bookings and revenue for the owner dashboard.
9. Demo data XML: members in all tiers, a busy-evening set of bookings, low-stock products.

## Standards
- Follow Odoo conventions: models/, views/, security/ir.model.access.csv, data/, demo/, controllers/, tests/.
- Every model needs access rules; add a club manager group and staff group.
- Use @api.constrains and clear ValidationError messages.
- Write TransactionCase tests for every booking rule (overlap, 2/day, 30-min slots, tier pricing, social play).
- Keep code simple and demo-ready. No over-engineering. Prefer reusing standard Odoo apps over rebuilding.
- Small commits, one feature per commit, clear messages. Don't touch files outside club_management unless needed, to avoid merge conflicts with teammates.

## Priority order (cut from the bottom if behind)
1. Booking engine + constraints
2. Tier-driven pricing/discounts across booking, shop, bar
3. Enquiry -> CRM flow and availability endpoint
4. Owner reports
5. Reminders, QR, cancel/reschedule polish

## Commands
Odoo 17.0 via Docker (docker-compose.yml, config/odoo.conf, custom addons in ./addons). Start Docker Desktop first.
- Run: `docker compose up -d` then open http://localhost:8069 (logs: `docker compose logs -f odoo`)
- Install: `docker compose run --rm odoo odoo -d club -i club_management --stop-after-init`
- Update module: `docker compose run --rm odoo odoo -d club -u club_management --stop-after-init`
- Tests (first run; later runs use `-u`): `docker compose run --rm odoo odoo -d club_test -i club_management --test-tags club_management --stop-after-init`
  (Git Bash on Windows mangles `/club_management` into a path, so use the plain tag; all our tests carry the `club_management` tag.)
- Tier discounts (POS bar + website shop): each membership plan auto-generates a pricelist ("Club Gold" etc.) with its shop % on product category "Club Shop" and bar % on "Bar & Cafeteria" (incl. child categories). Active members get their tier pricelist; POS configs get the tier pricelists automatically. Person B: put shop/bar products in those categories, and pick the member as customer in POS.
- Club rules: timezone Asia/Kolkata, courts open 06:00-22:00, Friday = whole-day social play.