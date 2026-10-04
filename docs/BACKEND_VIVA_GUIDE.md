# Backend Viva Guide: `club_management` (Odoo 17)

A study guide for explaining the backend of **The Champions Club** system. For every part it says what it is, where it lives, what the code does, and where it is used.

Stack: Odoo 17.0, PostgreSQL, Docker. Custom addons: `club_management` (all backend logic) and `club_website` (public site).
Club rules: timezone Asia/Kolkata, courts open 06:00-22:00, Friday is whole-day social play, currency INR.

---

## 1. The 60-second pitch

> One member record powers everything. A visitor enquires, becomes a CRM lead, gets a membership quote, accepts it, and is automatically made a member with a tier. That tier then decides the court price, the shop discount and the bar discount. Every sale (membership, court, shop, bar) becomes an invoice tagged with its revenue source, and the owner dashboard reads it all from one place.

Why this design: we **reuse standard Odoo apps** (CRM, Sales, Accounting, POS, Website, Stock) and only add what Odoo does not have: plans, courts and bookings, and the glue between them.

---

## 2. Big picture: the 9-stage flow and who does what

| # | Stage | Main code |
|---|-------|-----------|
| 1 | CRM lead New > Contacted > Interested > Quote | `models/crm_lead.py`, `data/crm_pipeline.xml` |
| 2 | Quote, accept, invoice | `crm_lead.action_create_membership_quote`, `models/sale_order.py` |
| 3 | Membership activation | `crm_lead._club_activate_member`, `res_partner.action_activate_membership` |
| 4 | Member dashboard | `club_website/controllers/member.py` (`/my/club`) |
| 5 | Court booking | `models/booking.py`, `models/court.py` |
| 6 | Shop | `models/club_pos_and_shop.py`, `club_website/controllers/online.py` |
| 7 | Bar / POS | `models/club_pos_and_shop.py`, `models/frontend_api.py`, `models/pos_config.py` |
| 8 | Accounting | `models/account_move.py`, `club_order._create_invoice`, `sale_order._club_invoice_membership` |
| 9 | Owner dashboard | `models/club_dashboard.py`, `static/src/components/owner_dashboard` |

```
Website form --> crm.lead --> sale.order (membership product) --confirm--> lead Won
                                                          |                  |
                                                  invoice (club_source=membership)
                                                                              v
                                            res.partner: is_member, plan_id, expiry_date, member_id
                                                                              |
              tier pricelist  -------------------------------------------------+--------------------------
              |                         |                          |                                      |
        club.booking price        website shop price          POS / bar price                  portal /my/club
```

---

## 3. Module structure

```
addons/club_management/
  __manifest__.py        depends: base, web, mail, account, product, crm, sale_crm, point_of_sale, stock
  models/                all business logic
  views/                 backend forms, lists, menus, reports, client actions
  security/              groups (security.xml) + access rules (ir.model.access.csv)
  data/                  plans, categories, pricelist, products, CRM stages, mail templates, cron, sequences
  demo/                  demo courts, members, products, activity
  controllers/main.py    public JSON/HTTP API
  wizard/                reschedule wizard
  static/src/components/ OWL screens (plans, court grid, shop, bar POS, owner dashboard, analytics, staff)
  tests/                 TransactionCase tests + e2e (headless Chrome)
addons/club_website/     public site: controllers, QWeb templates, availability JS
```

Load order in the manifest matters: security first, then data (plans before products before CRM), then views, then menus.

---

## 4. Models: file by file

### 4.1 `models/membership_plan.py` - `club.membership.plan`

**What:** Gold, Silver, Junior. Fields: `code`, `price`, `court_rate`, `shop_discount`, `bar_discount`, `validity_days`, `product_id`, `pricelist_id`. SQL constraints: unique `code`, `validity_days > 0`.

**Key idea:** saving a plan *automatically builds the Odoo objects that make discounts work*.

```python
def create(self, vals_list):
    plans = super().create(vals_list)
    plans._sync_pricelist()   # "Club Gold" pricelist: shop % on Club Shop, bar % on Bar & Cafeteria
    plans._sync_product()     # service product used on the membership quote
    return plans
```

