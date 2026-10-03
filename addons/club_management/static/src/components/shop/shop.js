/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

// Comprehensive Catalog for Pro-Shop
const DEFAULT_PRODUCTS = [
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
        stock: 0, // OUT OF STOCK DEMO
        description: "Lightweight junior development frame tailored for young players building clean technique.",
        image_icon: "🎾",
    }
];

const CATEGORIES = [
    { id: "all", label: "All" },
    { id: "rackets", label: "Rackets" },
    { id: "balls", label: "Balls" },
    { id: "shoes", label: "Shoes" },
    { id: "accessories", label: "Accessories" },
    { id: "apparel", label: "Apparel" },
];

const CURRENT_MEMBER = {
    name: "Chitt Hirpara",
    plan: "Gold",
    planCode: "gold",
    discountPct: 20, // 20% discount on Pro-Shop as per Gold Plan
};

export class ShopPage extends Component {
    static template = "club_management.ShopPage";

    setup() {
        try {
            this.orm = useService("orm");
            this.notification = useService("notification");
        } catch {
            this.orm = null;
            this.notification = null;
        }

        this.state = useState({
            currentView: "catalog", // "catalog" | "checkout" | "order_confirmed"
            products: DEFAULT_PRODUCTS,
            categories: CATEGORIES,
            selectedCategory: "all",
            searchQuery: "",
            inStockOnly: false,
            
            // Product Detail Modal
            selectedProduct: null,
            detailQuantity: 1,
            isDetailOpen: false,

            // Cart State
            cart: [], // [{ product, qty }]
            isCartOpen: false,

            // Checkout & Order
            fulfillment: "club_pickup", // "club_pickup" | "home_delivery"
            deliveryAddress: "",
            paymentMethod: "member_account", // "member_account" | "upi_card"
            confirmedOrder: null,

            // System Status
            loading: false,
            error: null,
        });

        onWillStart(async () => {
            await this.loadCatalog();
        });
    }

    get member() {
        return CURRENT_MEMBER;
    }

    get cartCount() {
        return this.state.cart.reduce((sum, item) => sum + item.qty, 0);
    }

    get cartSubtotal() {
        return this.state.cart.reduce((sum, item) => sum + (item.product.price * item.qty), 0);
    }

    get memberDiscountAmount() {
        // Backend discount rule: Gold = 20%
        return Math.round((this.cartSubtotal * this.member.discountPct) / 100);
    }

    get cartTotal() {
        return Math.max(0, this.cartSubtotal - this.memberDiscountAmount);
    }

    get filteredProducts() {
        return this.state.products.filter((p) => {
            const matchesCat = this.state.selectedCategory === "all" || p.category === this.state.selectedCategory;
            const matchesSearch = !this.state.searchQuery || 
                p.name.toLowerCase().includes(this.state.searchQuery.toLowerCase()) ||
                p.category.toLowerCase().includes(this.state.searchQuery.toLowerCase());
            const matchesStock = !this.state.inStockOnly || p.stock > 0;
            return matchesCat && matchesSearch && matchesStock;
        });
    }

    async loadCatalog() {
        this.state.loading = true;
        if (this.orm) {
            try {
                const res = await this.orm.call("club.shop.product", "get_shop_catalog", [
                    this.state.selectedCategory,
                    this.state.searchQuery
                ]);
                if (res && res.length) {
                    this.state.products = res;
                }
            } catch (err) {
                console.warn("[Shop OWL] Using cached catalog:", err);
            }
        }
        setTimeout(() => {
            this.state.loading = false;
        }, 150);
    }

    handleSearchInput(query) {
        this.state.searchQuery = query;
        this.state.loading = true;
        setTimeout(() => {
            this.state.loading = false;
        }, 120);
    }

    setCategory(catId) {
        this.state.selectedCategory = catId;
        this.state.loading = true;
        setTimeout(() => {
            this.state.loading = false;
        }, 120);
    }

