# 🏆 Champions Club — Sports Club Management System
> **Odoo Hackathon 2026** | Unified Racket & Athletic Club Operating Platform

Champions Club is a unified sports club operating system built on **Odoo 17**, designed to eliminate fragmented workflows (Excel sheets, WhatsApp court groups, paper chits, phone reservations) and replace them with a cohesive, premium SaaS platform for:
- 🎾 **Tennis, Padel & Badminton Court Management**
- 💳 **Membership Management (Gold, Silver, Junior)**
- 📅 **Court Bookings & Peak Scheduling**
- 🛍️ **Sports Equipment Pro-Shop & Inventory**
- 🥗 **Clubhouse Cafeteria & Sports Bar POS**
- 👥 **Member CRM & Financial / Utilization Reporting**

---

## 🧭 Project layout and how to run

| Where | What |
|---|---|
| `addons/club_management/` | The platform: memberships, courts, bookings, pricing, shop and bar orders, CRM, reports, and the OWL screens described below. **Odoo 17.** |
| `addons/club_website/` | The public website (Home, Membership, Courts, Shop, Join, status page). Depends on `club_management`. |
| `preview/` | An offline, mock-data preview of the OWL screens (no Odoo needed). See "Running the Unified SPA Frontend Preview". |
| `docker-compose.yml`, `docker/` | Odoo 17 and Postgres. |

```bash
docker compose build db && docker compose up -d
docker compose run --rm odoo odoo -d club -i club_management,club_website --stop-after-init
# then open http://localhost:8069  (login admin / admin)
```

Run commands, the CRM workflow, tests and the browser checks are documented in `CLAUDE.md` and
`addons/club_management/tests/e2e/README.md`. The earlier standalone `champions_club/` module (Odoo 19)
was retired: everything it held lives in `club_management`, wired to real data.

---

## 🛍️ Module 3: Pro-Shop & Equipment eCommerce (Odoo OWL)

The Pro-Shop delivers a state-of-the-art sports club eCommerce experience integrated directly with **Odoo Inventory, Sales, and the club's member pricing**:

### 1. Key Capabilities
- **Catalog Browsing**: 4-column responsive product grid (Desktop: 4 columns, Tablet: 2–3 columns, Mobile: 1–2 columns).
- **Instant Search with Debouncing**: Real-time keyword search across product name, sport type, and categories (e.g. typing "tennis" shows rackets, balls, and shoes).
- **Categories & Filters**:
  - Filter pills: `All`, `Rackets`, `Balls`, `Shoes`, `Accessories`, `Apparel`.
  - `In Stock Only` availability toggle.
  - Active item count feedback.
- **Product Card (`ProductCard`)**:
  - High-res product icon & sport category badge.
  - Clear stock status (e.g., `🟢 8 available` or `🔴 Out of Stock`). Availability is never communicated by color alone.
  - Regular price + Gold Member discounted price preview.
  - Direct `[ Add to Cart ]` or disabled `[ Unavailable ]` button.
- **Product Details (`ProductDetail` Modal)**:
  - Large product image preview, full technical specifications, and category tag.
  - Dynamic `QuantitySelector` (`[-] 1 [+]`) with strict upper bound validation against Odoo Inventory stock levels.
  - Member pricing tag: `Gold Member: ₹X (20% off)`.
- **Shopping Cart (`Cart` Slide-Over Drawer)**:
  - Slide-out drawer with backdrop blur.
  - `CartItem` rows with live quantity adjustments and item removal (`🗑️`).
  - **Server-Side Pricing**: Frontend delegates discount calculations to Odoo backend RPC (`calculate_cart_pricing`). Subtotal, Gold Member Discount (-20%), and Total are computed server-side.
  - `[ Continue Shopping ]` and `[ Proceed to Checkout ]`.
- **Checkout (`CheckoutPage`)**:
  - Customer summary: Chitt Hirpara (Gold Member verified).
  - **Fulfillment Options**:
    - `○ Collect at Club`: Immediate pickup at Clubhouse Front Desk.
    - `○ Home Delivery`: Courier dispatch with customer address input.
  - **Payment Options**: Member Club Account (Monthly Settlement) or UPI / NetBanking / Cards.
  - Order summary pane with real-time stock revalidation before order confirmation.
