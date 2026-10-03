/**
 * Champions Club — Sports Club Management System
 * Bar + Cafeteria POS Frontend Architecture
 *
 * Modular Components:
 * - BarPOSPage (Root Coordinator & State Manager)
 * - TableGrid & TableCard
 * - CategoryTabs
 * - ProductGrid & ProductCard
 * - MemberSelector
 * - OrderPanel & OrderItem
 * - OpenTabs
 * - PaymentModal
 * - SuccessScreen
 * - ShiftPanel
 * - OrderHistory
 */

// ==========================================================================
// 1. TableCard Component
// ==========================================================================
const TableCard = {
  render(table, isSelected) {
    const isAvailable = table.status === "available";
    const statusClass = isAvailable ? "status-available" : "status-occupied";
    const selectedClass = isSelected ? "selected-table" : "";

    let bodyContent = `
      <div class="cc-table-meta-row">
        <span>Capacity:</span>
        <span>${table.capacity} Seats</span>
      </div>
    `;

    if (!isAvailable && table.active_order) {
      bodyContent += `
        <div class="cc-table-meta-row">
          <span>Guest:</span>
          <strong style="color: #FFFFFF;">${table.active_order.member_name}</strong>
        </div>
        <div class="cc-table-meta-row">
          <span>Tab Ref:</span>
          <span>${table.active_order.order_ref}</span>
        </div>
        <div class="cc-tab-amount">
          Total: ₹${table.active_order.amount.toLocaleString("en-IN")}
        </div>
      `;
    } else {
      bodyContent += `
        <div style="font-size: 0.78rem; color: #10B981; margin-top: 0.5rem; font-weight: 600;">
          Ready for seating
        </div>
      `;
    }

    return `
      <div class="cc-table-card ${statusClass} ${selectedClass}" data-table-id="${table.id}">
        <div class="cc-table-header">
          <h4 class="cc-table-name">${table.name}</h4>
          <span class="cc-table-status-badge">${table.status}</span>
        </div>
        <div class="cc-table-body">
          ${bodyContent}
        </div>
      </div>
    `;
  }
};

// ==========================================================================
// 2. TableGrid Component
// ==========================================================================
const TableGrid = {
  render(tables, currentTableId) {
    const cardsHtml = tables
      .map((t) => TableCard.render(t, t.id === currentTableId))
      .join("");

    return `
      <div class="cc-tables-grid-view">
        <div class="cc-tables-grid-header">
          <div>
            <h3>Clubhouse Floor &amp; Table Layout</h3>
            <p style="font-size: 0.84rem; color: #94A3B8; margin: 0.25rem 0 0 0;">
              Select an available table to begin a new order, or tap an occupied table to reopen its tab.
            </p>
          </div>
          <div class="cc-table-legend">
            <div class="cc-legend-pill">
              <span style="width: 10px; height: 10px; border-radius: 50%; background: #10B981; display: inline-block;"></span>
              <span>Available</span>
            </div>
            <div class="cc-legend-pill">
              <span style="width: 10px; height: 10px; border-radius: 50%; background: #F59E0B; display: inline-block;"></span>
              <span>Occupied (Open Tab)</span>
            </div>
          </div>
        </div>

        <div class="cc-tables-cards-grid">
          ${cardsHtml}
        </div>
      </div>
    `;
  }
};

// ==========================================================================
// 3. CategoryTabs Component
// ==========================================================================
const CategoryTabs = {
  render(categories, selectedCategoryId) {
    const tabsHtml = categories
      .map(
        (cat) => `
        <button type="button" class="cc-cat-tab ${cat.id === selectedCategoryId ? "active" : ""}" data-category-id="${cat.id}">
          <span>${cat.icon}</span>
          <span>${cat.label}</span>
        </button>
      `
      )
      .join("");

    return `
      <div class="cc-category-tabs-bar">
        ${tabsHtml}
      </div>
    `;
  }
};

// ==========================================================================
// 4. PosProductCard Component
// ==========================================================================
const PosProductCard = {
  render(product) {
    const isOut = !product.is_available || product.stock <= 0;
    const cardClass = isOut ? "cc-pos-product-card out-of-stock" : "cc-pos-product-card";

    const buttonHtml = isOut
      ? `<span style="font-size: 0.7rem; color: #EF4444; font-weight: 700;">OUT OF STOCK</span>`
      : `<button type="button" class="cc-btn-add-item cc-action-add-product" data-product-id="${product.id}">+ ADD</button>`;

    return `
      <div class="${cardClass}" data-product-id="${product.id}">
        <div class="cc-product-media">
          <span>${product.image_icon}</span>
        </div>
        <span class="cc-product-cat">${product.category_label || product.category}</span>
        <h3 class="cc-product-name">${product.name}</h3>
        <div class="cc-product-footer">
          <span class="cc-product-price">₹${product.price}</span>
          ${buttonHtml}
        </div>
      </div>
    `;
  }
};