    openProductDetail(product) {
        this.state.selectedProduct = product;
        this.state.detailQuantity = 1;
        this.state.isDetailOpen = true;
        this.state.error = null;
    }

    closeProductDetail() {
        this.state.isDetailOpen = false;
        this.state.selectedProduct = null;
    }

    incrementDetailQty() {
        if (!this.state.selectedProduct) return;
        if (this.state.detailQuantity >= this.state.selectedProduct.stock) {
            this.state.error = `⚠ Only ${this.state.selectedProduct.stock} units are available.`;
            return;
        }
        this.state.detailQuantity += 1;
        this.state.error = null;
    }

    decrementDetailQty() {
        if (this.state.detailQuantity > 1) {
            this.state.detailQuantity -= 1;
            this.state.error = null;
        }
    }

    addToCart(product, qty = 1) {
        this.state.error = null;
        if (product.stock <= 0) {
            this.state.error = "⚠ This product is currently out of stock.";
            return;
        }

        const existing = this.state.cart.find((i) => i.product.id === product.id);
        const currentQtyInCart = existing ? existing.qty : 0;

        if (currentQtyInCart + qty > product.stock) {
            this.state.error = `⚠ Only ${product.stock} units are available in stock.`;
            return;
        }

        if (existing) {
            existing.qty += qty;
        } else {
            this.state.cart.push({ product, qty });
        }

        this.closeProductDetail();
        this.openCart();

        if (this.notification) {
            this.notification.add(`Added ${product.name} to cart.`, { type: "success" });
        }
    }

    updateCartItemQty(productId, delta) {
        const item = this.state.cart.find((i) => i.product.id === productId);
        if (!item) return;

        if (delta > 0) {
            if (item.qty + 1 > item.product.stock) {
                this.state.error = `⚠ Only ${item.product.stock} units are available.`;
                return;
            }
            item.qty += 1;
        } else {
            if (item.qty <= 1) {
                this.removeCartItem(productId);
                return;
            }
            item.qty -= 1;
        }
        this.state.error = null;
    }

    removeCartItem(productId) {
        this.state.cart = this.state.cart.filter((i) => i.product.id !== productId);
    }

    openCart() {
        this.state.isCartOpen = true;
    }

    closeCart() {
        this.state.isCartOpen = false;
    }

    proceedToCheckout() {
        if (this.state.cart.length === 0) return;
        this.closeCart();
        this.state.currentView = "checkout";
        this.state.error = null;
    }

    async placeOrder() {
        this.state.loading = true;
        this.state.error = null;

        // Stock re-validation check before placing order
        for (const item of this.state.cart) {
            if (item.qty > item.product.stock) {
                this.state.loading = false;
                this.state.error = "⚠ Stock availability changed. Please review your cart.";
                return;
            }
        }

        // Deduct inventory in products
        for (const item of this.state.cart) {
            item.product.stock = Math.max(0, item.product.stock - item.qty);
        }

        const nextOrderNum = `SC-${1024 + Math.floor(Math.random() * 800)}`;
        this.state.confirmedOrder = {
            order_id: nextOrderNum,
            customer_name: this.member.name,
            fulfillment: this.state.fulfillment === "club_pickup" ? "Collect at Club" : "Home Delivery",
            delivery_address: this.state.deliveryAddress || "Clubhouse Front Desk",
            items: [...this.state.cart],
            subtotal: `₹${this.cartSubtotal.toLocaleString("en-IN")}`,
            discount: `-₹${this.memberDiscountAmount.toLocaleString("en-IN")}`,
            total: `₹${this.cartTotal.toLocaleString("en-IN")}`,
            date: new Date().toLocaleDateString("en-IN", { day: "2-digit", month: "long", year: "numeric" }),
        };

        // Reset cart and go to confirmation screen
        this.state.cart = [];
        this.state.currentView = "order_confirmed";
        this.state.loading = false;
    }

    backToCatalog() {
        this.state.currentView = "catalog";
        this.state.error = null;
    }
}

registry.category("actions").add("club_management.shop", ShopPage);