- `_sync_pricelist()` creates one `product.pricelist` per plan with percentage rules per product category. It runs `sudo()` because club managers may not have Sales rights.
- `_sync_product()` creates a service product "Gold Membership (365 days)" priced at the plan fee. It sits outside the shop and bar categories so it never appears in POS or the shop.
- `get_frontend_plans()` formats plans for the OWL Membership Plans screen.

**Used by:** quotes (product), POS, shop and bookings (pricelist, rates), the website membership page.

### 4.2 `models/res_partner.py` - extends `res.partner` (the member)

**Why extend partner:** Odoo POS, shop, sales and invoices already key on the partner. A member *is* a partner, so one record serves all three channels.

Fields: `is_member`, `plan_id`, `member_id` (sequence), `join_date`, `expiry_date`, `date_of_birth`, `member_state` (stored computed: none/active/expired), `qr_code` (computed from `member_id`), `is_junior`.

| Function | What it does |
|---|---|
| `_compute_member_state` | `@api.depends('is_member','expiry_date')`; expired when `expiry_date < today` |
| `_check_junior_plan` | `@api.constrains`; Junior plan requires age under 18 |
| `_assign_member_id` | gives the next `club.member` sequence number |
| `_sync_club_pricelist` | active member gets their tier pricelist; when membership ends only a *tier* pricelist is removed (manual ones are left) |
| `action_activate_membership` | sets `is_member`, `join_date`, `expiry_date = today + validity_days` |
| `_get_active_plan(on=None)` | **the single rule**: returns the plan only if the membership is still valid on that date |
| `_cron_lapse_memberships` | daily; marks expired members |
| `_cron_send_expiry_reminders` | daily; one mail per expiry date via `expiry_reminder_for` (renewing re-arms it) |
| `_club_ensure_portal_login` | creates a portal user (login = e-mail, never staff) and sends the "set password" mail |
| `register_or_renew_member(partner_id, plan_code)` | used by the plans screen to sign up or renew |

```python
def _get_active_plan(self, on=None):
    on = on or club_today()
    if self.is_member and self.plan_id and self.expiry_date and self.expiry_date >= on:
        return self.plan_id
    return self.env['club.membership.plan']   # expired = no benefits
```

**Used by:** booking price, shop and bar price (`club.order.service._plan_for`), dashboard.

### 4.3 `models/court.py` - `club.court`

Fields: `name`, `sport`, `list_price` (walk-in hourly price), `social_capacity` (default 8), `open_hour`/`close_hour`. Constraints: price >= 0, capacity > 0, open < close (`_check_hours`).
Functions: `get_availability(day)`, `get_availability_matrix(...)` build the slot grid for screens and the website; `get_courts_list()` for the API.

### 4.4 `models/booking.py` - `club.booking` (the core)

Fields: `court_id`, `partner_id` or `walkin_name`, `start_datetime` (UTC), computed stored `end_datetime`, `booking_date` (club-local date), `is_social`, `start_hour`, `players`, `state` (draft/confirmed/cancelled/done), `price`, `tier`, `invoice_id`, guest contact, `access_token`.

Constants: `SLOT_MINUTES=30`, `BOOKING_DURATION=1h`, `MAX_BOOKINGS_PER_DAY=2`, `FRIDAY=4`.

**Time handling:** Odoo stores UTC. `to_club_time(dt)` converts to Asia/Kolkata. Rules (date, Friday, opening hours) use club time. `_compute_times` stores `booking_date`, `is_social` and `start_hour` in club time, so reports group correctly.

**Pricing (computed and stored):**
```python
@api.depends('court_id.list_price','booking_date','partner_id.is_member',
             'partner_id.plan_id.court_rate','partner_id.expiry_date')
def _compute_price(self):
    plan = booking._get_member_plan()          # valid member on the booking date, else empty
    booking.price = plan.court_rate if plan else booking.court_id.list_price
    booking.tier  = plan.code if plan else 'guest'
```
Gold = rate 0 or low, Silver = standard, Junior = discounted, walk-in/expired = full `list_price`.