- **Order Confirmation (`OrderConfirmation`)**:
  - Visual checkmark banner: `✓ Order Confirmed`.
  - Order Reference: `#SC-1024`.
  - Full breakdown of ordered equipment, quantities, fulfillment method, and final totals.
  - Direct actions to continue shopping or review in Odoo Sales.
- **Error & Loading States**:
  - Out of stock: *"⚠ This product is currently out of stock."*
  - Quantity too high: *"⚠ Only 3 units are available."*
  - Stock changed during checkout: *"⚠ Stock availability changed. Please review your cart."*
  - Shimmering skeleton loader grid during data fetch (`cc-skeleton-grid`).

### 2. Component Structure

```
ShopPage (Root Orchestrator & State Coordinator)
├── ShopHeader (Brand, Navigation, Member Badge, Search with debounce, Cart Trigger)
├── CategoryFilter (All, Rackets, Balls, Shoes, Accessories, Apparel, In Stock Only)
├── ProductGrid
│   ├── SkeletonGrid (4 shimmering placeholder cards during loading)
│   └── ProductCard (Image, Category, Name, Stock Badge, Price, Add to Cart)
├── ProductDetail (Modal: Large preview, specs, member pricing, QuantitySelector)
│   └── QuantitySelector ([-] <qty> [+], stock bounds enforcement)
├── Cart (Slide-over drawer with backdrop)
│   ├── CartItem (Item icon, name, unit price, QuantitySelector, line total, remove)
│   └── CartFooter (Subtotal, Gold Member Discount, Total, [ Checkout ])
├── CheckoutPage
│   ├── CustomerSection (Chitt Hirpara, Gold Tier active)
│   ├── FulfillmentSection (Collect at Club vs Home Delivery + Address)
│   ├── PaymentSection (Member Folio Account vs Odoo Payment Acquirer)
│   └── OrderSummaryPane (Item breakdown, Subtotal, Discount, [ Place Order ])
└── OrderConfirmation (✓ Order Confirmed, #SC-1024, Fulfillment, Equipment list, Total)
```

### 3. Backend Integration Architecture

```
OWL Component (ShopPage)
       ↓
Odoo RPC Service (`club.shop.product`, `club.shop.order`)
       ↓
Member tier pricelist (one pricing rule for shop, bar and POS)
       ↓
Club order (`club.order`) + Odoo Inventory (`stock.quant`)
       ↓
PostgreSQL Database
```

- **Models**: `club.shop.product`, `club.shop.order` (`addons/club_management/models/frontend_api.py`); pricing, orders and stock in `models/club_pos_and_shop.py`
- **Key Methods**:
  - `get_shop_catalog(category, search_query, partner_id)`: live stock and the member's price
  - `place_order(vals)`: the server re-prices the basket, checks and deducts stock, and creates the order (`ORD/00001`)

---

## ☕ Module 4: Bar + POS Module (Odoo OWL)

The Bar & Cafeteria POS module delivers a high-speed commercial point-of-sale interface tailored for sports clubs:

### 1. Key Capabilities
- **Commercial POS Workspace**: 3-column desktop layout (Categories & Catalog left, Product Grid center, Current Order panel right). Touch-friendly for POS terminals and tablets.
- **Table Floor Management (`TableGrid` & `TableCard`)**:
  - Live floor layout with seating capacity and status (`AVAILABLE` in green vs `OCCUPIED` in amber).
  - Tapping an available table starts a new tab; tapping an occupied table reopens its active tab and items.
- **Category Tabs (`CategoryTabs`)**:
  - Quick filters: `All Items`, `Drinks`, `Food`, `Snacks`, `Coffee & Tea`, `Protein & Shakes`.
- **Product Catalog & Search (`ProductGrid`, `ProductCard`)**:
  - High-res icons, unit pricing, real-time stock levels, and `+ ADD` actions.
  - Search bar with instant filtering and debouncing.
  - Out-of-stock items automatically rendered disabled with clear status badge.
