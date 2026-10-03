/**
 * Champions Club — Sports Club Management System
 * Bar + Cafeteria POS Service Layer (Simulating Odoo 19 Backend RPC)
 *
 * Models:
 * - club.pos.table
 * - club.pos.product
 * - club.pos.order / club.pos.order.line
 * - club.pos.session
 */

const POS_TABLES = [
  { id: 1, name: "Table 01", capacity: 4, status: "occupied", active_order: { order_ref: "POS-00121", amount: 420, items_count: 3, member_name: "Aarav Patel" } },
  { id: 2, name: "Table 02", capacity: 2, status: "available", active_order: null },
  { id: 3, name: "Table 03", capacity: 4, status: "occupied", active_order: { order_ref: "POS-00123", amount: 780, items_count: 5, member_name: "Chitt Hirpara" } },
  { id: 4, name: "Table 04", capacity: 6, status: "available", active_order: null },
  { id: 5, name: "Table 05", capacity: 4, status: "occupied", active_order: { order_ref: "POS-00124", amount: 250, items_count: 2, member_name: "Rohan Shah" } },
  { id: 6, name: "Table 06", capacity: 2, status: "available", active_order: null },
  { id: 7, name: "Bar Counter 01", capacity: 1, status: "available", active_order: null },
  { id: 8, name: "Lounge 01", capacity: 8, status: "available", active_order: null },
];

const POS_CATEGORIES = [
  { id: "all", label: "All Items", icon: "🍽️" },
  { id: "drinks", label: "Drinks", icon: "🍹" },
  { id: "food", label: "Food", icon: "🥗" },
  { id: "snacks", label: "Snacks", icon: "🍿" },
  { id: "coffee", label: "Coffee & Tea", icon: "☕" },
  { id: "shakes", label: "Protein & Shakes", icon: "🥤" },
];

const POS_PRODUCTS = [
  { id: 1, name: "Espresso Single Origin", category: "coffee", category_label: "Coffee & Tea", price: 80, stock: 40, image_icon: "☕", is_available: true },
  { id: 2, name: "Artisanal Cappuccino", category: "coffee", category_label: "Coffee & Tea", price: 140, stock: 35, image_icon: "☕", is_available: true },
  { id: 3, name: "Cold Brew Nitro", category: "coffee", category_label: "Coffee & Tea", price: 160, stock: 20, image_icon: "🧊", is_available: true },
  { id: 4, name: "Whey Gold Recovery Shake", category: "shakes", category_label: "Protein & Shakes", price: 220, stock: 18, image_icon: "🥤", is_available: true },
  { id: 5, name: "Plant Berry Antioxidant Smoothie", category: "shakes", category_label: "Protein & Shakes", price: 240, stock: 15, image_icon: "🫐", is_available: true },
  { id: 6, name: "Hydration Electrolyte Coconut Water", category: "drinks", category_label: "Drinks", price: 90, stock: 50, image_icon: "🥥", is_available: true },
  { id: 7, name: "Fresh Orange & Mint Juice", category: "drinks", category_label: "Drinks", price: 130, stock: 25, image_icon: "🍊", is_available: true },
  { id: 8, name: "Sparkling Mineral Water (500ml)", category: "drinks", category_label: "Drinks", price: 60, stock: 60, image_icon: "💧", is_available: true },
  { id: 9, name: "Clubhouse Grilled Chicken Wrap", category: "food", category_label: "Food", price: 210, stock: 14, image_icon: "🌯", is_available: true },
  { id: 10, name: "Avocado & Sourdough Toast", category: "food", category_label: "Food", price: 190, stock: 12, image_icon: "🥑", is_available: true },
  { id: 11, name: "Mediterranean Quinoa Power Bowl", category: "food", category_label: "Food", price: 260, stock: 10, image_icon: "🥗", is_available: true },
  { id: 12, name: "Champions Classic Smash Burger", category: "food", category_label: "Food", price: 250, stock: 16, image_icon: "🍔", is_available: true },
  { id: 13, name: "Raw Whey Protein Bar (Salted Caramel)", category: "snacks", category_label: "Snacks", price: 110, stock: 45, image_icon: "🍫", is_available: true },
  { id: 14, name: "Roasted Almond & Cranberry Mix", category: "snacks", category_label: "Snacks", price: 120, stock: 30, image_icon: "🥜", is_available: true },
  { id: 15, name: "Baked Sweet Potato Crisps", category: "snacks", category_label: "Snacks", price: 95, stock: 0, image_icon: "🍠", is_available: false },
];