// ==========================================================================
// 5. PosProductGrid Component
// ==========================================================================
const PosProductGrid = {
  render(products, isLoading) {
    if (isLoading) {
      return `
        <div class="cc-pos-grid-container" style="display: flex; align-items: center; justify-content: center; height: 300px;">
          <div style="color: #94A3B8; font-size: 0.9rem;">Fetching live Odoo catalog...</div>
        </div>
      `;
    }

    if (!products || products.length === 0) {
      return `
        <div class="cc-pos-grid-container" style="text-align: center; padding: 4rem 1rem;">
          <span style="font-size: 2.5rem; display: block; margin-bottom: 0.75rem;">🔍</span>
          <h4 style="color: #FFFFFF; margin: 0 0 0.35rem 0;">No Menu Items Found</h4>
          <p style="color: #94A3B8; font-size: 0.85rem; margin: 0;">Try a different keyword or category.</p>
        </div>
      `;
    }

    const cardsHtml = products.map((p) => PosProductCard.render(p)).join("");

    return `
      <div class="cc-pos-grid-container">
        <div class="cc-pos-products-grid">
          ${cardsHtml}
        </div>
      </div>
    `;
  }
};

// ==========================================================================
// 6. OrderItem Component
// ==========================================================================
const OrderItem = {
  render(item) {
    const { product, qty } = item;
    const lineTotal = product.price * qty;

    return `
      <div class="cc-order-item-row" data-product-id="${product.id}">
        <div class="cc-order-item-icon">
          ${product.image_icon}
        </div>
        <div class="cc-order-item-details">
          <h4 class="cc-item-title">${product.name}</h4>
          <span class="cc-item-unit-price">₹${product.price} × ${qty}</span>
        </div>

        <div class="cc-order-qty-ctrl">
          <button type="button" class="cc-qty-btn cc-action-dec-qty" data-product-id="${product.id}">−</button>
          <span class="cc-qty-number">${qty}</span>
          <button type="button" class="cc-qty-btn cc-action-inc-qty" data-product-id="${product.id}">+</button>
        </div>

        <span class="cc-item-line-total">₹${lineTotal}</span>
        <button type="button" class="cc-btn-remove-line cc-action-remove-line" data-product-id="${product.id}" title="Remove item">✕</button>
      </div>
    `;
  }
};

// ==========================================================================
// 7. OrderPanel Component
// ==========================================================================
const OrderPanel = {
  render(currentTable, selectedMember, cartItems, pricing) {
    let itemsContent = "";
    if (!cartItems || cartItems.length === 0) {
      itemsContent = `
        <div class="cc-empty-order-state">
          <span class="cc-empty-icon">🍽️</span>
          <h4>Order is Empty</h4>
          <p>Select items from the catalog or tap a category to add products.</p>
        </div>
      `;
    } else {
      itemsContent = cartItems.map((item) => OrderItem.render(item)).join("");
    }

    return `
      <div class="cc-pos-order-panel">
        <div class="cc-order-header">
          <div class="cc-order-title-row">
            <h2 class="cc-order-table-label">${currentTable ? currentTable.name : "Table 01"}</h2>
            <div class="cc-order-actions-top">
              <button type="button" class="cc-btn-ghost-sm cc-action-switch-table">Switch Table</button>
              <button type="button" class="cc-btn-ghost-sm cc-action-clear-order">Clear</button>
            </div>
          </div>

          <!-- Member Selector Box -->
          <div class="cc-member-selector-box cc-action-open-member-modal" title="Click to assign club member">
            <div class="cc-member-info-left">
              <div class="cc-mem-avatar">👤</div>
              <div class="cc-mem-text">
                <span class="cc-mem-name">${selectedMember.name}</span>
                <span class="cc-mem-tier">${selectedMember.plan} Member Privilege</span>
              </div>
            </div>
            <span class="cc-btn-change-member">Change Member ▾</span>
          </div>
        </div>

        <div class="cc-order-items-list">
          ${itemsContent}
        </div>

        <div class="cc-order-footer">
          <div class="cc-order-calc-breakdown">
            <div class="cc-calc-row">
              <span>Subtotal</span>
              <span>${pricing.formatted_subtotal}</span>
            </div>
            <div class="cc-calc-row discount">
              <span>${pricing.discount_label}</span>
              <span>${pricing.formatted_discount}</span>
            </div>
            <div class="cc-calc-row total">
              <span>Total Amount</span>
              <span class="cc-total-num">${pricing.formatted_total}</span>
            </div>
          </div>

          <div class="cc-order-footer-actions">
            <button type="button" class="cc-btn-tab-save cc-action-save-tab">Keep Tab Open</button>
            <button type="button" class="cc-btn-pay-now cc-action-open-payment" ${cartItems.length === 0 ? "disabled" : ""}>
              Pay Now
            </button>
          </div>
        </div>
      </div>
    `;
  }
};