- **Current Order Panel (`OrderPanel`, `OrderItem`)**:
  - Active table indicator with fast switch-table action.
  - Selected member widget with real-time membership privilege badge.
  - Line items with `+`, `−`, and `✕` remove controls.
  - Subtotal, Membership Discount, and Total.
  - `[ Keep Tab Open ]` and `[ Pay Now ]`.
- **Member Selection (`MemberSelector`)**:
  - Fast modal to assign club members (Chitt Hirpara - Gold, Aarav Patel - Silver, Rohan Shah - Junior, or Walk-in Guest).
  - **CRITICAL BACKEND PRICING**: The frontend never hardcodes discount math. Membership discounts (Gold 15%, Silver 10%, Junior 5%) are fetched and calculated directly by the Odoo backend RPC (`calculate_order_pricing`).
- **Open Tabs Management (`OpenTabs`)**:
  - Fast-access modal listing all active open tabs with guest name, order reference, and current folio amount.
- **Tender & Payment Processing (`PaymentModal`)**:
  - Methods: `CASH`, `CARD`, `UPI / QR`.
  - Processing state disables the button and displays `"Processing payment..."` to prevent double-charging.
- **Success Screen (`SuccessScreen`)**:
  - `✓ Payment Successful` banner with Order Ref (`POS-00125`), Table, Customer, Amount, and Payment method.
  - Fast buttons: `[ New Order ]` and `[ View Receipt ]`.
- **POS Shift Management (`ShiftPanel`)**:
  - Cashier shift metrics: Current Staff (Rahul Verma), Session Started, Completed Orders (42), Cash/Card/UPI breakdown, and Total Revenue (₹22,500).
  - `[ Close POS Shift (Z-Report) ]`.
- **Order History (`OrderHistory`)**:
  - Shift register audit log of all completed transactions with timestamps, tender methods, and amounts.

### 2. Component Structure

```
BarPOSPage (Root Orchestrator)
├── Topbar (Brand, Table Selector, View Switcher, Open Tabs Badge, Shift Button, Staff Avatar)
├── Workspace (3-Column Layout)
│   ├── CatalogPanel (Left / Center)
│   │   ├── SearchBar (Input with debounce & clear)
│   │   ├── CategoryTabs (Drinks, Food, Snacks, Coffee, Shakes)
│   │   └── ProductGrid
│   │       └── ProductCard (Image, Category, Name, Price, Stock, + ADD)
│   └── OrderPanel (Right Column)
│       ├── OrderHeader (Active Table, Clear Order, Switch Table)
│       ├── MemberSelectorWidget (Assigned member, tier discount badge)
│       ├── OrderItemsList
│       │   └── OrderItem (Icon, Name, Price, Qty +/- controls, Line Total, Remove)
│       └── OrderFooter (Subtotal, Backend Discount, Total, [ Keep Tab Open ], [ Pay Now ])
├── TableGrid (Floor view: Table cards, capacity, status Available / Occupied)
│   └── TableCard
├── MemberSelector (Modal: Search & assign club member, triggers backend pricing RPC)
├── OpenTabs (Drawer: Lists open tables with running balances)
├── PaymentModal (Tender selection: Cash, Card, UPI, processing state)
├── SuccessScreen (✓ Payment Successful, Order #, Table, Amount, [ New Order ], [ Receipt ])
├── ShiftPanel (Modal: Session metrics, tender breakdown, [ Close Shift ])
└── OrderHistory (Session register log with status & timestamps)
```

---

## 🎾 Module 2: Court + Booking Module (Odoo OWL)

The Court + Booking module delivers a premium, responsive court reservation platform:

### 1. Key Capabilities
- **Date Selector**: `[ Today ]`, `[ Tomorrow ]`, and native date picker.
- **CourtGrid Matrix**: Displays courts (Court 1 Padel, Court 2 Tennis Clay, Court 3 Tennis Hard, Court 4 Badminton) with 30-min time slots from 06:00 to 21:00.
- **Visual Slot States**:
  - `Available` (Open & clickable)
  - `Booked` (Hatched background with red indicator)
  - `Selected` (Emerald accent fill with checkmark)
  - `Disabled` (Past or maintenance)