const POS_MEMBERS = [
  { id: 101, name: "Chitt Hirpara", plan: "Gold", planCode: "gold", discountPct: 15 },
  { id: 102, name: "Aarav Patel", plan: "Silver", planCode: "silver", discountPct: 10 },
  { id: 103, name: "Rohan Shah", plan: "Junior", planCode: "junior", discountPct: 5 },
  { id: 0, name: "Walk-in Guest", plan: "Guest", planCode: "none", discountPct: 0 },
];

const POS_SHIFT_INITIAL = {
  session_id: "SESH-2026-004",
  staff_name: "Rahul Verma",
  start_time: "Today, 08:30 AM",
  orders_count: 42,
  cash_sales: 8500,
  card_sales: 6200,
  upi_sales: 7800,
  total_sales: 22500,
  formatted_cash: "₹8,500",
  formatted_card: "₹6,200",
  formatted_upi: "₹7,800",
  formatted_total: "₹22,500",
  state: "open"
};

const POS_ORDERS_LOG = [
  { order_ref: "POS-00124", table: "Table 05", member: "Rohan Shah", amount: "₹250.00", method: "CASH", status: "Paid", time: "10:14 AM" },
  { order_ref: "POS-00123", table: "Table 03", member: "Chitt Hirpara", amount: "₹780.00", method: "UPI", status: "Paid", time: "09:48 AM" },
  { order_ref: "POS-00122", table: "Bar 01", member: "Walk-in Guest", amount: "₹180.00", method: "CARD", status: "Paid", time: "09:20 AM" },
  { order_ref: "POS-00121", table: "Table 01", member: "Aarav Patel", amount: "₹420.00", method: "UPI", status: "Paid", time: "08:55 AM" },
];

/**
 * POS Service Layer (Simulating Odoo 19 Bar & POS RPC)
 */
const PosService = {
  async getTables() {
    return JSON.parse(JSON.stringify(POS_TABLES));
  },

  async getProducts(category = "all", searchQuery = "") {
    return POS_PRODUCTS.filter((p) => {
      const matchCat = category === "all" || p.category === category;
      const matchQuery = !searchQuery || 
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.category.toLowerCase().includes(searchQuery.toLowerCase());
      return matchCat && matchQuery;
    });
  },

  /**
   * Source of truth discount calculation (simulating backend RPC)
   */
  async calculateOrderPricing(cartItems, memberPlanCode = "none") {
    let subtotal = 0;
    for (const item of cartItems) {
      subtotal += item.product.price * item.qty;
    }

    let discountPct = 0;
    let discountLabel = "No Discount";
    if (memberPlanCode === "gold") {
      discountPct = 15;
      discountLabel = "Gold Member Discount (15%)";
    } else if (memberPlanCode === "silver") {
      discountPct = 10;
      discountLabel = "Silver Member Discount (10%)";
    } else if (memberPlanCode === "junior") {
      discountPct = 5;
      discountLabel = "Junior Member Discount (5%)";
    }

    const discountAmount = Math.round((subtotal * discountPct) / 100);
    const total = Math.max(0, subtotal - discountAmount);

    return {
      subtotal,
      formatted_subtotal: `₹${subtotal.toLocaleString("en-IN")}.00`,
      discount_amount: discountAmount,
      formatted_discount: discountAmount > 0 ? `-₹${discountAmount.toLocaleString("en-IN")}.00` : "₹0.00",
      discount_label: discountLabel,
      discount_pct: discountPct,
      total,
      formatted_total: `₹${total.toLocaleString("en-IN")}.00`
    };
  },

  async processPayment(orderData) {
    // Validate stock
    for (const item of orderData.items) {
      const product = POS_PRODUCTS.find(p => p.id === item.product.id);
      if (!product || product.stock < item.qty) {
        return {
          success: false,
          message: `⚠ Insufficient stock: ${product?.name || "Item"} has only ${product?.stock || 0} left.`
        };
      }
    }

    // Deduct stock
    for (const item of orderData.items) {
      const product = POS_PRODUCTS.find(p => p.id === item.product.id);
      if (product) {
        product.stock = Math.max(0, product.stock - item.qty);
      }
    }

    // Create order ref
    const nextNum = 10125 + Math.floor(Math.random() * 50);
    const orderRef = `POS-${nextNum}`;

    return {
      success: true,
      order_ref: orderRef,
      table_name: orderData.table_name,
      member_name: orderData.member_name,
      payment_method: orderData.payment_method.toUpperCase(),
      amount: orderData.pricing.formatted_total,
      date: new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })
    };
  }
};