**Constraints (every one has a test):**

| Rule | Function |
|---|---|
| member or walk-in name required | `_check_customer` |
| start on :00 or :30, inside court hours | `_check_slot` |
| no overlap; Friday shared capacity | `_check_availability` |
| max 2 per member per day | `_check_daily_limit` |
| max 2 per guest per day (by phone or e-mail) | `_check_guest_daily_limit` |
| `players > 0` | SQL constraint |

**Overlap and race protection (important viva point):**
```python
self.env.cr.execute('SELECT id FROM club_court WHERE id IN %s FOR UPDATE', ...)
others = self.search([... start < booking.end, end > booking.start, state != 'cancelled'])
```
`FOR UPDATE` locks the court row, so two simultaneous transactions on the same court are serialised and cannot both pass the check. This is a database-level lock, not only a Python check. On Fridays the same function sums `players` of overlapping bookings against `social_capacity` for both half-hour moments of the session.

**Workflow:** `action_confirm`, `action_cancel` (blocked if the invoice is posted: issue a credit note), `action_done`, `action_draft`, `action_reschedule(new_start, court)` (all rules re-checked; blocked if the price would change on an invoiced booking), `action_create_invoice` (draft invoice, `club_source='court'`; walk-ins go to the shared "Walk-in Customer").

**API methods for screens/website:** `calculate_booking_price`, `create_member_booking`, `get_availability`, `create_booking_api`, `cancel_member_booking`, `get_partner_bookings`, `create_public_booking` (guest booking within 14 days, sends a confirmation, files a follow-up lead), `get_by_token`, `cancel_by_visitor`.

`wizard/booking_reschedule.py` is a `TransientModel` giving staff a form to reschedule.

### 4.5 `models/crm_lead.py` - extends `crm.lead`

Adds enquiry fields: `enquiry_ref`, `enquiry_token` (secret status link), `interested_plan_id`, `enquiry_type`, `member_date_of_birth`, `member_activated`.

| Function | Purpose |
|---|---|
| `create_club_enquiry(...)` | public intake; the same e-mail within 24h extends the same lead; assigns a manager, schedules a follow-up call for the next day, sends an acknowledgement |
| `club_enquiry_status(token)` / `_club_public_status` | what a visitor sees; internal stage names stay hidden (`PUBLIC_STATUS`) |
| `action_create_membership_quote` | builds a `sale.order` with the plan's product and moves the lead to Quote Sent |
| `_club_advance_to(stage)` | moves forward only, never backwards or out of Won |
| `write` override | when a lead becomes Won (drag or button) it calls `_club_activate_member` |
| `_club_activate_member` | customer, then plan, then `action_activate_membership`, portal login, welcome mail; a validation error (e.g. Junior without birth date) is logged on the lead and a to-do is scheduled |
| `action_join_club` | one-click "Join the Club" button |

### 4.6 `models/sale_order.py` - extends `sale.order`

```python
def action_confirm(self):                       # customer accepts the quote
    res = super().action_confirm()
    for order in self.filtered('opportunity_id'):
        if order._club_is_membership_quote():
            order._club_invoice_membership()    # post invoice in a savepoint
            order.opportunity_id.action_set_won()   # triggers member creation
    return res

def _prepare_invoice(self):                     # tags the invoice source
    vals = super()._prepare_invoice()
    if self.opportunity_id and self._club_is_membership_quote():
        vals['club_source'] = 'membership'
    return vals
```
Also `action_quotation_sent` advances the lead to Quote Sent. Note: the membership **starts on acceptance**, not on payment. The invoice stays outstanding until paid.

### 4.7 `models/account_move.py` - extends `account.move`

`club_source` (membership/court/shop/bar, indexed) is how accounting separates the four revenue streams. `_invoice_paid_hook` e-mails a payment receipt for membership and court invoices (shop and bar are paid at the till and already get a confirmation).

### 4.8 `models/club_order.py` - `club.order`, `club.order.line`

A completed bar tab or shop order. Fields: `channel` (bar/shop), `payment_method` (cash/card/UPI), `plan_id` (tier applied), `list_price` vs `unit_price` per line, stored totals (`subtotal`, `discount`, `total`), `access_token`, `invoice_id`.