- **1-Hour Bookings**: Every reservation is exactly 1 hour duration.
- **Dynamic Pricing via Backend**: Prices are calculated by backend RPC (`club.booking.calculate_booking_price`), not duplicated in JS. Gold members receive free off-peak & discounted prime-time rates.
- **Confirmation Flow**: `BookingConfirmationModal` displays court, date, start/end time, member name, plan, and dynamic price.
- **Booking Confirmed Screen**: Shows `✓ Booking Confirmed`, booking reference (`BK-00001`), and `[ Done ]` action.
- **My Bookings View**:
  - Filter tabs: `Upcoming`, `Completed`, `Cancelled`.
  - Detailed reservation cards with status badge (`CONFIRMED`, `COMPLETED`, `CANCELLED`).
  - **Cancel Booking Dialog**: "Cancel this booking?" confirmation dialog. Upon cancellation, the slot immediately becomes available in the grid.
- **Graceful Error Handling**:
  - Double booking: *"⚠ This court is no longer available."*
  - Daily limit: *"⚠ You have reached your maximum of 2 bookings for today."*
  - Expired membership: *"⚠ Your membership has expired. Please renew your membership."*
  - Network error: *"Something went wrong. Please try again."*

---

### 2. Component Structure

```
CourtBookingPage (Root Orchestrator)
├── DateSelector ([ Today ], [ Tomorrow ], [ Select Date ])
├── CourtGrid
│   ├── TimeHeaderRow (06:00, 06:30, 07:00, ...)
│   └── CourtRow
│       ├── CourtLabelCell (Sticky first column: Name, Surface, Sport)
│       └── TimeSlot (Visual states: Available, Booked, Selected, Disabled)
├── SelectionActionBar (Appears when a slot is chosen: Court, 1-hr range, [ Continue ])
├── BookingConfirmationModal (Summary box, dynamic backend price, [ Confirm Booking ])
├── BookingConfirmedModal (✓ Booking Confirmed, ID: BK-00001, [ Done ])
├── MyBookings (Upcoming, Completed, Cancelled tabs)
│   └── BookingCard (Court info, date, time, fee, [ Cancel Booking ])
└── CancelBookingModal ("Cancel this booking?", [ Keep Booking ], [ Cancel Booking ])
```

---

## 🎖️ Module 1: Membership Plans UI

1. **GOLD** (Premium / Full Access) — ₹5,000 / year (`MOST POPULAR`)
2. **SILVER** (Standard) — ₹3,000 / year
3. **JUNIOR** (Under 18 / Discounted) — ₹1,500 / year (`UNDER 18`)

Features:
- Responsive desktop (3 cards), tablet (2+1), mobile (1-column).
- Minimalist, distraction-free aesthetic with hairline borders.
- Detailed 18-point feature comparison table.

---

## 🖥️ Running the Unified SPA Frontend Preview

The frontend runs locally as a **Single Page Application (SPA)** with **client-side hash routing** and **zero external dependencies** (no Node.js, React, Mongo, or MERN):

