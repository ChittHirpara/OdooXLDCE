/**
 * Champions Club — Sports Club Management System
 * Pro-Shop & Equipment Module Frontend
 *
 * Modular Component Architecture:
 * - ShopPage (Root Coordinator & State Manager)
 * - ShopHeader
 * - CategoryFilter
 * - ProductGrid
 * - ProductCard
 * - ProductDetail (Modal)
 * - QuantitySelector
 * - Cart (Slide-over Drawer)
 * - CartItem
 * - CheckoutPage
 * - OrderConfirmation
 */

// ==========================================================================
// 1. QuantitySelector Component
// ==========================================================================
const QuantitySelector = {
  render(qty, maxStock, size = "md") {
    const isSm = size === "sm";
    const btnClass = isSm ? "cc-qty-btn-sm" : "cc-qty-btn";
    const valClass = isSm ? "cc-qty-val-sm" : "cc-qty-val";
    const ctrlClass = isSm ? "cc-cart-qty-ctrl" : "cc-qty-selector";

    return `
      <div class="${ctrlClass}">
        <button type="button" class="${btnClass} cc-qty-dec" ${qty <= 1 ? "disabled" : ""}>−</button>
        <span class="${valClass}">${qty}</span>
        <button type="button" class="${btnClass} cc-qty-inc" ${qty >= maxStock ? "disabled" : ""}>+</button>
      </div>
    `;
  }
};

// ==========================================================================
// 2. ProductCard Component
// ==========================================================================
const ProductCard = {
  render(product, memberDiscountPct = 20) {
    const isOutOfStock = product.stock <= 0;
    const memberPrice = Math.round(product.price * (1 - memberDiscountPct / 100));

    // Availability Badge: Clear visual and text indicators (never color-alone)
    const stockBadge = isOutOfStock
      ? `<span class="cc-stock-badge out-stock" title="Currently unavailable in inventory"><span class="cc-dot-red"></span>🔴 Out of Stock</span>`
      : `<span class="cc-stock-badge in-stock" title="${product.stock} units in stock"><span class="cc-dot"></span>🟢 ${product.stock} available</span>`;

    const buttonHtml = isOutOfStock
      ? `<button type="button" class="cc-btn-add-card disabled" disabled>Unavailable</button>`
      : `<button type="button" class="cc-btn-add-card cc-action-quick-add" data-product-id="${product.id}">Add to Cart</button>`;

    return `
      <div class="cc-product-card" data-product-id="${product.id}">
        <div class="cc-card-img-wrap">
          ${stockBadge}
          <div class="cc-product-emoji-icon">${product.image_icon || "🎾"}</div>
        </div>
        <div class="cc-card-body">
          <span class="cc-card-cat">${product.category_label || product.category}</span>
          <h3 class="cc-card-title">${product.name}</h3>
          <div class="cc-card-price-row">
            <div class="cc-card-pricing">
              <span class="cc-price-main">₹${product.price.toLocaleString("en-IN")}</span>
              <span class="cc-member-price-sub">Gold: ₹${memberPrice.toLocaleString("en-IN")}</span>
            </div>
            ${buttonHtml}
          </div>
        </div>
      </div>
    `;
  }
};

// ==========================================================================
// 3. ProductGrid Component
// ==========================================================================
const ProductGrid = {
  render(products, isLoading, memberDiscountPct = 20) {
    if (isLoading) {
      return `
        <div class="cc-skeleton-grid">
          <div class="cc-skeleton-card"></div>
          <div class="cc-skeleton-card"></div>
          <div class="cc-skeleton-card"></div>
          <div class="cc-skeleton-card"></div>
        </div>
      `;
    }

    if (!products || products.length === 0) {
      return `
        <div class="cc-cart-empty" style="grid-column: 1 / -1; padding: 5rem 2rem;">
          <span class="cc-empty-icon">🔍</span>
          <h4>No Products Found</h4>
          <p>We couldn't find any tournament gear matching your search or filters.</p>
          <button type="button" class="cc-btn-secondary cc-action-reset-filters">Reset All Filters</button>
        </div>
      `;
    }

    const cardsHtml = products
      .map((p) => ProductCard.render(p, memberDiscountPct))
      .join("");

    return `
      <div class="cc-product-grid">
        ${cardsHtml}
      </div>
    `;
  }
};