`_create_invoice()` posts a customer invoice (`club_source = channel`) and `_register_payment()` pays it (cash journal for cash, bank otherwise), all inside a **savepoint with logging**: accounting must never block a sale at the till. Trade-off: if it fails the order exists without an invoice.

### 4.9 `models/club_pos_and_shop.py`

- `club.pos.table`: bar tables and their state.
- `product.product` extension: `get_shop_catalog`, `get_bar_products` (stock, image URL, member price).
- `club.order.service` (AbstractModel) is the **server-side pricing and checkout engine**:

```python
unit = plan.pricelist_id._get_product_price(product, qty) if plan.pricelist_id else product.list_price
```
`calculate_order_pricing` (preview), `_check_and_deduct_stock` (deducts from the warehouse stock quants, error if short), `_create_order`, `process_pos_payment` (bar), `place_public_order` (website), `process_shop_checkout`. **Prices are never trusted from the client.**

### 4.10 `models/frontend_api.py`

Thin adapters with the model/method names the OWL screens call (`club.pos.product`, `club.pos.order`, `club.shop.order`...). They convert errors to friendly messages. The test `test_every_orm_call_in_the_screens_has_a_backend_method` fails if a screen calls a missing method.

### 4.11 `models/pos_config.py`

On creating a POS config, `_enable_club_pricelists` adds the tier pricelists so choosing a member as customer applies their discount. Pricelists in another currency are skipped.

### 4.12 `models/res_company.py`

`_register_hook` runs once and switches the main company to INR (Odoo only allows it while there are no accounting entries; hence `scripts/create_demo_db.sh` installs without Odoo demo data).

### 4.13 `models/club_dashboard.py` - `club.dashboard` (AbstractModel)

Owner numbers computed on the server: `get_dashboard_data(period)`, `get_analytics`, `get_staff_overview`, `get_monitoring`, with helper `_revenue(date_from, date_to)`.

```python
def _require_manager(self, what): ...   # raises AccessError unless group_club_manager
```
Revenue by source: membership = confirmed sale lines of plan products; court = non-cancelled bookings; shop/bar = `club.order` totals. Utilization = distinct booked court-hours / (courts x 16 open hours x days). Outstanding = posted club invoices with `payment_state` in not_paid/partial. Uses `sudo()` only **after** the manager check.

### 4.14 `models/club_support.py`

`club.feedback` (1-5 star ratings by area, public create) and `club.ticket` (complaints/refunds with `mail.thread`, states new/progress/resolved/closed, public token status page).

### 4.15 `models/demo_data.py` - `club.demo`

Loads date-relative demo: members, 2 weeks of history, a fully booked "busy evening" tomorrow, Friday social play, a CRM pipeline with a lead per stage, low-stock products.

### 4.16 `models/res_users.py`
`_club_send_invitation` sends Odoo's password-set e-mail to new portal users.

---

## 5. Controllers (HTTP/JSON API)

`club_management/controllers/main.py`:

| Route | Auth | Purpose |
|---|---|---|
| `GET /club/availability` | public | court availability (website grid reads this) |
| `POST /club/enquiry` | public | creates a `crm.lead` (honeypot field `website_url`) |
| `GET /club/enquiry/status/<token>` | public | themed status page |
| `GET /club/api/plans`, `/club/api/courts` | public | data for apps |
| `POST /club/api/booking/create` | user | JSON booking |
| `GET /club/api/pos/catalog` | user | POS products |

`club_website/controllers/`: `main.py` (home, membership, courts, shop, join, contact), `online.py` (`/book`, `/booking/<token>`, cart, checkout, `/club-shop/order/<token>`), `member.py` (`/my/club`, signed-in members only, shows only their own data), `support.py` (feedback, tickets).

Public endpoints are safe because: inputs are cleaned and length-limited, private random tokens guard each booking or order link, honeypot fields stop bots, and products are served by controller (`/club-shop/image/<id>`) since visitors cannot read them.

---

## 6. Security and roles