1. **Unified Application Entry Point**:
   - **Unified Suite URL**: [http://localhost:8070/](http://localhost:8070/)
   - **Memberships Route**: [http://localhost:8070/#/memberships](http://localhost:8070/#/memberships)
   - **Court Booking Route**: [http://localhost:8070/#/courts](http://localhost:8070/#/courts)
   - **Pro-Shop Route**: [http://localhost:8070/#/shop](http://localhost:8070/#/shop)
   - **Bar & Cafeteria POS Route**: [http://localhost:8070/#/pos](http://localhost:8070/#/pos)

> **Zero Page Reloads**: Clicking between **Memberships**, **Courts**, **Shop**, and **Bar + POS** in the top navigation transitions instantly within the single viewport `<div id="app-viewport">` via `js/router.js`. No need to open separate files or reload pages! All direct legacy URLs (`courts.html`, `shop.html`, `pos.html`) automatically forward into their corresponding routed view.

2. **Testing Bar + POS Workflow in Browser**:
   1. Open [http://localhost:8070/pos.html](http://localhost:8070/pos.html).
   2. Notice the 3-column commercial layout: categories on top, menu item cards in center, and current table order on right.
   3. Search `"coffee"` or filter by **Drinks**, **Food**, **Snacks**, **Coffee**, or **Shakes**.
   4. Tap `+ ADD` on any item (e.g. Cold Brew Nitro or Clubhouse Grilled Chicken Wrap).
   5. Tap **Change Member ▾** → Pick **Aarav Patel (Silver)** or **Chitt Hirpara (Gold)**. Notice the discount updates server-side automatically.
   6. Click **🪑 Floor** to view the table grid. Click an available table (e.g. Table 02) to assign, or click an occupied table to reopen its tab.
   7. Click **📑 Open Tabs** to review all open tables with running balances.
   8. Click **Pay Now** → Choose **CASH**, **CARD**, or **UPI / QR** → Click **Confirm & Complete Payment**.
   9. Observe the button state change to `"Processing payment..."` to prevent double-clicks, followed by the **✓ Payment Successful** modal with receipt summary.
   10. Click **⏱️ Shift** to view cashier shift metrics (orders count, tender breakdown, and total revenue).
   11. Click **📜 Orders** to review the completed order audit log.
3. **Testing Pro-Shop Workflow in Browser**:
   1. Open [http://localhost:8070/shop.html](http://localhost:8070/shop.html).
   2. Filter by category (e.g. click **Rackets** or **Balls**), or search `"tennis"`.
   3. Click any product card (e.g. **Wilson Carbon Force Pro Padel Racket**) to inspect full specifications and stock.
   4. Adjust quantity using `[-] 1 [+]` and click **Add to Cart**.
   5. Notice the **Shopping Cart** drawer slides open showing backend-calculated 20% Gold Member discount.
   6. Click **Proceed to Checkout** → Choose fulfillment (**Collect at Club** or **Home Delivery**).
   7. Click **Place Order** → Odoo validates stock, deducts inventory, and renders **✓ Order Confirmed** with Order ID `#SC-1024`.
4. **Testing Court Booking Workflow in Browser**:
   1. Select date: Click **Today** or **Tomorrow**.
   2. Select an open slot (e.g. **Court 2** at **6:30 PM**).
   3. See floating bottom bar: *"Court 2 • 6:30 PM – 7:30 PM • Gold Member"*.
   4. Click **Continue** → Review modal with member plan and price from backend.
   5. Click **Confirm Booking** → View *"✓ Booking Confirmed"* dialog with Booking ID.
   6. Click **Done** → Switch to **My Bookings** tab to see your confirmed reservation.
   7. Click **Cancel Booking** → Confirm dialog → Booking is cancelled and the slot is freed up in the availability grid.

---

## 🔌 Backend Integration Contract

The OWL screens call the server with `orm.call("model", "method", ...)`. Each of these exists in
`addons/club_management` (`tests/test_frontend_api.py` fails if a screen calls one that does not):

| Screen | Model | Methods |
|---|---|---|
| Court Booking | `club.court` | `get_courts_list` |
| | `club.booking` | `get_availability(date)`, `calculate_booking_price`, `create_booking_api`, `get_partner_bookings`, `action_cancel` |
| Memberships | `club.membership.plan` | `get_frontend_plans` |
| Members (all screens) | `res.partner` | `get_current_member`, `get_members_list`, `register_or_renew_member` |
| Pro-Shop | `club.shop.product` | `get_shop_catalog(category, search, partner_id)` |
| | `club.shop.order` | `calculate_order_pricing`, `place_order` |
| Bar + POS | `club.pos.table` | `get_tables_data` |
| | `club.pos.product` | `get_products_data(category, search)` |
| | `club.pos.order` | `calculate_order_pricing(items, plan_code, partner_id)`, `process_payment_api`, `get_recent_orders` |
| | `club.pos.session` | `get_current_shift` |

Prices, discounts and stock are always computed on the server from the member's tier pricelist;
the screens never calculate them. Bar tabs and shop orders are saved as `club.order` records
(Club > Bar & Shop Orders).

Registered OWL client actions: `club_management.membership_plans`, `club_management.court_booking`,
`club_management.shop`, `club_management.bar_pos`.