// ==========================================================================
// 8. PaymentModal Component
// ==========================================================================
const PaymentModal = {
  render(currentTable, selectedMember, pricing, paymentMethod, isProcessing, isOpen) {
    if (!isOpen) return "";

    return `
      <div class="cc-pos-modal-backdrop" id="payment-modal-backdrop">
        <div class="cc-pos-modal-dialog cc-payment-modal">
          <div class="cc-modal-head">
            <h3>Settle Table Bill — ${currentTable ? currentTable.name : "Table 01"}</h3>
            <button type="button" class="cc-modal-close cc-action-close-payment">✕</button>
          </div>

          <div class="cc-modal-body">
            <div class="cc-payment-total-box">
              <div class="cc-pay-label">Total Amount Due</div>
              <div class="cc-pay-total-val">${pricing.formatted_total}</div>
              <div class="cc-pay-member-pill">
                ${selectedMember.name} • ${pricing.discount_label}
              </div>
            </div>

            <div style="font-size: 0.82rem; font-weight: 600; color: #94A3B8; margin-bottom: 0.65rem;">
              Select Payment Method:
            </div>

            <div class="cc-payment-methods-grid">
              <div class="cc-pay-method-btn ${paymentMethod === "cash" ? "selected" : ""}" data-method="cash">
                <span class="cc-pay-icon">💵</span>
                <span class="cc-pay-method-title">Cash</span>
              </div>
              <div class="cc-pay-method-btn ${paymentMethod === "card" ? "selected" : ""}" data-method="card">
                <span class="cc-pay-icon">💳</span>
                <span class="cc-pay-method-title">Card</span>
              </div>
              <div class="cc-pay-method-btn ${paymentMethod === "upi" ? "selected" : ""}" data-method="upi">
                <span class="cc-pay-icon">📱</span>
                <span class="cc-pay-method-title">UPI / QR</span>
              </div>
            </div>

            <button type="button" class="cc-btn-confirm-payment cc-action-confirm-pay" ${isProcessing ? "disabled" : ""}>
              ${isProcessing ? `<span>Processing payment...</span>` : `<span>Confirm &amp; Complete Payment</span>`}
            </button>
          </div>
        </div>
      </div>
    `;
  }
};

// ==========================================================================
// 9. SuccessScreen Component
// ==========================================================================
const SuccessScreen = {
  render(result, isOpen) {
    if (!isOpen || !result) return "";

    return `
      <div class="cc-pos-modal-backdrop" id="success-modal-backdrop">
        <div class="cc-pos-modal-dialog">
          <div class="cc-modal-body cc-success-screen">
            <div class="cc-success-badge-icon">✓</div>
            <h2 class="cc-success-headline">Payment Successful</h2>
            <p style="font-size: 0.84rem; color: #94A3B8; margin: 0;">Commercial POS receipt recorded in Odoo database.</p>

            <div class="cc-receipt-card">
              <div class="cc-receipt-row">
                <span>Order Reference:</span>
                <strong>${result.order_ref}</strong>
              </div>
              <div class="cc-receipt-row">
                <span>Table:</span>
                <strong>${result.table_name}</strong>
              </div>
              <div class="cc-receipt-row">
                <span>Member / Customer:</span>
                <strong>${result.member_name}</strong>
              </div>
              <div class="cc-receipt-row">
                <span>Payment Method:</span>
                <strong>${result.payment_method}</strong>
              </div>
              <div class="cc-receipt-row highlight">
                <span>Amount Paid:</span>
                <strong class="cc-amt">${result.amount}</strong>
              </div>
            </div>

            <div class="cc-success-actions">
              <button type="button" class="cc-btn-new-order cc-action-new-order">New Order</button>
              <button type="button" class="cc-btn-receipt cc-action-view-receipt">View Receipt</button>
            </div>
          </div>
        </div>
      </div>
    `;
  }
};

// ==========================================================================
// 10. ShiftPanel Component
// ==========================================================================
const ShiftPanel = {
  render(shift, isOpen) {
    if (!isOpen) return "";

    return `
      <div class="cc-pos-modal-backdrop" id="shift-modal-backdrop">
        <div class="cc-pos-modal-dialog">
          <div class="cc-modal-head">
            <h3>Current POS Shift Metrics</h3>
            <button type="button" class="cc-modal-close cc-action-close-shift">✕</button>
          </div>

          <div class="cc-modal-body cc-shift-panel-content">
            <div class="cc-shift-grid">
              <div class="cc-shift-stat-box">
                <div class="cc-stat-lbl">Active Cashier</div>
                <div class="cc-stat-val">${shift.staff_name}</div>
              </div>
              <div class="cc-shift-stat-box">
                <div class="cc-stat-lbl">Session Started</div>
                <div class="cc-stat-val" style="font-size: 0.95rem;">${shift.start_time}</div>
              </div>
              <div class="cc-shift-stat-box">
                <div class="cc-stat-lbl">Completed Orders</div>
                <div class="cc-stat-val" style="color: #10B981;">${shift.orders_count}</div>
              </div>
              <div class="cc-shift-stat-box">
                <div class="cc-stat-lbl">Total Shift Sales</div>
                <div class="cc-stat-val" style="color: #10B981;">${shift.formatted_total}</div>
              </div>
            </div>

            <div class="cc-shift-payment-split">
              <div style="font-size: 0.78rem; text-transform: uppercase; color: #64748B; margin-bottom: 0.4rem; font-weight: 700;">
                Tender Breakdown:
              </div>
              <div class="cc-split-row">
                <span>Cash Register:</span>
                <strong>${shift.formatted_cash}</strong>
              </div>
              <div class="cc-split-row">
                <span>Card Terminal:</span>
                <strong>${shift.formatted_card}</strong>
              </div>
              <div class="cc-split-row">
                <span>UPI QR Gateway:</span>
                <strong>${shift.formatted_upi}</strong>
              </div>
              <div class="cc-split-row total">
                <span>Shift Revenue:</span>
                <strong style="color: #10B981;">${shift.formatted_total}</strong>
              </div>
            </div>

            <button type="button" class="cc-btn-close-shift cc-action-do-close-shift">Close POS Shift (Z-Report)</button>
          </div>
        </div>
      </div>
    `;
  }
};

