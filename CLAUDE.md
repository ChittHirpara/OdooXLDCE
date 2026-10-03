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
- Create the database (recommended): `bash scripts/create_demo_db.sh [name]` (default `club`). It drops and rebuilds the DB, installs `club_management` + `club_website` WITHOUT Odoo demo data (so the company can switch to INR, see below) and loads only the club demo data. Then `docker compose up -d` and open http://localhost:8069 (admin / admin). Plain install, if you do not need rupees: `docker compose run --rm odoo odoo -d club -i club_management,club_website --stop-after-init` (club_website is the public site; club_management works alone).
- Update modules: `docker compose run --rm odoo odoo -d club -u club_management,club_website --stop-after-init`
- Tests (first run; later runs use `-u`): `docker compose run --rm odoo odoo -d club_test -i club_management,club_website --test-tags club_management --stop-after-init`
  (Git Bash on Windows mangles `/club_management` into a path, so use the plain tag; all tests of both modules carry the `club_management` tag, the website ones also `club_website`.)
- Tier discounts (POS bar + website shop): each membership plan auto-generates a pricelist ("Club Gold" etc.) with its shop % on product category "Club Shop" and bar % on "Bar & Cafeteria" (incl. child categories). Active members get their tier pricelist; POS configs get the tier pricelists automatically. Person B: put shop/bar products in those categories, and pick the member as customer in POS.
- Demo data: courts, members, products and date-relative activity, loaded by `scripts/create_demo_db.sh` (or automatically on a plain install with demo data). 5 courts (+4 from the frontend work), 9 members (gold/silver/junior, one expiring in 5 days, one expired), 11 shop/bar products (5 below reorder minimum), 2 weeks of history, a fully booked "busy evening" tomorrow, Friday social play, a CRM pipeline with a lead in every stage. Dates are relative to the install day. To reset, run the script again.
- Frontend <-> backend: the OWL screens (static/src/components) call the server with `orm.call("model", "method", ...)`. The backend side lives in `models/frontend_api.py` (thin adapters), `models/club_pos_and_shop.py` (pricing, orders, stock) and `club.booking` (`get_availability`, `create_booking_api`). `tests/test_frontend_api.py::test_every_orm_call_in_the_screens_has_a_backend_method` fails if a screen calls a model/method that does not exist; the screens otherwise swallow the error and show mock data, so keep it green. Prices are always computed on the server from the member's tier pricelist; bar tabs and shop orders create `club.order` records (menu: Club > Bar & Shop Orders) and deduct stock.
- Real-browser checks: `addons/club_management/tests/e2e/` (see its README). They book, check out and pay in headless Chrome and verify the database. Run them against a fresh demo DB before the demo.
- Currency: the club trades in rupees. As `club_management` installs, the main company is switched to INR once, and its pricelists with it (`models/res_company.py`). Odoo only allows that while the company has NO accounting entries, and Odoo's accounting demo data creates some, so a plain install with Odoo demo data stays in dollars (with a warning in the log). Use `scripts/create_demo_db.sh`, which installs without Odoo demo data. Only the main company is ever switched. A POS config in another currency simply does not get the club pricelists.
- Known gaps: "Choose <plan>" on the Membership Plans screen only shows a notification (no sign-up yet; `res.partner.register_or_renew_member` exists for it). The screens' top nav and the "Vikram Mehta" persona on the plans screen are static. `data/demo_club_data.xml` is in `data` (loads in production too), not `demo`. The earlier Odoo 19 `champions_club/` module was removed: its models duplicated ours by name and could not be installed together; its membership-contract idea (monthly billing, paused state) was not ported and is in git history.
- CRM workflow (all in `crm.lead`, no second CRM): enquiry -> lead (stage New, assigned to a club manager, follow-up call due next day, acknowledgment email with a private status link) -> staff move it Contacted > Interested -> "Create Membership Quote" (sale.order from the plan's product, lead -> Quote Sent) -> customer accepts = confirm the quote -> lead Won -> customer created/linked -> member created, plan activated, tier pricelist given, welcome email. Dragging the lead to Won or pressing Won does the same. Code: `models/crm_lead.py`, `models/sale_order.py`; staff screens: Club > Enquiries (CRM) and Reporting > Enquiry Funnel. Public intake: `crm.lead.create_club_enquiry` / `POST /club/enquiry` (honeypot field `website_url`; same email within 24h extends the same lead); visitors check progress at `/club/enquiry/status/<token>`. Follow-ups are Odoo activities (no custom task system). Junior leads need `member_date_of_birth` before activation. Staff group includes all-leads CRM and Sales; managers get Sales manager. Assignee can be set with system parameter `club_management.enquiry_assignee_id`.
- Public website (`addons/club_website`, depends on `website` + `club_management`, adds no data of its own): Home, Membership (plans from the DB), Courts (live availability grid, `static/src/js/availability.js`, reads `/club/availability`), Shop (browse + live stock + member prices; "Reserve" = a shop enquiry), Join/Contact (the enquiry form, `POST /join/submit`, honeypot), About, and the themed status page `/club/enquiry/status/<token>`. Public visitors can only view and enquire: every join, "request this slot" and "reserve" becomes a CRM lead. Odoo's stock `/contactus` redirects to our `/contact` so enquiries never bypass the CRM. Menus are created under `website.main_menu` WITHOUT `website_id` (Odoo then copies them into each website's own tree; setting `website_id` hides them). Data helpers for templates: model `club.website.data`. Company name/phone/email are set to the club in `club_website/data/website_data.xml`; change them in Settings > Companies.
- Docker note: the db image is built from `docker/postgres/Dockerfile` (adds `tzdata-legacy`). Without it, users whose browser reports `Asia/Calcutta` (India, Chrome) get `time zone "Asia/Calcutta" not recognized` on any screen that groups dates. After pulling, run `docker compose build db && docker compose up -d`.
- Club rules: timezone Asia/Kolkata, courts open 06:00-22:00, Friday = whole-day social play.