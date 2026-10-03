/**
 * Champions Club — Sports Club Management System
 * Pro-Shop & Inventory Service Layer (Simulating Odoo 19 Backend RPC)
 *
 * Models:
 * - club.shop.product / product.template
 * - sale.order / sale.order.line
 * - stock.quant
 */

const SHOP_CATALOG = [
  {
    id: 1,
    name: "Wilson Carbon Force Pro Padel Racket",
    category: "rackets",
    category_label: "Rackets",
    price: 12500,
    stock: 8,
    description: "Engineered for elite power and precision. Features high-density foam core, carbon weave face, and Tri-Hex grip texture for maximum spin.",
    image_icon: "🏓",
  },
  {
    id: 2,
    name: "Head Speed MP Tennis Racket (300g)",
    category: "rackets",
    category_label: "Rackets",
    price: 14200,
    stock: 6,
    description: "Built for fast-swinging tournament players. Auxetic 2.0 construction provides sensational feel and controlled power on heavy groundstrokes.",
    image_icon: "🎾",
  },
  {
    id: 3,
    name: "Yonex Astrox 88D Pro Badminton Racket",
    category: "rackets",
    category_label: "Rackets",
    price: 8900,
    stock: 12,
    description: "Heavy smash power racket favored by world doubles champions. Rotational Generator System balances swing weight effortlessly.",
    image_icon: "🏸",
  },
  {
    id: 4,
    name: "Wilson US Open Extra Duty Tennis Balls (Can of 4)",
    category: "balls",
    category_label: "Balls",
    price: 550,
    stock: 45,
    description: "The official ball of the US Open since 1978. Premium woven felt engineered for optimal performance and durability on hard courts.",
    image_icon: "🎾",
  },
  {
    id: 5,
    name: "Bullpadel Premium Pro Padel Balls (Can of 3)",
    category: "balls",
    category_label: "Balls",
    price: 620,
    stock: 30,
    description: "High-speed core designed specifically for padel glass courts with lively bounce and pressure retention.",
    image_icon: "🏓",
  },
  {
    id: 6,
    name: "Yonex Aerosensa 50 Tournament Shuttlecocks (Doz)",
    category: "balls",
    category_label: "Balls",
    price: 1850,
    stock: 25,
    description: "Grade 1 natural goose feather shuttlecocks certified for international tournament play.",
    image_icon: "🏸",
  },
  {
    id: 7,
    name: "Asics Gel-Resolution 9 Clay Tennis Shoes",
    category: "shoes",
    category_label: "Shoes",
    price: 9999,
    stock: 5,
    description: "Dynawall technology for unmatched lateral stability and sliding confidence on clay courts.",
    image_icon: "👟",
  },
  {
    id: 8,
    name: "Babolat Jet Premura 2 Men's Padel Shoes",
    category: "shoes",
    category_label: "Shoes",
    price: 10499,
    stock: 4,
    description: "Developed exclusively with Michelin rubber outsole for 360-degree rapid pivot agility on sand-turf.",
    image_icon: "👟",
  },
  {
    id: 9,
    name: "Champions Club Performance Aeroready Tee",
    category: "apparel",
    category_label: "Apparel",
    price: 1499,
    stock: 20,
    description: "Ultra-breathable micro-mesh athletic tee with moisture-wicking technology and club crest.",
    image_icon: "👕",
  },
  {
    id: 10,
    name: "Champions Club Pro Tech Court Shorts",
    category: "apparel",
    category_label: "Apparel",
    price: 1299,
    stock: 18,
    description: "4-way stretch court shorts equipped with deep ball-security pockets and ergonomic waistband.",
    image_icon: "🩳",
  },
  {
    id: 11,
    name: "Tour Pro Thermal Racket Bag (9 Rackets)",
    category: "accessories",
    category_label: "Accessories",
    price: 5400,
    stock: 7,
    description: "Isothermal compartment shields string tension from heat. Separate ventilated shoe pocket.",
    image_icon: "🎒",
  },
  {
    id: 12,
    name: "Bullpadel Tour Pro Overgrips (Pack of 3)",
    category: "accessories",
    category_label: "Accessories",
    price: 450,
    stock: 50,
    description: "Tacky non-slip overgrips offering exceptional sweat absorption and vibration dampening.",
    image_icon: "🎗️",
  },
  {
    id: 13,
    name: "Junior Graphite Training Racket (Under 14)",
    category: "rackets",
    category_label: "Rackets",
    price: 2800,
    stock: 0, // Out of stock demonstration
    description: "Lightweight junior development frame tailored for young players building clean technique.",
    image_icon: "🎾",
  }
];