// ==========================================================================
// 4. CategoryFilter Component
// ==========================================================================
const CategoryFilter = {
  render(categories, selectedCategory, inStockOnly, totalCount) {
    const pillsHtml = categories
      .map((cat) => {
        const isActive = cat.id === selectedCategory ? "active" : "";
        return `
          <button type="button" class="cc-cat-pill ${isActive}" data-cat-id="${cat.id}">
            ${cat.label}
          </button>
        `;
      })
      .join("");

    return `
      <div class="cc-filter-bar">
        <div class="cc-category-pills">
          ${pillsHtml}
        </div>
        <div class="cc-stock-filter">
          <label class="cc-toggle-label">
            <input type="checkbox" id="in-stock-checkbox" ${inStockOnly ? "checked" : ""} />
            <span>In Stock Only</span>
          </label>
          <span style="font-size: 0.8rem; color: var(--cc-text-muted); margin-left: 0.85rem;">
            Showing ${totalCount} items
          </span>
        </div>
      </div>
    `;
  }
};

// ==========================================================================
// 5. ProductDetail Modal Component
// ==========================================================================
const ProductDetail = {
  render(product, quantity, isOpen, memberDiscountPct = 20) {
    if (!isOpen || !product) {
      return `<div class="cc-modal-backdrop" id="product-detail-backdrop"></div>`;
    }

    const isOutOfStock = product.stock <= 0;
    const memberPrice = Math.round(product.price * (1 - memberDiscountPct / 100));

    const stockBadge = isOutOfStock
      ? `<span class="cc-stock-badge out-stock"><span class="cc-dot-red"></span>🔴 Out of Stock</span>`
      : `<span class="cc-stock-badge in-stock"><span class="cc-dot"></span>🟢 ${product.stock} available</span>`;

    const addButtonHtml = isOutOfStock
      ? `<button type="button" class="cc-btn-primary cc-btn-add-detail disabled" disabled style="opacity: 0.5; cursor: not-allowed;">Unavailable</button>`
      : `<button type="button" class="cc-btn-primary cc-btn-add-detail cc-action-modal-add" data-product-id="${product.id}">Add to Cart</button>`;

    return `
      <div class="cc-modal-backdrop active" id="product-detail-backdrop">
        <div class="cc-modal-dialog cc-product-detail-dialog">
          <button type="button" class="cc-modal-close-btn cc-action-close-detail" aria-label="Close modal">✕</button>
          
          <div style="padding: 2rem;">
            <div class="cc-detail-layout">
              <div class="cc-detail-img-box">
                <span class="cc-detail-large-icon">${product.image_icon || "🎾"}</span>
              </div>
              <div class="cc-detail-info-box">
                <span class="cc-card-cat">${product.category_label || product.category}</span>
                <h2 class="cc-detail-title">${product.name}</h2>
                
                <div class="cc-detail-pricing">
                  <span class="cc-detail-price">₹${product.price.toLocaleString("en-IN")}</span>
                  <span class="cc-member-badge">Gold Member: ₹${memberPrice.toLocaleString("en-IN")} (20% off)</span>
                </div>

                <div class="cc-detail-stock-row">
                  ${stockBadge}
                </div>

                <p class="cc-detail-description">${product.description}</p>

                <div class="cc-qty-action-row">
                  ${QuantitySelector.render(quantity, product.stock, "md")}
                  ${addButtonHtml}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  }
};

// ==========================================================================
// 6. CartItem Component
// ==========================================================================
const CartItem = {
  render(item) {
    const { product, qty } = item;
    const itemSubtotal = product.price * qty;

    return `
      <div class="cc-cart-item-row" data-product-id="${product.id}">
        <div class="cc-item-icon">
          ${product.image_icon || "🎾"}
        </div>
        <div class="cc-item-info">
          <h4 class="cc-item-name">${product.name}</h4>
          <span class="cc-item-price">₹${product.price.toLocaleString("en-IN")} × ${qty}</span>
          <div style="margin-top: 0.4rem;">
            ${QuantitySelector.render(qty, product.stock, "sm")}
          </div>
        </div>
        <div class="cc-item-right">
          <span class="cc-item-subtotal">₹${itemSubtotal.toLocaleString("en-IN")}</span>
          <button type="button" class="cc-item-remove cc-action-remove-item" data-product-id="${product.id}" title="Remove item">
            🗑️
          </button>
        </div>
      </div>
    `;
  }
};

// ==========================================================================
// 7. Cart Drawer Component
// ==========================================================================
const Cart = {
  render(cartItems, pricing, isOpen) {
    const totalCount = cartItems.reduce((acc, i) => acc + i.qty, 0);

    let contentHtml = "";
    let footerHtml = "";

    if (!cartItems || cartItems.length === 0) {
      contentHtml = `
        <div class="cc-cart-empty">
          <span class="cc-empty-icon">🛍️</span>
          <h4>Your Cart is Empty</h4>
          <p>Explore our premium tournament equipment, rackets, and apparel.</p>
          <button type="button" class="cc-btn-secondary cc-action-close-cart">Continue Shopping</button>
        </div>
      `;
    } else {
      const itemsListHtml = cartItems.map((item) => CartItem.render(item)).join("");
      contentHtml = `
        <div class="cc-cart-items-list">
          ${itemsListHtml}
        </div>
      `;

      footerHtml = `
        <div class="cc-drawer-footer">
          <div class="cc-drawer-price-row">
            <span>Subtotal</span>
            <span>${pricing.formattedSubtotal}</span>
          </div>
          <div class="cc-drawer-price-row discount">
            <span>${pricing.discountLabel}</span>
            <span class="cc-discount-text">${pricing.formattedDiscount}</span>
          </div>
          <div class="cc-drawer-price-row total">
            <span>Estimated Total</span>
            <span class="cc-total-amount">${pricing.formattedTotal}</span>
          </div>
          <div class="cc-drawer-actions">
            <button type="button" class="cc-btn-secondary cc-action-close-cart">Continue Shopping</button>
            <button type="button" class="cc-btn-primary cc-action-checkout">Proceed to Checkout</button>
          </div>
        </div>
      `;
    }

    return `
      <div class="cc-drawer-backdrop ${isOpen ? "active" : ""}" id="cart-drawer-backdrop">
        <div class="cc-cart-drawer">
          <div class="cc-drawer-header">
            <h3 class="cc-drawer-title">Shopping Cart (${totalCount})</h3>
            <button type="button" class="cc-drawer-close cc-action-close-cart" aria-label="Close cart">✕</button>
          </div>
          ${contentHtml}
          ${footerHtml}
        </div>
      </div>
    `;
  }
};

// ==========================================================================
// 8. CheckoutPage Component
// ==========================================================================
const CheckoutPage = {
  render(cartItems, pricing, member, fulfillment, deliveryAddress, paymentMethod) {
    const itemsListHtml = cartItems
      .map(
        (item) => `
        <div class="cc-summary-item-row">
          <div class="cc-sum-item-left">
            <span class="cc-sum-item-name">${item.product.name}</span>
            <span class="cc-sum-item-qty">Qty: ${item.qty} × ₹${item.product.price.toLocaleString("en-IN")}</span>
          </div>
          <span class="cc-sum-item-total">₹${(item.product.price * item.qty).toLocaleString("en-IN")}</span>
        </div>
      `
      )
      .join("");

    return `
      <div class="cc-checkout-page" style="padding-top: 1rem;">
        <div style="margin-bottom: 1.5rem;">
          <button type="button" class="cc-btn-secondary cc-action-return-catalog" style="padding: 0.35rem 0.75rem; font-size: 0.82rem;">
            ← Return to Pro-Shop
          </button>
        </div>

        <div class="cc-checkout-layout">
          <!-- Left Column: Checkout Options -->
          <div class="cc-checkout-main">
            <!-- 1. Customer Section -->
            <div class="cc-checkout-section">
              <h3 class="cc-section-title">1. Customer & Membership</h3>
              <div class="cc-member-card-box">
                <div class="cc-m-avatar">CH</div>
                <div style="flex-grow: 1;">
                  <h4 class="cc-m-name">${member.name}</h4>
                  <span class="cc-m-plan">🏆 ${member.plan} Tier Active (20% Pro-Shop Discount Applied)</span>
                </div>
                <span class="cc-member-badge">Verified Member</span>
              </div>
            </div>

            <!-- 2. Fulfillment Section -->
            <div class="cc-checkout-section">
              <h3 class="cc-section-title">2. Fulfillment Method</h3>
              <div class="cc-fulfillment-options">
                <label class="cc-fulfillment-card ${fulfillment === "club_pickup" ? "selected" : ""}">
                  <input type="radio" name="fulfillment" value="club_pickup" ${fulfillment === "club_pickup" ? "checked" : ""} />
                  <div>
                    <span class="cc-f-title">Collect at Club</span>
                    <p class="cc-f-desc">Pick up at Clubhouse Front Desk. Complimentary & immediate.</p>
                  </div>
                </label>

                <label class="cc-fulfillment-card ${fulfillment === "home_delivery" ? "selected" : ""}">
                  <input type="radio" name="fulfillment" value="home_delivery" ${fulfillment === "home_delivery" ? "checked" : ""} />
                  <div>
                    <span class="cc-f-title">Home Delivery</span>
                    <p class="cc-f-desc">Tracked courier delivery to your registered residence.</p>
                  </div>
                </label>
              </div>

              <div class="cc-delivery-address-box" style="${fulfillment === "home_delivery" ? "display: block;" : "display: none;"}">
                <label for="delivery-address-input">Delivery Address</label>
                <textarea id="delivery-address-input" class="cc-address-input" placeholder="Enter your full street address, apartment, city, and pincode...">${deliveryAddress}</textarea>
              </div>
            </div>

            <!-- 3. Payment Section -->
            <div class="cc-checkout-section">
              <h3 class="cc-section-title">3. Payment Method</h3>
              <div class="cc-payment-methods">
                <label class="cc-payment-radio ${paymentMethod === "member_account" ? "selected" : ""}">
                  <input type="radio" name="payment_method" value="member_account" ${paymentMethod === "member_account" ? "checked" : ""} />
                  <div>
                    <strong style="color: #FFFFFF;">Member Club Account</strong>
                    <div style="font-size: 0.76rem; color: var(--cc-text-secondary);">Directly settle via your monthly membership folio</div>
                  </div>
                </label>

                <label class="cc-payment-radio ${paymentMethod === "upi_card" ? "selected" : ""}">
                  <input type="radio" name="payment_method" value="upi_card" ${paymentMethod === "upi_card" ? "checked" : ""} />
                  <div>
                    <strong style="color: #FFFFFF;">UPI / NetBanking / Cards</strong>
                    <div style="font-size: 0.76rem; color: var(--cc-text-secondary);">Odoo Payment Acquirer Gateway (Instant Confirmation)</div>
                  </div>
                </label>
              </div>
            </div>
          </div>

          <!-- Right Column: Order Summary Pane -->
          <div class="cc-checkout-summary-pane">
            <h3 class="cc-summary-title">Order Summary</h3>
            <div class="cc-summary-items-list">
              ${itemsListHtml}
            </div>

            <div class="cc-pricing-breakdown">
              <div class="cc-price-row">
                <span>Subtotal</span>
                <span>${pricing.formattedSubtotal}</span>
              </div>
              <div class="cc-price-row discount-row">
                <span>${pricing.discountLabel}</span>
                <span class="cc-discount-text">${pricing.formattedDiscount}</span>
              </div>
              <div class="cc-price-row">
                <span>Shipping / Collection</span>
                <span class="cc-free-text">FREE</span>
              </div>
              <div class="cc-price-divider"></div>
              <div class="cc-price-row total-row">
                <span>Total Due</span>
                <span class="cc-total-val">${pricing.formattedTotal}</span>
              </div>
            </div>

            <button type="button" class="cc-btn-primary cc-action-place-order" style="width: 100%; padding: 0.85rem; font-size: 0.95rem;">
              Place Order
            </button>
            <div style="text-align: center; margin-top: 0.75rem; font-size: 0.74rem; color: var(--cc-text-muted);">
              🔒 Real-time Odoo Sales & Inventory verification
            </div>
          </div>
        </div>
      </div>
    `;
  }
};

// ==========================================================================
// 9. OrderConfirmation Component
// ==========================================================================
const OrderConfirmation = {
  render(order) {
    if (!order) return "";

    const itemsSummary = order.items
      .map(
        (i) => `
        <div class="cc-conf-row">
          <span>${i.product.name} × ${i.qty}</span>
          <span>₹${(i.product.price * i.qty).toLocaleString("en-IN")}</span>
        </div>
      `
      )
      .join("");

    return `
      <div class="cc-confirmed-screen">
        <div class="cc-confirmed-box">
          <div class="cc-confirmed-icon">✓</div>
          <h2 class="cc-conf-heading">Order Confirmed</h2>
          <p class="cc-conf-num">Order Reference: <strong>${order.orderId}</strong></p>

          <div class="cc-conf-details-card">
            <div class="cc-conf-row">
              <span>Customer:</span>
              <strong>${order.customerName}</strong>
            </div>
            <div class="cc-conf-row">
              <span>Fulfillment:</span>
              <strong>${order.fulfillment}</strong>
            </div>
            <div class="cc-conf-row">
              <span>Location:</span>
              <strong style="max-width: 250px; text-align: right;">${order.deliveryAddress}</strong>
            </div>
            <div class="cc-conf-row">
              <span>Order Date:</span>
              <strong>${order.date}</strong>
            </div>

            <div class="cc-conf-divider"></div>
            <div style="font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--cc-text-muted); margin-bottom: 0.25rem;">
              Ordered Equipment:
            </div>
            ${itemsSummary}

            <div class="cc-conf-divider"></div>
            <div class="cc-conf-row">
              <span>Subtotal:</span>
              <strong>${order.subtotal}</strong>
            </div>
            <div class="cc-conf-row" style="color: var(--cc-accent-gold);">
              <span>Gold Member Discount:</span>
              <strong>${order.discount}</strong>
            </div>
            <div class="cc-conf-row total-row">
              <span>Final Total:</span>
              <strong class="cc-total-highlight">${order.total}</strong>
            </div>
          </div>

          <div style="display: flex; gap: 0.75rem; justify-content: center;">
            <button type="button" class="cc-btn-primary cc-action-return-catalog" style="padding: 0.75rem 1.5rem;">
              Continue Shopping
            </button>
            <button type="button" class="cc-btn-secondary cc-action-view-inventory" style="padding: 0.75rem 1.25rem;">
              View in Odoo Sales
            </button>
          </div>
        </div>
      </div>
    `;
  }
};

// ==========================================================================
// 10. ShopHeader Component
// ==========================================================================
const ShopHeader = {
  render(cartCount, member, searchQuery) {
    return `
      <!-- Top Clean Minimal Navbar -->
      <header class="cc-header">
        <div class="cc-header-inner">
          <a href="#/memberships" class="cc-brand">
            <div class="cc-brand-emblem">🏆</div>
            <h1 class="cc-brand-title">Champions Club</h1>
          </a>

          <nav class="cc-nav" aria-label="Main Navigation">
            <a href="#/memberships" class="cc-nav-link">Memberships</a>
            <a href="#/courts" class="cc-nav-link">Courts</a>
            <a href="#/shop" class="cc-nav-link active">Shop</a>
            <a href="#/pos" class="cc-nav-link">Bar + POS</a>
          </nav>

          <div style="display: flex; align-items: center; gap: 1rem;">
            <!-- Cart Trigger Button -->
            <button type="button" class="cc-cart-trigger-btn cc-action-open-cart" id="btn-open-cart" aria-label="View Shopping Cart">
              <span>🛒 Cart</span>
              <span class="cc-cart-badge" id="cart-badge-count">${cartCount}</span>
            </button>

            <!-- Member Info Mini -->
            <div style="display: flex; align-items: center; gap: 0.65rem; border-left: 1px solid var(--cc-border-card); padding-left: 1rem;">
              <div style="width: 28px; height: 28px; border-radius: 50%; background-color: #1E2738; display: flex; align-items: center; justify-content: center; font-size: 0.72rem; font-weight: 700; color: #FFFFFF;">
                CH
              </div>
              <div style="display: flex; flex-direction: column;">
                <span style="font-size: 0.82rem; font-weight: 600; color: #FFFFFF; line-height: 1.1;">${member.name}</span>
                <span style="font-size: 0.7rem; color: var(--cc-accent-gold); font-weight: 600;">Gold Member (20% Off)</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      <!-- Shop Section Hero Header -->
      <div class="cc-shop-hero">
        <div>
          <h2 style="font-size: 1.6rem; font-weight: 700; color: #FFFFFF; margin: 0 0 0.35rem 0;">
            Champions Club Shop
          </h2>
          <p style="font-size: 0.88rem; color: var(--cc-text-secondary); margin: 0;">
            Official tournament rackets, pressure-tested balls, court shoes, and pro accessories.
          </p>
        </div>

        <div class="cc-search-wrapper">
          <span class="cc-search-icon">🔍</span>
          <input 
            type="text" 
            id="shop-search-input" 
            class="cc-search-input" 
            placeholder="Search products..." 
            value="${searchQuery}" 
            autocomplete="off"
          />
          ${
            searchQuery
              ? `<button type="button" class="cc-search-clear cc-action-clear-search" title="Clear search">✕</button>`
              : ""
          }
        </div>
      </div>
    `;
  }
};

// ==========================================================================
// 11. ShopPage Root Controller
// ==========================================================================
class ShopPageController {
  constructor(rootElement) {
    this.root = rootElement;

    this.state = {
      view: "catalog", // "catalog" | "checkout" | "order_confirmed"
      products: [],
      categories: SHOP_CATEGORIES,
      selectedCategory: "all",
      searchQuery: "",
      inStockOnly: false,

      // Modal state
      selectedProduct: null,
      detailQty: 1,
      isDetailOpen: false,

      // Cart state
      cart: [
        { product: SHOP_CATALOG[0], qty: 1 }, // Default initial sample items
        { product: SHOP_CATALOG[3], qty: 2 },
      ],
      isCartOpen: false,
      pricing: {
        subtotal: 0,
        formattedSubtotal: "₹0",
        discountAmount: 0,
        formattedDiscount: "-₹0",
        discountLabel: "Gold Member Discount (20%)",
        total: 0,
        formattedTotal: "₹0",
      },

      // Checkout form
      fulfillment: "club_pickup", // "club_pickup" | "home_delivery"
      deliveryAddress: "B-402, Shivalik Highstreet, Vastrapur, Ahmedabad - 380015",
      paymentMethod: "member_account",
      confirmedOrder: null,

      // Feedback & loading
      loading: false,
      error: null,
      toast: null,
    };

    this.searchDebounceTimer = null;
    this.init();
  }

  async init() {
    this.bindEvents();
    await this.refreshCatalog();
    await this.updateCartPricing();
    this.render();
  }

  async refreshCatalog() {
    this.state.loading = true;
    this.render();

    try {
      const data = await ShopService.getProducts(
        this.state.selectedCategory,
        this.state.searchQuery
      );
      this.state.products = data;
    } catch (err) {
      this.state.error = "Failed to load product catalog. Please try again.";
    } finally {
      this.state.loading = false;
      this.render();
    }
  }

  async updateCartPricing() {
    const pricing = await ShopService.calculateCartPricing(this.state.cart);
    this.state.pricing = pricing;
  }

  showToast(message) {
    this.state.toast = message;
    this.renderToast();
    setTimeout(() => {
      this.state.toast = null;
      this.renderToast();
    }, 3000);
  }

  renderToast() {
    let container = document.getElementById("cc-toast-box");
    if (!container) {
      container = document.createElement("div");
      container.id = "cc-toast-box";
      container.className = "cc-toast-container";
      document.body.appendChild(container);
    }

    if (this.state.toast) {
      container.innerHTML = `
        <div class="cc-toast">
          <span>✓</span>
          <span>${this.state.toast}</span>
        </div>
      `;
    } else {
      container.innerHTML = "";
    }
  }

  render() {
    const {
      view,
      products,
      categories,
      selectedCategory,
      searchQuery,
      inStockOnly,
      selectedProduct,
      detailQty,
      isDetailOpen,
      cart,
      isCartOpen,
      pricing,
      fulfillment,
      deliveryAddress,
      paymentMethod,
      confirmedOrder,
      loading,
      error,
    } = this.state;

    const filtered = products.filter((p) => {
      if (inStockOnly && p.stock <= 0) return false;
      return true;
    });

    const cartCount = cart.reduce((acc, i) => acc + i.qty, 0);

    let errorBanner = "";
    if (error) {
      errorBanner = `
        <div class="cc-alert-banner">
          <span>${error}</span>
          <button type="button" class="cc-alert-close cc-action-dismiss-error">✕</button>
        </div>
      `;
    }

    let mainContent = "";

    if (view === "checkout") {
      mainContent = `
        ${ShopHeader.render(cartCount, SHOP_MEMBER, searchQuery)}
        ${errorBanner}
        ${CheckoutPage.render(cart, pricing, SHOP_MEMBER, fulfillment, deliveryAddress, paymentMethod)}
      `;
    } else if (view === "order_confirmed") {
      mainContent = `
        ${ShopHeader.render(0, SHOP_MEMBER, "")}
        ${OrderConfirmation.render(confirmedOrder)}
      `;
    } else {
      // Default: Catalog View
      mainContent = `
        ${ShopHeader.render(cartCount, SHOP_MEMBER, searchQuery)}
        ${errorBanner}
        ${CategoryFilter.render(categories, selectedCategory, inStockOnly, filtered.length)}
        ${ProductGrid.render(filtered, loading, SHOP_MEMBER.discountPct)}
      `;
    }

    // Modal & Drawer overlays
    const modalHtml = ProductDetail.render(
      selectedProduct,
      detailQty,
      isDetailOpen,
      SHOP_MEMBER.discountPct
    );
    const cartHtml = Cart.render(cart, pricing, isCartOpen);

    this.root.innerHTML = `
      <main class="cc-page-container" style="max-width: 1200px; margin: 0 auto; padding: 1.5rem;">
        ${mainContent}
      </main>
      ${modalHtml}
      ${cartHtml}
    `;

    // Maintain focus on search input if active
    const searchInput = document.getElementById("shop-search-input");
    if (searchInput && document.activeElement?.id === "shop-search-input") {
      searchInput.focus();
      searchInput.setSelectionRange(searchInput.value.length, searchInput.value.length);
    }
  }

  bindEvents() {
    this.root.addEventListener("click", async (e) => {
      // 1. Category Filter Pill Click
      const catPill = e.target.closest(".cc-cat-pill");
      if (catPill) {
        const catId = catPill.dataset.catId;
        if (catId) {
          this.state.selectedCategory = catId;
          this.state.error = null;
          await this.refreshCatalog();
        }
        return;
      }

      // 2. Clear Search
      if (e.target.closest(".cc-action-clear-search")) {
        this.state.searchQuery = "";
        await this.refreshCatalog();
        return;
      }

      // 3. Reset Filters
      if (e.target.closest(".cc-action-reset-filters")) {
        this.state.selectedCategory = "all";
        this.state.searchQuery = "";
        this.state.inStockOnly = false;
        await this.refreshCatalog();
        return;
      }

      // 4. Dismiss Error
      if (e.target.closest(".cc-action-dismiss-error")) {
        this.state.error = null;
        this.render();
        return;
      }

      // 5. Open Cart Drawer
      if (e.target.closest(".cc-action-open-cart")) {
        this.state.isCartOpen = true;
        this.state.error = null;
        this.render();
        return;
      }

      // 6. Close Cart Drawer
      if (
        e.target.closest(".cc-action-close-cart") ||
        e.target.id === "cart-drawer-backdrop"
      ) {
        this.state.isCartOpen = false;
        this.render();
        return;
      }

      // 7. Quick Add to Cart from Card
      const quickAddBtn = e.target.closest(".cc-action-quick-add");
      if (quickAddBtn) {
        e.stopPropagation();
        const pId = Number(quickAddBtn.dataset.productId);
        const product = await ShopService.getProductById(pId);
        if (product) {
          this.addToCart(product, 1);
        }
        return;
      }

      // 8. Open Product Detail Modal (Click anywhere on card)
      const productCard = e.target.closest(".cc-product-card");
      if (productCard && !e.target.closest("button")) {
        const pId = Number(productCard.dataset.productId);
        const product = await ShopService.getProductById(pId);
        if (product) {
          this.state.selectedProduct = product;
          this.state.detailQty = 1;
          this.state.isDetailOpen = true;
          this.state.error = null;
          this.render();
        }
        return;
      }

      // 9. Close Product Detail Modal
      if (
        e.target.closest(".cc-action-close-detail") ||
        e.target.id === "product-detail-backdrop"
      ) {
        this.state.isDetailOpen = false;
        this.state.selectedProduct = null;
        this.render();
        return;
      }

      // 10. Modal Quantity Increment / Decrement
      if (e.target.closest(".cc-product-detail-dialog .cc-qty-inc")) {
        if (!this.state.selectedProduct) return;
        if (this.state.detailQty >= this.state.selectedProduct.stock) {
          this.state.error = `⚠ Only ${this.state.selectedProduct.stock} units are available.`;
          this.render();
          return;
        }
        this.state.detailQty += 1;
        this.state.error = null;
        this.render();
        return;
      }

      if (e.target.closest(".cc-product-detail-dialog .cc-qty-dec")) {
        if (this.state.detailQty > 1) {
          this.state.detailQty -= 1;
          this.state.error = null;
          this.render();
        }
        return;
      }

      // 11. Modal Add to Cart
      if (e.target.closest(".cc-action-modal-add")) {
        if (this.state.selectedProduct) {
          this.addToCart(this.state.selectedProduct, this.state.detailQty);
          this.state.isDetailOpen = false;
          this.state.selectedProduct = null;
        }
        return;
      }

      // 12. Cart Item Quantity Controls
      const cartItemRow = e.target.closest(".cc-cart-item-row");
      if (cartItemRow) {
        const pId = Number(cartItemRow.dataset.productId);
        const item = this.state.cart.find((i) => i.product.id === pId);

        if (e.target.closest(".cc-qty-inc") && item) {
          if (item.qty + 1 > item.product.stock) {
            this.state.error = `⚠ Only ${item.product.stock} units are available.`;
            this.render();
            return;
          }
          item.qty += 1;
          this.state.error = null;
          await this.updateCartPricing();
          this.render();
          return;
        }

        if (e.target.closest(".cc-qty-dec") && item) {
          if (item.qty > 1) {
            item.qty -= 1;
            this.state.error = null;
            await this.updateCartPricing();
            this.render();
          } else {
            this.removeFromCart(pId);
          }
          return;
        }

        if (e.target.closest(".cc-action-remove-item")) {
          this.removeFromCart(pId);
          return;
        }
      }

      // 13. Proceed to Checkout
      if (e.target.closest(".cc-action-checkout")) {
        if (this.state.cart.length === 0) return;
        this.state.isCartOpen = false;
        this.state.view = "checkout";
        this.state.error = null;
        this.render();
        return;
      }

      // 14. Return to Catalog
      if (e.target.closest(".cc-action-return-catalog")) {
        this.state.view = "catalog";
        this.state.error = null;
        await this.refreshCatalog();
        return;
      }

      // 15. Place Order Action
      if (e.target.closest(".cc-action-place-order")) {
        await this.handlePlaceOrder();
        return;
      }

      // 16. View in Odoo Sales
      if (e.target.closest(".cc-action-view-inventory")) {
        alert(
          `[Odoo 19 Sales & Inventory]\n\nOrder ${this.state.confirmedOrder?.orderId || "SC-1024"} recorded in PostgreSQL database.\nWarehouse: Champions Club Pro-Shop (WH/STOCK).\nStock ledger updated successfully.`
        );
      }
    });

    // Handle Input & Changes
    this.root.addEventListener("input", (e) => {
      // Search Input Debouncing
      if (e.target.id === "shop-search-input") {
        const query = e.target.value;
        this.state.searchQuery = query;

        clearTimeout(this.searchDebounceTimer);
        this.searchDebounceTimer = setTimeout(async () => {
          await this.refreshCatalog();
        }, 180);
      }

      // Delivery Address Input
      if (e.target.id === "delivery-address-input") {
        this.state.deliveryAddress = e.target.value;
      }
    });

    this.root.addEventListener("change", (e) => {
      // In-stock only checkbox
      if (e.target.id === "in-stock-checkbox") {
        this.state.inStockOnly = e.target.checked;
        this.render();
      }

      // Fulfillment Radio
      if (e.target.name === "fulfillment") {
        this.state.fulfillment = e.target.value;
        this.render();
      }

      // Payment Method Radio
      if (e.target.name === "payment_method") {
        this.state.paymentMethod = e.target.value;
        this.render();
      }
    });
  }

  async addToCart(product, qty = 1) {
    if (product.stock <= 0) {
      this.state.error = "⚠ This product is currently out of stock.";
      this.render();
      return;
    }

    const existing = this.state.cart.find((i) => i.product.id === product.id);
    const currentQtyInCart = existing ? existing.qty : 0;

    if (currentQtyInCart + qty > product.stock) {
      this.state.error = `⚠ Only ${product.stock} units are available.`;
      this.render();
      return;
    }

    if (existing) {
      existing.qty += qty;
    } else {
      this.state.cart.push({ product, qty });
    }

    await this.updateCartPricing();
    this.showToast(`Added ${product.name} to cart`);
    this.state.isCartOpen = true;
    this.state.error = null;
    this.render();
  }

  async removeFromCart(productId) {
    this.state.cart = this.state.cart.filter((i) => i.product.id !== productId);
    await this.updateCartPricing();
    this.render();
  }

  async handlePlaceOrder() {
    this.state.loading = true;
    this.render();

    try {
      const result = await ShopService.placeOrder(
        this.state.cart,
        this.state.fulfillment,
        this.state.deliveryAddress
      );

      if (!result.success) {
        this.state.loading = false;
        this.state.error = result.message || "⚠ Stock availability changed. Please review your cart.";
        this.render();
        return;
      }

      // Successful order creation
      this.state.confirmedOrder = result.order;
      this.state.cart = []; // Empty cart
      await this.updateCartPricing();
      this.state.view = "order_confirmed";
      this.state.loading = false;
      this.state.error = null;
      this.render();
    } catch (err) {
      this.state.loading = false;
      this.state.error = "Something went wrong. Please try again.";
      this.render();
    }
  }
}

window.ShopPageController = ShopPageController;

// Global initialization
document.addEventListener("DOMContentLoaded", () => {
  const mountPoint = document.getElementById("shop-app-root");
  if (mountPoint) {
    window.shopPageApp = new ShopPageController(mountPoint);
  }
});
