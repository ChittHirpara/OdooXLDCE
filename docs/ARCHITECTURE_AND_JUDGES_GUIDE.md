# The Champions Club: Architecture, Data Flow and Judges' Guide

One Odoo 17 platform for a sports club: **court bookings, memberships, a pro-shop, a bar/cafeteria, a CRM and a public website, all driven by a single member record.**

> Read **section 1** (the pitch) and **section 13** (the 10 questions) last-minute. Sections 2 to 12 are the reference.

---

## Contents
1. [The 30-second pitch and the 5-minute demo](#1-the-30-second-pitch-and-the-5-minute-demo)
2. [What we built, in numbers](#2-what-we-built-in-numbers)
3. [Architecture at a glance](#3-architecture-at-a-glance)
4. [The two modules and what is inside them](#4-the-two-modules-and-what-is-inside-them)
5. [The database: every table we created or extended](#5-the-database-every-table-we-created-or-extended)
6. [Pricing: one rule for everything](#6-pricing-one-rule-for-everything)
7. [Business rules and where each one is enforced](#7-business-rules-and-where-each-one-is-enforced)
8. [Workflows and exactly what happens in the database](#8-workflows-and-exactly-what-happens-in-the-database)
9. [How data travels: the request lifecycle](#9-how-data-travels-the-request-lifecycle)
10. [Security model](#10-security-model)
11. [Reports and automation](#11-reports-and-automation)
12. [Proof it works: tests, and how to run and demo it](#12-proof-it-works-tests-and-how-to-run-and-demo-it)
13. [The 10 fundamental questions judges can ask](#13-the-10-fundamental-questions-judges-can-ask)
14. [Honest limitations](#14-honest-limitations)

---

## 1. The 30-second pitch and the 5-minute demo

**Problem.** A club runs on spreadsheets, WhatsApp groups and paper: courts are double-booked, members' discounts are applied by memory, and enquiries get lost.

**Solution.** One platform on Odoo where **one member record** decides what you pay for a court, in the shop and at the bar, and where every website enquiry becomes a tracked CRM lead that turns into a member.

**What makes it different.**
- **One source of truth for price.** Discounts live in Odoo pricelists, generated from the membership plan. The shop, the bar, the real Odoo POS and the website all read the same rule.
- **Nothing is calculated in the browser.** The screens ask the server for every price, stock figure and availability.
- **We reused Odoo instead of rebuilding it:** CRM, Sales quotations, Inventory, Accounting, Website, POS pricelists, activities, e-mail.

### The 5-minute demo script (the full story, in order)

| # | Do this | You will see | What it proves |
|---|---|---|---|
| 1 | Open `http://localhost:8069/` | The club website | Public site, branded, in rupees |
| 2 | **Membership** | Gold ₹5,000 / Silver ₹3,000 / Junior ₹1,500, benefits, comparison | Plans come from the database, not hard-coded |
| 3 | **Courts**: pick tomorrow | A grid with the busy evening struck through; pick a Friday and see "N left" | Live availability, Friday social play |
| 4 | Click a free slot, then **Send enquiry** | "Thank you" and a reference `ENQ-000xx` | Website to CRM |
| 5 | Log in at `/web` (admin / admin), **Club, Enquiries (CRM)** | The new lead in **New**, with a follow-up call task | CRM pipeline, automatic assignment |
| 6 | Click **Contacted**, then **Interested**; refresh the visitor's status link | The visitor's status page follows each stage | Visitor-facing transparency |
| 7 | **Create Membership Quote**, then **Confirm** | Quotation from the plan's product, then lead turns **Won** | CRM to Sales to member |
| 8 | Open the lead's **Member** button | A Gold member with ID `CC-000xx`, QR code, welcome e-mail queued | Lead to member automatically |
| 9 | **Bar & POS**: choose that member, add Cold Coffee, pay | ₹180 becomes ₹153 (15% Gold) | Tier pricing at the bar |
| 10 | **Reporting**: Booking Revenue, Peak Hours, Enquiry Funnel | Pivot and graph reports | Owner dashboard |

---

## 2. What we built, in numbers

| | |
|---|---|
| Platform | Odoo 17, PostgreSQL 15, Docker |
| Our modules | `club_management` (platform) and `club_website` (public site) |
| Our database tables | 7 new, plus new columns on 3 standard Odoo tables (contact, CRM lead, product) |
| Membership tiers | 3 (Gold, Silver, Junior) |
| Courts | 9 (tennis, padel, badminton, cricket) |
| Custom screens | 4 interactive OWL screens (booking grid, plans, shop, bar POS) |
| Public website pages | 9 (home, membership, courts, shop, product, join, about, contact, enquiry status) |
| CRM pipeline stages | 6 (New, Contacted, Interested, Quote Sent, Negotiation, Won) plus Lost |
| Automated tests | **297 Python tests**, all passing |
| Real-browser checks | **144 checks** across 8 scripts, all passing |
| Code | about 2,600 lines of Python (without tests), about 2,800 lines of tests |

---

## 3. Architecture at a glance

```
                              ┌─────────────────────────────────────────────┐
                              │                  BROWSER                    │
                              └───────┬───────────────┬──────────────┬──────┘
                                      │               │              │
                      PUBLIC WEBSITE  │   4 OWL SCREENS │   ODOO BACKEND │
                      (club_website)  │   (JS components)│   (standard views)│
                                      │               │              │
        pages: / /membership /courts  │  orm.call(...) │  forms, lists, │
        /club-shop /join /status      │  JSON-RPC      │  kanban, pivot │
                                      ▼               ▼              ▼
   ┌──────────────────────────────────────────────────────────────────────────┐
   │                         CONTROLLERS  /  RPC ENDPOINTS                    │
   │   website pages · /club/availability · /club/enquiry · /club/api/*       │
   │   frontend_api.py (adapters called by the OWL screens)                   │
   └──────────────────────────────────┬───────────────────────────────────────┘
                                      ▼
   ┌──────────────────────────────────────────────────────────────────────────┐
   │                       BUSINESS LOGIC  (Python models)                    │
   │  membership.plan · res.partner(member) · court · booking · order         │
   │  crm.lead · sale.order · pricing service · demo/cron                     │
   │  ── all rules live HERE, never in the browser ──                         │
   └──────────────────────────────────┬───────────────────────────────────────┘
                                      ▼
   ┌──────────────────────────────────────────────────────────────────────────┐
   │              ODOO STANDARD APPS WE BUILD ON (reused, not rebuilt)        │
   │   CRM · Sales · Inventory · Accounting · Point of Sale · Website · Mail  │
   │   Pricelists · Activities · Cron · Access rights                         │
   └──────────────────────────────────┬───────────────────────────────────────┘
                                      ▼
                          ┌──────────────────────────┐
                          │   PostgreSQL  (one DB)   │
                          └──────────────────────────┘
```

**The idea in one sentence:** the browser only *asks*; the Python models *decide*; PostgreSQL *remembers*; and Odoo's standard apps do the generic work (quotes, stock, invoices, CRM).

### How the pieces connect (the business map)

```
   WEBSITE ──enquiry──▶ CRM LEAD ──quote──▶ SALE ORDER ──accepted──▶ WON
                                                                      │
                                                                      ▼
                                                 MEMBER  (res.partner + plan + tier pricelist)
                                                                      │
                          ┌──────────────────────┬────────────────────┼────────────────────┐
                          ▼                      ▼                    ▼                    ▼
                    COURT BOOKING            SHOP ORDER           BAR / POS ORDER     INVOICE
                   (club.booking)           (club.order)          (club.order)     (account.move)
                          │                      │                    │
                          └──────────── price from the SAME tier pricelist ─────────────┘
                                               stock from stock.quant
```

---

## 4. The two modules and what is inside them

### `addons/club_management`: the platform

| Area | Files | What it does |
|---|---|---|
| Membership | `models/membership_plan.py`, `models/res_partner.py` | Plans (Gold/Silver/Junior), the member fields on the contact, ID, expiry, QR code |
| Courts and bookings | `models/court.py`, `models/booking.py`, `wizard/booking_reschedule.py` | Courts, 1-hour bookings, every booking rule, pricing, invoice, reschedule |
| Shop and bar | `models/club_pos_and_shop.py`, `models/club_order.py`, `models/pos_config.py` | Server-side pricing, orders, stock deduction, tables, shift totals, POS pricelists |
| Screens' server side | `models/frontend_api.py` | The exact model/method names the OWL screens call |
| CRM | `models/crm_lead.py`, `models/sale_order.py` | Enquiry intake, pipeline, quote, lead to member |
| Currency | `models/res_company.py` | Switches the club to rupees once, at install |
| Public API | `controllers/main.py` | Availability, enquiry, status, plans, courts, catalogs |
| Screens | `static/src/components/*` | 4 OWL screens: booking grid, membership plans, shop, bar POS |
| Views | `views/*.xml` | Forms, lists, kanban, pivot, graph, menus |
| Data | `data/*.xml`, `demo/*.xml`, `models/demo_data.py` | Plans, pricelists, stages, e-mail templates, crons, demo data |
| Setup | `scripts/create_demo_db.sh` | Builds a ready database in rupees with demo data |

### `addons/club_website`: the public site (depends on the platform)

It adds **no tables**. It reads plans, courts, products and availability from `club_management` (through the helper model `club.website.data`) and writes exactly one thing: an enquiry, which becomes a CRM lead.

| Page | URL | Data it shows |
|---|---|---|
| Home | `/` | plans, open courts today, 4 products |
| Membership | `/membership` | plans with price, benefits, comparison |
| Courts | `/courts` | live availability grid (JavaScript reads `/club/availability`) |
| Shop | `/club-shop`, `/club-shop/<id>` | products, live stock, member prices per tier |
| Join / Contact | `/join`, `/contact` | the enquiry form |
| Status | `/club/enquiry/status/<token>` | the visitor's private progress timeline |

---

## 5. The database: every table we created or extended

### 5.1 Entity relationship (simplified)

```
 club_membership_plan ◀─────────────────────────┐
   │ pricelist_id ▶ product_pricelist           │ plan_id
   │ product_id   ▶ product_product       res_partner  (the MEMBER)
   │                                        │  ▲  member_id, expiry_date, member_state…
   │                                        │  │
   │  interested_plan_id                    │  │ partner_id
   ▼                                        ▼  │
 crm_lead ───── partner_id ──────────▶ res_partner        club_court
   │  (enquiry fields)                      ▲  ▲                ▲
   │ opportunity_id                         │  │ partner_id     │ court_id
   ▼                                        │  └──────── club_booking ──▶ account_move (invoice)
 sale_order ─▶ sale_order_line ─▶ product   │
                                            │ partner_id
                              club_order ───┘── plan_id ▶ club_membership_plan
                                  │   table_id ▶ club_pos_table
                                  ▼
                           club_order_line ─▶ product_product
```

### 5.2 Tables we created

**`club_membership_plan`**: the three tiers. One row per tier; everything else derives from it.

| Column | Meaning |
|---|---|
| `name`, `code` | "Gold", `gold` (unique: only one plan per tier) |
| `court_rate` | price of a court per hour for this tier (Gold 0, Silver 500, Junior 250) |
| `shop_discount`, `bar_discount` | percent off in the shop / bar (Gold 20 / 15, Silver 10 / 10, Junior 5 / 0) |
| `validity_days` | how long a membership lasts (365) |
| `price` | annual fee (5,000 / 3,000 / 1,500) |
| `pricelist_id` | **auto-generated** Odoo pricelist that encodes the two discounts |
| `product_id` | **auto-generated** service product sold on a membership quotation |

*SQL checks:* discounts between 0 and 100, rate not negative, validity at least 1 day.

**`club_court`**: a bookable court or net.

| Column | Meaning |
|---|---|
| `name`, `sport` | "Tennis Court 1", one of tennis / padel / badminton / cricket |
| `list_price` | full price per hour (walk-ins and non-members pay this) |
| `social_capacity` | players who may share the court in one Friday slot |
| `open_hour`, `close_hour` | opening hours, default 6.0 to 22.0 |
| `surface`, `is_indoor`, `active` | descriptive |

**`club_booking`**: one court for one hour.

| Column | Meaning |
|---|---|
| `name` | reference `BK/00154` (from a sequence) |
| `court_id`, `partner_id` | which court; which member (empty for a walk-in) |
| `walkin_name` | the name when there is no member |
| `start_datetime`, `end_datetime` | UTC; **end is always start + 1 hour** (computed and stored) |
| `booking_date`, `is_social`, `start_hour` | computed in **club time (Asia/Kolkata)**: the day, "is it Friday", the hour |
| `players` | how many people (1 normally, up to capacity on Fridays) |
| `state` | draft, confirmed, cancelled, done |
| `price`, `tier` | computed: what was charged and which tier applied (gold, silver, junior, guest) |
| `sport` | copied from the court so reports can group by it |
| `invoice_id` | link to the customer invoice, once created |

*Stored on purpose:* `tier`, `sport`, `start_hour`, `booking_date` exist so the pivot and graph reports can group by them quickly.
*SQL check:* `players > 0`. The overlap and daily-limit rules are Python constraints (section 7).

**`club_order`** and **`club_order_line`**: one completed bar tab or pro-shop order.

| `club_order` column | Meaning |
|---|---|
| `name` | `ORD/00001` |
| `channel` | `bar` or `shop` |
| `partner_id`, `customer_name`, `plan_id` | who, and which tier discount was applied |
| `table_id`, `payment_method` | bar only: which table, cash / card / upi |
| `fulfillment`, `delivery_address` | shop only: collect at club or delivery |
| `subtotal`, `discount`, `total` | computed from the lines |

| `club_order_line` column | Meaning |
|---|---|
| `order_id`, `product_id`, `qty` | what was bought |
| `list_price` | the unit price before any discount |
| `unit_price` | the unit price actually charged (the tier price) |
| `line_total` | `unit_price × qty` |

**`club_pos_table`**: bar floor tables (name, capacity, status available/occupied).

**`club_booking_reschedule`**: a short-lived wizard table for the "Reschedule" pop-up (Odoo cleans it automatically).

### 5.3 Standard Odoo tables we extended with our own columns

| Table | Columns we added | Why |
|---|---|---|
| `res_partner` (the contact **is** the member) | `is_member`, `plan_id`, `member_id` (`CC-00001`), `date_of_birth`, `join_date`, `expiry_date`, `member_state` (none/active/expired), `expiry_reminder_for` | One record for the person everywhere; Junior = under 18 by birth date |
| `crm_lead` (the enquiry) | `enquiry_ref` (`ENQ-00001`), `enquiry_token`, `interested_plan_id`, `enquiry_type`, `enquiry_source`, `sport_interest`, `member_date_of_birth`, `member_activated` | Track the enquiry and know when it has become a member |
| `product_product` | `club_category` (rackets, balls, coffee, food…), `image_icon` | Filters and icons on the shop and bar screens |

### 5.4 Standard Odoo tables we **use** (we did not rebuild them)

| Odoo table | What we use it for |
|---|---|
| `crm_lead`, `crm_stage`, `crm_lost_reason` | The enquiry pipeline, its 6 stages, lost reasons |
| `mail_activity`, `mail_message`, `mail_mail` | Follow-up call tasks, chatter notes, queued e-mails |
| `sale_order`, `sale_order_line` | The membership quotation |
| `product_pricelist`, `product_pricelist_item` | The tier discounts (one pricelist per plan) |
| `stock_quant`, `stock_warehouse_orderpoint` | Live stock, and the low-stock reorder rules |
| `account_move`, `account_move_line` | Customer invoices for court bookings |
| `pos_config` | The real Odoo POS also offers the tier pricelists |
| `ir_cron`, `ir_sequence`, `ir_config_parameter` | Scheduled jobs, numbering (`BK/`, `ORD/`, `ENQ-`, `CC-`), settings |
| `website`, `website_menu`, `website_page` | The public site and its navigation |

---

## 6. Pricing: one rule for everything

**The rule:** a member whose membership is active on the day gets their **tier**; everyone else (walk-ins, non-members, lapsed members) pays **full price**.

| | Court / hour | Shop discount | Bar discount | Annual fee |
|---|---|---|---|---|
| **Gold** | ₹0 (included) | 20% | 15% | ₹5,000 |
| **Silver** | ₹500 | 10% | 10% | ₹3,000 |
| **Junior** (under 18) | ₹250 | 5% | 0% | ₹1,500 |
| Walk-in / lapsed | court's list price (e.g. ₹800) | 0% | 0% | n/a |

**How shop and bar discounts are applied.** Each plan generates an Odoo **pricelist** ("Club Gold" …) with two rules: *shop % on the Club Shop product category* and *bar % on the Bar & Cafeteria category*. An active member's contact is given that pricelist. Then:
- the **bar and shop screens** ask the server `calculate_order_pricing`, which reads that pricelist;
- the **real Odoo POS** reads the same pricelist when you pick the customer;
- the **website** shows the same member prices.

**Worked examples**
- Gold member buys a ₹4,200 bat → shop 20% → **₹3,360** (discount ₹840).
- Gold member orders Cold Coffee ₹180 → bar 15% → **₹153**.
- Gold member books a court → **₹0**. Silver → ₹500. Walk-in → ₹800.
- Karan's membership lapsed 10 days ago → he pays full price everywhere.

**Why this is solid:** change a discount on the plan and every screen follows; there is exactly one place to change it. A test (`test_price_matches_the_real_pos_pricelist`) proves the screen price equals the real POS price.

---

## 7. Business rules and where each one is enforced

| Rule | Where it is enforced | How |
|---|---|---|
| Sessions are **1 hour** | `club_booking.end_datetime` | Computed (`start + 1h`); not editable |
| Start every **30 minutes** | Python constraint | Minute must be 0 or 30, else a clear error |
| Inside **opening hours** | Python constraint | Start ≥ open, start + 1h ≤ close (per court) |
| **No overlap** on a court | Python constraint + row lock | Another non-cancelled booking overlapping the hour is refused. `SELECT … FOR UPDATE` on the court row serialises simultaneous bookings, so two people cannot both win |
| **Max 2 bookings per member per day** | Python constraint | Counts non-cancelled bookings on the **club-time date** |
| **Friday social play** | Python constraint | On Friday many players share a court: the sum of `players` in any half-hour of the slot may not exceed `social_capacity` |
| Walk-ins allowed, pay full price | Pricing | No member → the court's list price |
| Junior must be **under 18** | Python constraint on the contact | Needs a birth date; age < 18 |
| Club timezone | Everywhere | "Day" and "Friday" are computed in **Asia/Kolkata**, not the server's timezone |
| Cancel frees the slot | State machine | Cancelled bookings are ignored by every rule; resetting re-checks them |
| Reschedule re-validates | `action_reschedule` | Runs all rules again; an **invoiced** booking may only move if the price is unchanged |
| Stock cannot go negative | Order service | A stock-tracked product refuses an order bigger than the stock, and nothing is saved |
| Prices are server-side | `club.order.service` | Whatever the browser sends is ignored and recomputed |

---

## 8. Workflows and exactly what happens in the database

### 8.1 Website enquiry becomes a CRM lead

```
Visitor fills /join ──POST /join/submit──▶ create_club_enquiry()
```
1. Validate name, email or phone, plan, sport, type. A hidden **honeypot** field catches bots (they get a normal-looking page, nothing is saved).
2. **Duplicate check:** the same e-mail within 24 hours **adds a note to the same lead** instead of creating another.
3. **Database writes:**
   - `crm_lead`: new row, `type = opportunity`, stage **New**, `enquiry_source = website`, `interested_plan_id`, `expected_revenue = plan fee`, `enquiry_ref = ENQ-000xx`, a random 32-character `enquiry_token`, assigned to the first club manager.
   - `mail_activity`: a **call task**, due the next day, for the assignee.
   - `mail_mail` / `mail_message`: an acknowledgement e-mail with the reference and a private status link.
4. The visitor sees the reference and a link to `/club/enquiry/status/<token>`.

### 8.2 From lead to member (the CRM workflow)

```
New ─▶ Contacted ─▶ Interested ─▶ [Create Membership Quote] ─▶ Quote Sent ─▶ Negotiation
                                                  │
                         customer accepts = CONFIRM the quote
                                                  ▼
                                               WON
                                                  │
                  customer linked/created ─▶ plan set ─▶ membership activated ─▶ welcome e-mail
```
- **Create Membership Quote** (`action_create_membership_quote`): finds or creates the customer contact; creates `sale_order` + one `sale_order_line` for the plan's product at the annual fee; moves the lead to **Quote Sent**. Pressing it twice reuses the open quote.
- **Won** can happen three ways, all doing the same thing: confirming the quote, dragging the lead to Won, or the **Won** button.
- **On Won** (`_club_activate_member`):
  - `res_partner`: `plan_id` set, `is_member = true`, `join_date = today`, `expiry_date = today + 365`, `member_id` from the `CC-` sequence, `member_state = active`;
  - the contact is given the plan's **pricelist** (so shop, bar and POS discounts start working immediately);
  - `crm_lead.member_activated = true`; a chatter note records the member ID; a welcome e-mail is queued.
- A **Junior** lead needs a birth date first; otherwise staff get a note and a to-do instead of an error.
- An existing active member of the same plan is **not reset** (their expiry is never shortened).

### 8.3 Booking a court

```
Screen/API ─▶ create_booking_api(court, date, time, member) ─▶ rules ─▶ INSERT club_booking
```
1. The screen first asks `get_availability(date)`: the server returns the booked start times per court. Booked slots are shown struck through.
2. On **Confirm**, the server creates the booking. The constraints in section 7 run inside the same transaction. A broken rule returns a **message** (for example "Court is already booked at …") and **nothing is saved** (a savepoint rolls it back).
3. Stored automatically: `price` and `tier` (from the member's plan and the booking date), `booking_date`, `is_social`, `start_hour`, a `BK/…` reference.
4. **Create Invoice** (optional): a draft `account_move` with one line of the "Court Booking" product at the booking price; walk-ins are invoiced to a shared "Walk-in Customer" contact. A booking with a posted invoice cannot be cancelled until credited.

### 8.4 Shop order and bar tab

```
Screen ─▶ place_order / process_payment_api ─▶ re-price on server ─▶ check stock
        ─▶ INSERT club_order + club_order_line ─▶ UPDATE stock_quant ─▶ (bar) free the table
```
- Prices come from the member's pricelist: `list_price` and `unit_price` are both stored, so the discount is auditable.
- Tracked stock is deducted from `stock_quant`; an order larger than the stock is refused as a whole.
- A bar payment also frees the table. The **shift** panel and the **order history** are built from the day's real `club_order` rows.
- Visible in Odoo: **Club, Bar & Shop Orders**.

### 8.5 Membership lifecycle (automatic)

Two daily scheduled jobs:
1. **Lapse job** `_cron_lapse_memberships`: members whose `expiry_date` has passed become **expired**, lose their tier pricelist (so they pay full price), and get a chatter note.
2. **Reminder job** `_cron_send_expiry_reminders`: active members expiring within **14 days** get one e-mail (once per expiry date; renewing re-arms it).
Both use the **club date** (Asia/Kolkata).

---

## 9. How data travels: the request lifecycle

**Example: a member pays at the bar (an OWL screen).**

```
1. Staff taps  Pay Now            bar_pos.js (browser)
2. orm.call("club.pos.order", "process_payment_api", [ {table, member_id, items, payment_method} ])
        │   (JSON-RPC over HTTPS to /web/dataset/call_kw, with the staff session)
        ▼
3. frontend_api.py  → ClubPosOrder.process_payment_api()           (thin adapter)
        ▼
4. club_pos_and_shop.py → ClubOrderService.process_pos_payment()   (the real logic)
        │   a. find the member's active plan
        │   b. price every line from the plan's pricelist (browser's prices ignored)
        │   c. check stock; deduct from stock_quant
        │   d. INSERT club_order + club_order_line; UPDATE club_pos_table (freed)
        ▼
5. PostgreSQL commits the transaction (all or nothing)
        ▼
6. JSON result  {success, order_ref:"ORD/00002", amount:"₹153.00", …}
        ▼
7. bar_pos.js shows "Payment Successful", then reloads stock, shift and history from the server
```

**The same pattern, for every feature:** *screen → orm.call → adapter → service/model → SQL → JSON back → screen state.*

### The server calls our screens make (the contract)

| Screen | Model | Methods |
|---|---|---|
| Court booking | `club.court` | `get_courts_list` |
| | `club.booking` | `get_availability`, `calculate_booking_price`, `create_booking_api`, `get_partner_bookings`, `action_cancel` |
| Membership plans | `club.membership.plan` | `get_frontend_plans` |
| All screens | `res.partner` | `get_current_member`, `get_members_list` |
| Pro-shop | `club.shop.product` / `club.shop.order` | `get_shop_catalog` / `place_order`, `calculate_order_pricing` |
| Bar POS | `club.pos.table`, `club.pos.product`, `club.pos.order`, `club.pos.session` | tables, products, `calculate_order_pricing`, `process_payment_api`, `get_recent_orders`, `get_current_shift` |

A test scans the JavaScript and **fails if a screen calls a server method that does not exist**, because the screens would otherwise silently fall back to fake data.

### Public HTTP endpoints

| URL | Who | Purpose |
|---|---|---|
| `GET /club/availability?date=&sport=` | public | slot availability JSON (no customer data) |
| `POST /club/enquiry`, `POST /join/submit` | public (CSRF-protected) | create an enquiry |
| `GET /club/api/enquiry/status?token=` | public, secret token | visitor's progress |
| `GET /club/api/plans`, `/courts`, `/shop/catalog` | public | read-only catalogs |
| `POST /club/api/booking/create` | **logged-in users only** | create a booking (non-staff can only book for themselves) |
| `GET /club/api/pos/catalog` | **staff only** | bar products and tables |

---

## 10. Security model

| Who | Can | Cannot |
|---|---|---|
| **Public visitor** | view plans, courts, availability, products, submit an enquiry, read **their own** enquiry status (secret token) | read any lead, member, booking, order or revenue; create bookings; change stock |
| **Club Staff** | work **all** CRM leads, create quotations, create bookings and orders, invoice, use the screens | change configuration, delete bookings |
| **Club Manager** | everything staff can, plus plans, courts, reports, Sales manager rights | n/a |

How it is enforced:
- **Odoo access rules** (`ir.model.access.csv`) on every one of our models, for the two groups.
- Public pages read data through a helper that returns **only the fields shown** (no costs, no customers).
- The booking endpoint requires login; the POS endpoint requires staff; both were closed after we found them open.
- Enquiry forms have a **CSRF token** and a **honeypot**; the status link uses a **random 32-character token**, so enquiries cannot be guessed or enumerated.
- Tests verify the public **cannot** read leads, members, bookings or orders through the web client API.

---

## 11. Reports and automation

| Report | Where | Built from |
|---|---|---|
| **Booking Revenue** (pivot and graph) | Club, Reporting | `club_booking.price` by court, month, tier, sport |
| **Peak Hours** | Club, Reporting | `club_booking.start_hour` by court |
| **Enquiry Funnel** | Club, Reporting | `crm_lead` by stage and plan |
| **Bar & Shop Orders** | Club | `club_order` list with discount and total |
| **Low stock** | Inventory, Replenishment | `stock_warehouse_orderpoint` (5 demo products are below their minimum) |

Automation: 2 daily cron jobs (lapse, reminders), automatic e-mails (enquiry received, welcome, expiry reminder), automatic follow-up task for every new enquiry.

---

## 12. Proof it works: tests, and how to run and demo it

### Tests

| | Count | What it proves |
|---|---|---|
| Python tests | **297 passing** | every booking rule, pricing for every tier, invoice creation, pricelists, CRM from enquiry to member, cron jobs, security, the website pages, currency, demo data |
| Real-browser checks | **144 passing** | headless Chrome drives the real screens against a live database and then checks the **database** |

The browser scripts (`addons/club_management/tests/e2e/`) include `flow_journey.js`, which plays the **entire story**: visitor enquiry, staff CRM clicks, quote, accept, member created, court booked, shop order, bar payment on the real POS screen, and checks every record.

### Run it

```bash
docker compose build db && docker compose up -d
bash scripts/create_demo_db.sh club        # builds the database in rupees with demo data (~2 min)
docker compose up -d                       # then open http://localhost:8069   (admin / admin)
```

Run the tests:
```bash
docker compose run --rm odoo odoo -d club_test -u club_management,club_website --test-tags club_management --stop-after-init
```

### Demo data you will find
9 courts, 13 members (Gold, Silver, Junior; one **expiring in 5 days**, one **already expired**), 2 weeks of booking history, a **fully booked "busy evening" tomorrow**, **Friday social play** with places left, 11 products (5 **low on stock**, one out of stock), and a CRM pipeline with a lead in every stage plus one already converted to a member.

---

## 13. The 10 fundamental questions judges can ask

**1. What problem does this solve, and why Odoo?**
A club juggles courts, members, a shop, a bar and enquiries in separate tools, so rules and discounts are applied by hand and data is duplicated. Odoo already provides the hard generic parts (CRM, Sales, Inventory, Accounting, POS, Website, e-mail, access rights) on **one database**. We built only what is club-specific (membership tiers, courts and booking rules, the screens, the enquiry-to-member link) and **reused everything else**, so the platform is small, consistent and maintainable.

**2. How do you stop two people booking the same court at the same time?**
Three layers. The booking rules run as **Python constraints** inside the database transaction. The check **locks the court's row** (`SELECT … FOR UPDATE`), so two simultaneous bookings are processed one after the other and the second sees the first. And the screen shows live availability from the server. We chose the lock plus constraint over a database exclusion rule because it keeps the Friday social-play exception (many players on one court) in one readable place. A test proves overlaps, adjacent slots, cancelled slots and rescheduling.

**3. How does one member record drive booking, shop and bar?**
The member is the standard Odoo **contact** (`res_partner`) with a few extra fields (plan, ID, expiry). Their **plan** produces the court rate and an Odoo **pricelist**; the contact is given that pricelist. Court pricing reads the plan; shop, bar and the real POS read the pricelist. Same person, same record, no duplicated member data and no second membership system.

**4. Where are prices calculated, and why not in the browser?**
Always on the server. The browser sends *what* was bought; the server recomputes the price from the member's pricelist, checks stock and saves the result. Anything the browser claims about price is ignored. This prevents tampering, keeps discounts consistent across shop, bar, website and POS, and means changing a discount in one place updates everything. We found and fixed screens that were calculating locally and falling back to fake numbers.

**5. Walk me through a website enquiry becoming a paying member.**
A visitor submits `/join`. A **lead** appears in the CRM (stage New) with a follow-up call task and an acknowledgement e-mail. Staff move it Contacted, Interested, then press **Create Membership Quote**, which creates a real Sales quotation for the plan's fee. When the customer **accepts (the quote is confirmed)** the lead becomes **Won**, which automatically creates or links the customer, sets the plan, activates the membership (ID, dates, tier pricelist) and e-mails a welcome. From that moment they get member prices on courts, shop and bar. The whole chain is tested and demonstrated.

**6. How did you model Friday social play?**
On a Friday a court is not exclusive: several players or groups share it up to the court's **social capacity** (for example 8). The booking records `players`; the rule sums the players overlapping each half-hour of the slot and refuses to exceed capacity. The availability grid shows **"N left"** instead of a simple booked/free flag. "Friday" is decided in **club time (Asia/Kolkata)**, not the server's timezone.

**7. What happens when a membership expires?**
A daily job marks overdue members **expired** and removes their tier pricelist, so they immediately pay full price for courts, shop and bar. Another daily job e-mails members **14 days before** expiry (once per expiry date). Renewal re-activates the plan and re-arms the reminder. Pricing also checks the expiry date directly, so a member is never discounted for a day after their membership ended.

**8. How is it secured? What can the public see?**
The public can view plans, availability, products and submit an enquiry; nothing else. Leads, members, bookings, orders and revenue are protected by Odoo access rules (staff and manager groups) and **tests prove the public cannot read them**. Enquiry forms use CSRF tokens and a honeypot against bots; the visitor's status link uses a random secret so enquiries cannot be guessed; the website only exposes the fields it displays (no costs, no customers).

**9. How do you know it actually works?**
Two independent layers. **297 automated Python tests** cover every rule (overlap, 30-minute slots, two per day, Friday capacity, every tier's price, invoices, the CRM flow, security, crons). Then **144 real-browser checks** run the actual screens in headless Chrome and verify the **database** after each action, including a full "visitor to member to order" story. This caught real bugs that unit tests cannot (screens calling server methods that did not exist, a report crashing in the browser, menus missing from the public site).

**10. What are the limits, and what would you build next?**
The pro-shop on the website is browse-and-reserve (pay at the club); there is **no online card payment**. Members use the screens through staff sessions; a member **self-service login** is the natural next step. The membership contract idea (monthly billing, pause) was left out of scope. Next we would add online payments, member login and self-booking, SMS reminders, and per-sport coaching products. The architecture supports these because everything already runs through the same member record, pricelists and orders.

---

## 14. Honest limitations

Judges respect candour. These are true today:

- **No online payment** on the website. Shop is "reserve for pickup"; membership is quote, then accept.
- **The OWL screens run under staff sessions.** There is no member self-service login yet.
- **"Choose plan" on the plans screen** only shows a notification; joining goes through the enquiry form.
- **Rupees** apply only to databases built with `scripts/create_demo_db.sh` (Odoo's own accounting demo data blocks a currency change, so a plain install with Odoo demo data stays in dollars).
- **Accounting is basic:** court bookings can create draft invoices; shop and bar orders are recorded as club orders and stock moves, not as posted accounting entries. A real deployment would map these to a chart of accounts and taxes.
- The `preview/` folder is an **offline mock-up** of the screens (no Odoo needed), kept for design reference; the real screens live in `addons/club_management/static/src/components`.

---

*Where to look in the code:* `addons/club_management/models/` (all logic), `addons/club_management/tests/` (proof), `addons/club_website/` (public site), `scripts/create_demo_db.sh` (setup), `CLAUDE.md` (developer notes), `addons/club_management/tests/e2e/README.md` (browser checks).

---

## Addendum: instant booking and ordering (no enquiry needed)

Visitors no longer have to send an enquiry to book a court or buy from the shop.

- **Book a court**: `/courts` free slot → `/book` → `POST /book/submit` → `club.booking.create_public_booking()`. Same overlap, 30-minute slot, 2-per-day and Friday social-capacity rules as staff. Confirmed instantly, source `website`, private link `/booking/<token>` (view and cancel). Guests pay the court's list price; members enter member ID + e-mail (verified together) for their tier rate. Guest 2/day limit is by phone or e-mail. Window: today to 14 days ahead.
- **Order from the shop**: product page → cart (session) → `/club-shop/checkout` → `club.order.service.place_public_order()` → `club.order` (source `website`), stock deducted, member discount applied server-side, confirmation page `/club-shop/order/<token>`. Collect at club or home delivery (address required). Payment is at the club or on delivery.
- **Safety**: CSRF, honeypot, secret tokens, savepoints (a refused request leaves nothing), prices never read from the browser, one vague member-verification error.
- **Staff view**: Club > Bookings and Bar & Shop Orders show a Source column and "Booked/Ordered Online" filters. Guest bookings also file a follow-up lead so the club can offer a membership.
- **Tests**: 401 Python tests, plus `tests/e2e/flow_online.js` (34 browser checks).