// ==========================================================================
// 11. OpenTabs Component
// ==========================================================================
const OpenTabs = {
  render(tables, isOpen) {
    if (!isOpen) return "";

    const occupiedTables = tables.filter((t) => t.status === "occupied" && t.active_order);

    const tabsHtml = occupiedTables
      .map(
        (t) => `
        <div class="cc-member-selector-box cc-action-pick-tab" data-table-id="${t.id}" style="padding: 0.85rem 1rem; margin-bottom: 0.65rem;">
          <div>
            <h4 style="margin: 0; font-size: 0.95rem; font-weight: 700; color: #FFFFFF;">${t.name}</h4>
            <span style="font-size: 0.78rem; color: #94A3B8;">${t.active_order.member_name} • ${t.active_order.order_ref}</span>
          </div>
          <div style="text-align: right;">
            <div style="font-size: 1.05rem; font-weight: 700; color: #10B981;">₹${t.active_order.amount}</div>
            <span style="font-size: 0.72rem; color: #D4A347; font-weight: 600;">Open Tab</span>
          </div>
        </div>
      `
      )
      .join("");

    return `
      <div class="cc-pos-modal-backdrop" id="opentabs-modal-backdrop">
        <div class="cc-pos-modal-dialog">
          <div class="cc-modal-head">
            <h3>Currently Open Bar Tabs (${occupiedTables.length})</h3>
            <button type="button" class="cc-modal-close cc-action-close-tabs">✕</button>
          </div>

          <div class="cc-modal-body">
            ${
              occupiedTables.length === 0
                ? `<div style="text-align: center; color: #64748B; padding: 2rem;">No open tabs active.</div>`
                : tabsHtml
            }
          </div>
        </div>
      </div>
    `;
  }
};

// ==========================================================================
// 12. MemberSelector Component
// ==========================================================================
const MemberSelector = {
  render(members, isOpen) {
    if (!isOpen) return "";

    const listHtml = members
      .map(
        (m) => `
        <div class="cc-member-selector-box cc-action-pick-member" data-member-id="${m.id}" style="padding: 0.85rem; margin-bottom: 0.65rem;">
          <div class="cc-member-info-left">
            <div class="cc-mem-avatar">${m.name.substring(0, 2).toUpperCase()}</div>
            <div class="cc-mem-text">
              <span class="cc-mem-name">${m.name}</span>
              <span class="cc-mem-tier" style="${m.plan === "Gold" ? "color: #D4A347;" : m.plan === "Silver" ? "color: #94A3B8;" : m.plan === "Junior" ? "color: #06B6D4;" : "color: #64748B;"}">
                ${m.plan} Member (${m.discountPct}% Bar Discount)
              </span>
            </div>
          </div>
          <span class="cc-btn-change-member">Select</span>
        </div>
      `
      )
      .join("");

    return `
      <div class="cc-pos-modal-backdrop" id="member-modal-backdrop">
        <div class="cc-pos-modal-dialog">
          <div class="cc-modal-head">
            <h3>Assign Club Member to Tab</h3>
            <button type="button" class="cc-modal-close cc-action-close-member">✕</button>
          </div>

          <div class="cc-modal-body">
            <p style="font-size: 0.84rem; color: #94A3B8; margin: 0 0 1rem 0;">
              Membership discounts are retrieved and calculated directly by the Odoo backend.
            </p>
            ${listHtml}
          </div>
        </div>
      </div>
    `;
  }
};