`security/security.xml`:
- **Club Staff**: implies internal user + invoicing + all-leads CRM.
- **Club Manager**: implies Staff + Sales Manager + POS Manager; admin is a member.

`security/ir.model.access.csv`: every model has rows. Staff can read plans and courts, create and edit bookings (no delete); managers have full CRUD. Orders are create-only for staff.
Other layers: menu `groups=`, the `_require_manager` check in the dashboard, and portal users limited to their own data. There are no per-row record rules (single company).

---

## 7. Data files

| File | Content |
|---|---|
| `data/plans.xml` | Gold, Silver, Junior with rates and discounts |
| `data/categories.xml` | "Club Shop", "Bar & Cafeteria" product categories |
| `data/pricelist.xml` | standard pricelist |
| `data/product.xml` | court booking product, "Walk-in Customer" partner |
| `data/crm_pipeline.xml`, `crm_data.xml` | stages New, Contacted, Interested, Quote Sent, Negotiation, Won |
| `data/mail_template.xml` | welcome, expiry reminder, confirmations, payment received |
| `data/cron.xml` | two daily jobs: lapse memberships, send reminders |
| `data/sequence.xml` | member id, booking and order numbers |

Note: `demo_club_data.xml` is in `data`, so it loads in production too.

---

## 8. Reports

`views/report_views.xml`: pivot and graph on `club.booking` (revenue by court, month, tier; peak hours), "Invoices by Source" list, and the Owner Dashboard (OWL client action `club_management.owner_dashboard` that calls `club.dashboard.get_dashboard_data` through `orm.call`).

---

## 9. Tests

`tests/` (all `TransactionCase`, tagged `club_management`): booking rules, availability, pricing, pricelists, CRM flow, enquiry, cron, currency, member, member login, public booking and order, reports, dashboard, owner reports, support, frontend API contract.
Run: `docker compose run --rm odoo odoo -d club_test -i club_management,club_website --test-tags club_management --stop-after-init`
Last full run: 432 tests, 0 failures (before the latest teammate additions; rerun).

---

## 10. Likely viva questions

**Why extend `res.partner` instead of a new member model?** POS, shop, sales and accounting all use partners, so one record powers every channel with no sync code.

**How does the tier give a discount in POS and the shop?** Each plan owns a pricelist; active members get it as `property_product_pricelist`; POS config gets the tier pricelists; server code prices with `plan.pricelist_id._get_product_price`.

**How do you stop double booking?** Python constraint `_check_availability` plus a `SELECT ... FOR UPDATE` lock on the court row to serialise concurrent transactions. We did not add a PostgreSQL EXCLUDE constraint (it needs `btree_gist`); that would be the next hardening step.

**How is Friday social play different?** `is_social` is computed from the club-local weekday; instead of exclusivity the constraint sums `players` against `social_capacity` for each half-hour moment.

**Why are prices computed on the server?** A client could send any number. The screens only display; `club.order.service` recomputes from the tier pricelist.

**What happens when a membership expires?** `member_state` becomes expired, `_get_active_plan` returns empty, so price falls to full rate; a daily cron lapses members and the tier pricelist is removed from the partner.

**What if accounting fails during a sale?** Invoice creation is in a savepoint, logged, and the sale still completes; the order has no invoice and needs manual follow-up.

**When does the membership start: acceptance or payment?** On quote acceptance; the invoice is posted and shows as outstanding until paid. This is a design choice that can be switched.

**How do you handle time zones?** Store UTC, convert to Asia/Kolkata for rules, store `booking_date` in club time.

**How is the dashboard protected?** Manager-only menu plus an `AccessError` check inside the method (RPC-safe), then `sudo()` for cross-model aggregation.

**Known gaps (be honest):** no record rules; no SQL overlap constraint; "Choose plan" on the plans screen only notifies; some screen nav items are static; court bookings are invoiced manually.

---

## 11. Commands cheat sheet

```bash
bash scripts/create_demo_db.sh club              # rebuild DB with demo data (INR)
docker compose up -d                              # http://localhost:8069  (admin/admin)
docker compose run --rm odoo odoo -d club -u club_management,club_website --stop-after-init
```