const SHOP_CATEGORIES = [
  { id: "all", label: "All" },
  { id: "rackets", label: "Rackets" },
  { id: "balls", label: "Balls" },
  { id: "shoes", label: "Shoes" },
  { id: "accessories", label: "Accessories" },
  { id: "apparel", label: "Apparel" },
];

const SHOP_MEMBER = {
  name: "Chitt Hirpara",
  plan: "Gold",
  planCode: "gold",
  discountPct: 20, // Backend discount specification
};

/**
 * Service Layer: ShopService
 * Handles catalog filtering, backend price calculation, inventory deduction and order creation
 */
const ShopService = {
  async getProducts(category = "all", searchTerm = "") {
    return SHOP_CATALOG.filter((p) => {
      const matchCat = category === "all" || p.category === category;
      const matchSearch = !searchTerm || 
        p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        p.category.toLowerCase().includes(searchTerm.toLowerCase());
      return matchCat && matchSearch;
    });
  },

  async getProductById(id) {
    return SHOP_CATALOG.find((p) => p.id === Number(id)) || null;
  },

  /**
   * Calculates order totals and applies member tier discount from the backend
   */
  async calculateCartPricing(cartItems, memberId = 101) {
    let subtotal = 0;
    const verifiedItems = [];

    for (const item of cartItems) {
      const product = SHOP_CATALOG.find((p) => p.id === item.product.id);
      if (!product) continue;
      const qty = Math.max(1, item.qty);
      const itemSubtotal = product.price * qty;
      subtotal += itemSubtotal;
      verifiedItems.push({
        product,
        qty,
        itemSubtotal,
      });
    }

    const discountAmount = Math.round((subtotal * SHOP_MEMBER.discountPct) / 100);
    const total = Math.max(0, subtotal - discountAmount);

    return {
      subtotal,
      formattedSubtotal: `₹${subtotal.toLocaleString("en-IN")}`,
      discountAmount,
      formattedDiscount: `-₹${discountAmount.toLocaleString("en-IN")}`,
      discountLabel: `${SHOP_MEMBER.plan} Member Discount (${SHOP_MEMBER.discountPct}%)`,
      total,
      formattedTotal: `₹${total.toLocaleString("en-IN")}`,
    };
  },

  /**
   * Validates inventory, creates Odoo Sale Order, and updates stock quantities
   */
  async placeOrder(cartItems, fulfillmentType, deliveryAddress = "") {
    // 1. Stock validation check
    for (const item of cartItems) {
      const product = SHOP_CATALOG.find((p) => p.id === item.product.id);
      if (!product || product.stock < item.qty) {
        return {
          success: false,
          error_code: "STOCK_UNAVAILABLE",
          message: `⚠ ${product?.name || "Product"} only has ${product?.stock || 0} units left in stock. Please review your cart.`
        };
      }
    }

    // 2. Deduct inventory (Odoo Inventory simulation)
    for (const item of cartItems) {
      const product = SHOP_CATALOG.find((p) => p.id === item.product.id);
      product.stock = Math.max(0, product.stock - item.qty);
    }

    const pricing = await this.calculateCartPricing(cartItems);
    const orderId = `SC-${1024 + Math.floor(Math.random() * 500)}`;

    return {
      success: true,
      order: {
        orderId,
        customerName: SHOP_MEMBER.name,
        fulfillment: fulfillmentType === "club_pickup" ? "Collect at Club" : "Home Delivery",
        deliveryAddress: deliveryAddress || "Clubhouse Front Desk",
        items: [...cartItems],
        subtotal: pricing.formattedSubtotal,
        discount: pricing.formattedDiscount,
        total: pricing.formattedTotal,
        date: new Date().toLocaleDateString("en-IN", { day: "2-digit", month: "long", year: "numeric" }),
      }
    };
  }
};