// ==========================================================================
// 13. OrderHistory Component
// ==========================================================================
const OrderHistory = {
  render(orders) {
    const rowsHtml = orders
      .map(
        (ord) => `
        <tr style="border-bottom: 1px solid #1A2332;">
          <td style="padding: 0.85rem 1.25rem; font-weight: 700; color: #FFFFFF;">${ord.order_ref}</td>
          <td style="padding: 0.85rem 1.25rem;">${ord.table}</td>
          <td style="padding: 0.85rem 1.25rem; color: #D4A347;">${ord.member}</td>
          <td style="padding: 0.85rem 1.25rem; font-weight: 700; color: #10B981;">${ord.amount}</td>
          <td style="padding: 0.85rem 1.25rem;"><span style="background: #1E293B; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.76rem;">${ord.method}</span></td>
          <td style="padding: 0.85rem 1.25rem; color: #94A3B8;">${ord.time}</td>
          <td style="padding: 0.85rem 1.25rem;"><span style="color: #10B981; font-weight: 600;">✓ ${ord.status}</span></td>
        </tr>
      `
      )
      .join("");

    return `
      <div style="padding: 1.5rem; overflow-y: auto; flex-grow: 1;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem;">
          <div>
            <h3 style="font-size: 1.2rem; font-weight: 700; margin: 0; color: #FFFFFF;">Shift POS Order History</h3>
            <p style="font-size: 0.84rem; color: #94A3B8; margin: 0.2rem 0 0 0;">Commercial register transactions completed in this session.</p>
          </div>
          <button type="button" class="cc-top-btn cc-action-back-pos">Back to POS</button>
        </div>

        <div style="background: #141B26; border: 1px solid #232D40; border-radius: 8px; overflow: hidden;">
          <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 0.86rem;">
            <thead style="background: #0E131C; border-bottom: 1px solid #222C3D; color: #94A3B8;">
              <tr>
                <th style="padding: 0.85rem 1.25rem;">Order Ref</th>
                <th style="padding: 0.85rem 1.25rem;">Table</th>
                <th style="padding: 0.85rem 1.25rem;">Member</th>
                <th style="padding: 0.85rem 1.25rem;">Amount</th>
                <th style="padding: 0.85rem 1.25rem;">Payment Method</th>
                <th style="padding: 0.85rem 1.25rem;">Time</th>
                <th style="padding: 0.85rem 1.25rem;">Status</th>
              </tr>
            </thead>
            <tbody>
              ${rowsHtml}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }
};

// ==========================================================================
// 14. BarPOSPage Root Controller
// ==========================================================================
class BarPOSController {
  constructor(rootElement) {
    this.root = rootElement;

    this.state = {
      currentView: "pos", // "pos" | "tables" | "history"
      tables: POS_TABLES,
      currentTable: POS_TABLES[3], // Table 04
      categories: POS_CATEGORIES,
      selectedCategory: "all",
      searchQuery: "",
      products: POS_PRODUCTS,

      // Current Cart
      cart: [
        { product: POS_PRODUCTS[0], qty: 2 }, // Espresso x2
        { product: POS_PRODUCTS[11], qty: 1 }, // Burger x1
        { product: POS_PRODUCTS[7], qty: 2 }, // Water x2
      ],
      selectedMember: POS_MEMBERS[0], // Chitt Hirpara (Gold)
      pricing: {
        subtotal: 530,
        formatted_subtotal: "₹530.00",
        discount_amount: 79.5,
        formatted_discount: "-₹79.50",
        discount_label: "Gold Member Discount (15%)",
        discount_pct: 15,
        total: 450.5,
        formatted_total: "₹450.50",
      },

      // Modals
      isOpenTabsOpen: false,
      isMemberSelectorOpen: false,
      isPaymentModalOpen: false,
      isShiftModalOpen: false,
      isSuccessOpen: false,

      // Payment state
      paymentMethod: "upi",
      isProcessingPayment: false,
      lastPaymentResult: null,

      // Shift Metrics
      shiftData: POS_SHIFT_INITIAL,
      orderHistory: POS_ORDERS_LOG,

      loading: false,
      error: null,
    };

    this.searchTimer = null;
    this.init();
  }

  async init() {
    this.render();
    this.bindEvents();
    try {
      await this.recalculatePricing();
    } catch (e) {
      console.warn("PosService pricing error:", e);
    }
    this.render();
  }

  async recalculatePricing() {
    const pricing = await PosService.calculateOrderPricing(
      this.state.cart,
      this.state.selectedMember.planCode
    );
    this.state.pricing = pricing;
  }

  render() {
    const {
      currentView,
      tables,
      currentTable,
      categories,
      selectedCategory,
      searchQuery,
      products,
      cart,
      selectedMember,
      pricing,
      isOpenTabsOpen,
      isMemberSelectorOpen,
      isPaymentModalOpen,
      isShiftModalOpen,
      isSuccessOpen,
      paymentMethod,
      isProcessingPayment,
      lastPaymentResult,
      shiftData,
      orderHistory,
      error,
      loading,
    } = this.state;

    const filtered = products.filter((p) => {
      const matchCat = selectedCategory === "all" || p.category === selectedCategory;
      const matchQuery =
        !searchQuery ||
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.category.toLowerCase().includes(searchQuery.toLowerCase());
      return matchCat && matchQuery;
    });

    const openTabsCount = tables.filter((t) => t.status === "occupied").length;

    let viewContent = "";
    if (currentView === "tables") {
      viewContent = TableGrid.render(tables, currentTable ? currentTable.id : null);
    } else if (currentView === "history") {
      viewContent = OrderHistory.render(orderHistory);
    } else {
      // Main POS Layout
      viewContent = `
        <div class="cc-pos-workspace">
          <!-- Left: Catalog -->
          <div class="cc-pos-catalog-panel">
            <div class="cc-catalog-header-bar">
              <div class="cc-pos-search-box">
                <span class="cc-search-icon">🔍</span>
                <input 
                  type="text" 
                  id="pos-search-input" 
                  class="cc-pos-search-input" 
                  placeholder="Search food, drinks, coffee..." 
                  value="${searchQuery}" 
                  autocomplete="off"
                />
                ${searchQuery ? `<button type="button" class="cc-search-clear cc-action-clear-search">✕</button>` : ""}
              </div>

              <div style="font-size: 0.8rem; color: #94A3B8;">
                Showing <strong style="color: #FFFFFF;">${filtered.length}</strong> items
              </div>
            </div>

            ${CategoryTabs.render(categories, selectedCategory)}
            ${PosProductGrid.render(filtered, loading)}
          </div>

          <!-- Right: Order Panel -->
          ${OrderPanel.render(currentTable, selectedMember, cart, pricing)}
        </div>
      `;
    }

    // Error banner
    let errorBannerHtml = "";
    if (error) {
      errorBannerHtml = `
        <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.35); color: #FCA5A5; padding: 0.75rem 1.5rem; font-size: 0.85rem; display: flex; justify-content: space-between; align-items: center; z-index: 90;">
          <span>${error}</span>
          <button type="button" class="cc-action-dismiss-error" style="background: transparent; border: none; color: inherit; cursor: pointer; font-size: 1rem;">✕</button>
        </div>
      `;
    }

    this.root.innerHTML = `
      <div class="cc-pos-app">
        <!-- Topbar -->
        <header class="cc-pos-topbar">
          <a href="#/memberships" class="cc-pos-brand" style="text-decoration: none;">
            <div class="cc-pos-emblem">☕</div>
            <h1 class="cc-pos-title">Champions Club Bar &amp; POS</h1>
            <span class="cc-pos-badge">Odoo 19 POS</span>
          </a>

          <!-- Cross-Module Nav Links -->
          <nav class="cc-pos-nav-links">
            <a href="#/memberships" class="cc-nav-link">Memberships</a>
            <a href="#/courts" class="cc-nav-link">Courts</a>
            <a href="#/shop" class="cc-nav-link">Shop</a>
            <a href="#/pos" class="cc-nav-link active">Bar + POS</a>
          </nav>

          <div class="cc-pos-top-actions">
            <button type="button" class="cc-top-btn ${currentView === "pos" ? "active" : ""} cc-action-switch-view" data-view="pos">
              <span>🛒 Register</span>
            </button>

            <button type="button" class="cc-top-btn ${currentView === "tables" ? "active" : ""} cc-action-switch-view" data-view="tables">
              <span>🪑 Floor (${currentTable ? currentTable.name : "None"})</span>
            </button>

            <button type="button" class="cc-top-btn ${currentView === "history" ? "active" : ""} cc-action-switch-view" data-view="history">
              <span>📜 Orders</span>
            </button>

            <button type="button" class="cc-top-btn cc-action-open-tabs">
              <span>📑 Open Tabs</span>
              <span class="cc-pill-badge">${openTabsCount}</span>
            </button>

            <button type="button" class="cc-top-btn cc-action-open-shift">
              <span>⏱️ Shift</span>
            </button>

            <div class="cc-staff-profile">
              <div class="cc-staff-avatar">RV</div>
              <div class="cc-staff-info">
                <span class="cc-staff-name">${shiftData.staff_name}</span>
                <span class="cc-staff-role">POS Cashier</span>
              </div>
            </div>
          </div>
        </header>

        ${errorBannerHtml}
        ${viewContent}

        <!-- Modals -->
        ${PaymentModal.render(currentTable, selectedMember, pricing, paymentMethod, isProcessingPayment, isPaymentModalOpen)}
        ${SuccessScreen.render(lastPaymentResult, isSuccessOpen)}
        ${ShiftPanel.render(shiftData, isShiftModalOpen)}
        ${OpenTabs.render(tables, isOpenTabsOpen)}
        ${MemberSelector.render(POS_MEMBERS, isMemberSelectorOpen)}
      </div>
    `;

    // Keep search focus
    const sInput = document.getElementById("pos-search-input");
    if (sInput && document.activeElement?.id === "pos-search-input") {
      sInput.focus();
      sInput.setSelectionRange(sInput.value.length, sInput.value.length);
    }
  }

  bindEvents() {
    this.root.addEventListener("click", async (e) => {
      // 1. Switch View
      const switchBtn = e.target.closest(".cc-action-switch-view");
      if (switchBtn) {
        this.state.currentView = switchBtn.dataset.view;
        this.state.error = null;
        this.render();
        return;
      }

      if (e.target.closest(".cc-action-back-pos")) {
        this.state.currentView = "pos";
        this.render();
        return;
      }

      // 2. Select Table from Floor
      const tableCard = e.target.closest(".cc-table-card");
      if (tableCard) {
        const tId = Number(tableCard.dataset.tableId);
        const table = this.state.tables.find((t) => t.id === tId);
        if (table) {
          this.state.currentTable = table;
          this.state.currentView = "pos";

          if (table.status === "occupied" && table.active_order) {
            this.state.cart = [
              { product: POS_PRODUCTS[1], qty: 1 },
              { product: POS_PRODUCTS[8], qty: 1 },
            ];
          } else {
            this.state.cart = [];
          }
          await this.recalculatePricing();
          this.render();
        }
        return;
      }

      // 3. Category Tab Click
      const catTab = e.target.closest(".cc-cat-tab");
      if (catTab) {
        this.state.selectedCategory = catTab.dataset.categoryId;
        this.render();
        return;
      }

      // 4. Clear Search
      if (e.target.closest(".cc-action-clear-search")) {
        this.state.searchQuery = "";
        this.render();
        return;
      }

      // 5. Add Product to Order
      const addBtn = e.target.closest(".cc-action-add-product") || e.target.closest(".cc-pos-product-card");
      if (addBtn) {
        const pId = Number(addBtn.dataset.productId);
        const product = POS_PRODUCTS.find((p) => p.id === pId);
        if (product) {
          if (!product.is_available || product.stock <= 0) {
            this.state.error = `⚠ ${product.name} is currently out of stock.`;
            this.render();
            return;
          }

          const existing = this.state.cart.find((i) => i.product.id === product.id);
          const curQty = existing ? existing.qty : 0;
          if (curQty + 1 > product.stock) {
            this.state.error = `⚠ Insufficient stock: only ${product.stock} units of ${product.name} available.`;
            this.render();
            return;
          }

          if (existing) {
            existing.qty += 1;
          } else {
            this.state.cart.push({ product, qty: 1 });
          }

          this.state.error = null;
          await this.recalculatePricing();
          this.render();
        }
        return;
      }

      // 6. Quantity Controls in Order
      if (e.target.closest(".cc-action-inc-qty")) {
        const pId = Number(e.target.closest(".cc-action-inc-qty").dataset.productId);
        const item = this.state.cart.find((i) => i.product.id === pId);
        if (item) {
          if (item.qty + 1 > item.product.stock) {
            this.state.error = `⚠ Only ${item.product.stock} units available in stock.`;
            this.render();
            return;
          }
          item.qty += 1;
          this.state.error = null;
          await this.recalculatePricing();
          this.render();
        }
        return;
      }

      if (e.target.closest(".cc-action-dec-qty")) {
        const pId = Number(e.target.closest(".cc-action-dec-qty").dataset.productId);
        const item = this.state.cart.find((i) => i.product.id === pId);
        if (item) {
          if (item.qty > 1) {
            item.qty -= 1;
          } else {
            this.state.cart = this.state.cart.filter((i) => i.product.id !== pId);
          }
          this.state.error = null;
          await this.recalculatePricing();
          this.render();
        }
        return;
      }

      if (e.target.closest(".cc-action-remove-line")) {
        const pId = Number(e.target.closest(".cc-action-remove-line").dataset.productId);
        this.state.cart = this.state.cart.filter((i) => i.product.id !== pId);
        await this.recalculatePricing();
        this.render();
        return;
      }

      // 7. Clear Order
      if (e.target.closest(".cc-action-clear-order")) {
        this.state.cart = [];
        await this.recalculatePricing();
        this.render();
        return;
      }

      // 8. Switch Table Action
      if (e.target.closest(".cc-action-switch-table")) {
        this.state.currentView = "tables";
        this.render();
        return;
      }

      // 9. Open / Close Member Selector
      if (e.target.closest(".cc-action-open-member-modal")) {
        this.state.isMemberSelectorOpen = true;
        this.render();
        return;
      }

      if (e.target.closest(".cc-action-close-member") || e.target.id === "member-modal-backdrop") {
        this.state.isMemberSelectorOpen = false;
        this.render();
        return;
      }

      const pickMemberBtn = e.target.closest(".cc-action-pick-member");
      if (pickMemberBtn) {
        const mId = Number(pickMemberBtn.dataset.memberId);
        const mem = POS_MEMBERS.find((m) => m.id === mId);
        if (mem) {
          this.state.selectedMember = mem;
          this.state.isMemberSelectorOpen = false;
          await this.recalculatePricing();
          this.render();
        }
        return;
      }

      // 10. Open / Close Tabs Drawer
      if (e.target.closest(".cc-action-open-tabs")) {
        this.state.isOpenTabsOpen = true;
        this.render();
        return;
      }

      if (e.target.closest(".cc-action-close-tabs") || e.target.id === "opentabs-modal-backdrop") {
        this.state.isOpenTabsOpen = false;
        this.render();
        return;
      }

      const pickTabBtn = e.target.closest(".cc-action-pick-tab");
      if (pickTabBtn) {
        const tId = Number(pickTabBtn.dataset.tableId);
        const table = this.state.tables.find((t) => t.id === tId);
        if (table) {
          this.state.currentTable = table;
          this.state.isOpenTabsOpen = false;
          this.state.currentView = "pos";
          this.state.cart = [
            { product: POS_PRODUCTS[1], qty: 1 },
            { product: POS_PRODUCTS[8], qty: 1 },
          ];
          await this.recalculatePricing();
          this.render();
        }
        return;
      }

      // 11. Keep Tab Open
      if (e.target.closest(".cc-action-save-tab")) {
        if (this.state.cart.length === 0) {
          this.state.error = "Cannot save an empty tab.";
          this.render();
          return;
        }
        if (this.state.currentTable) {
          this.state.currentTable.status = "occupied";
          this.state.currentTable.active_order = {
            order_ref: `POS-${10120 + Math.floor(Math.random() * 80)}`,
            amount: this.state.pricing.total,
            items_count: this.state.cart.reduce((s, i) => s + i.qty, 0),
            member_name: this.state.selectedMember.name,
          };
          alert(`Tab saved for ${this.state.currentTable.name}.\nRef: ${this.state.currentTable.active_order.order_ref}`);
          this.render();
        }
        return;
      }

      // 12. Open / Close Shift
      if (e.target.closest(".cc-action-open-shift")) {
        this.state.isShiftModalOpen = true;
        this.render();
        return;
      }

      if (e.target.closest(".cc-action-close-shift") || e.target.id === "shift-modal-backdrop") {
        this.state.isShiftModalOpen = false;
        this.render();
        return;
      }

      if (e.target.closest(".cc-action-do-close-shift")) {
        alert(`Shift for ${this.state.shiftData.staff_name} closed successfully in Odoo POS.\nZ-Report generated: Total Sales ${this.state.shiftData.formatted_total}`);
        this.state.isShiftModalOpen = false;
        this.render();
        return;
      }

      // 13. Payment Modal
      if (e.target.closest(".cc-action-open-payment")) {
        if (this.state.cart.length === 0) return;
        this.state.isPaymentModalOpen = true;
        this.state.error = null;
        this.render();
        return;
      }

      if (e.target.closest(".cc-action-close-payment") || e.target.id === "payment-modal-backdrop") {
        if (!this.state.isProcessingPayment) {
          this.state.isPaymentModalOpen = false;
          this.render();
        }
        return;
      }

      const methodBtn = e.target.closest(".cc-pay-method-btn");
      if (methodBtn) {
        this.state.paymentMethod = methodBtn.dataset.method;
        this.render();
        return;
      }

      // 14. Confirm Payment Action
      if (e.target.closest(".cc-action-confirm-pay")) {
        await this.handlePayment();
        return;
      }

      // 15. Success Actions
      if (e.target.closest(".cc-action-new-order") || e.target.id === "success-modal-backdrop") {
        this.state.isSuccessOpen = false;
        this.state.lastPaymentResult = null;
        this.state.cart = [];
        await this.recalculatePricing();
        this.render();
        return;
      }

      if (e.target.closest(".cc-action-view-receipt")) {
        alert(
          `[Odoo Thermal POS Receipt]\n\nCHAMPIONS CLUB BAR & CAFETERIA\nOrder: ${this.state.lastPaymentResult?.order_ref}\nTable: ${this.state.lastPaymentResult?.table_name}\nCustomer: ${this.state.lastPaymentResult?.member_name}\nTotal: ${this.state.lastPaymentResult?.amount}\nTendered: ${this.state.lastPaymentResult?.payment_method}\n\n✓ Transaction settled in Odoo POS Register.`
        );
        return;
      }

      // 16. Dismiss Error
      if (e.target.closest(".cc-action-dismiss-error")) {
        this.state.error = null;
        this.render();
        return;
      }
    });

    // Handle Input for Search
    this.root.addEventListener("input", (e) => {
      if (e.target.id === "pos-search-input") {
        this.state.searchQuery = e.target.value;
        clearTimeout(this.searchTimer);
        this.searchTimer = setTimeout(() => {
          this.render();
        }, 160);
      }
    });
  }

  async handlePayment() {
    if (this.state.isProcessingPayment) return;
    this.state.isProcessingPayment = true;
    this.render();

    // Simulation delay
    await new Promise((r) => setTimeout(r, 600));

    const result = await PosService.processPayment({
      table_name: this.state.currentTable.name,
      member_name: this.state.selectedMember.name,
      payment_method: this.state.paymentMethod,
      items: this.state.cart,
      pricing: this.state.pricing,
    });

    if (result.success) {
      // Free table
      if (this.state.currentTable) {
        this.state.currentTable.status = "available";
        this.state.currentTable.active_order = null;
      }

      // Add to log
      this.state.orderHistory.unshift({
        order_ref: result.order_ref,
        table: result.table_name,
        member: result.member_name,
        amount: result.amount,
        method: result.payment_method,
        status: "Paid",
        time: "Just now",
      });

      this.state.lastPaymentResult = result;
      this.state.isPaymentModalOpen = false;
      this.state.isSuccessOpen = true;
      this.state.cart = [];
      await this.recalculatePricing();
    } else {
      this.state.error = result.message || "Payment processing failed.";
    }

    this.state.isProcessingPayment = false;
    this.render();
  }
}

window.BarPOSController = BarPOSController;

// Global initialization
document.addEventListener("DOMContentLoaded", () => {
  const mountPoint = document.getElementById("pos-app-root");
  if (mountPoint) {
    window.posApp = new BarPOSController(mountPoint);
  }
});
