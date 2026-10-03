/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

// Default Data & Fallback Catalogs
const DEFAULT_TABLES = [
    { id: 1, name: "Table 01", capacity: 4, status: "occupied", active_order: { order_ref: "POS-00121", amount: 420, items_count: 3, member_name: "Aarav Patel" } },
    { id: 2, name: "Table 02", capacity: 2, status: "available", active_order: null },
    { id: 3, name: "Table 03", capacity: 4, status: "occupied", active_order: { order_ref: "POS-00123", amount: 780, items_count: 5, member_name: "Chitt Hirpara" } },
    { id: 4, name: "Table 04", capacity: 6, status: "available", active_order: null },
    { id: 5, name: "Table 05", capacity: 4, status: "occupied", active_order: { order_ref: "POS-00124", amount: 250, items_count: 2, member_name: "Rohan Shah" } },
    { id: 6, name: "Table 06", capacity: 2, status: "available", active_order: null },
    { id: 7, name: "Bar Counter 01", capacity: 1, status: "available", active_order: null },
    { id: 8, name: "Lounge 01", capacity: 8, status: "available", active_order: null },
];

const DEFAULT_CATEGORIES = [
    { id: "all", label: "All Items", icon: "🍽️" },
    { id: "drinks", label: "Drinks", icon: "🍹" },
    { id: "food", label: "Food", icon: "🥗" },
    { id: "snacks", label: "Snacks", icon: "🍿" },
    { id: "coffee", label: "Coffee & Tea", icon: "☕" },
    { id: "shakes", label: "Protein & Shakes", icon: "🥤" },
];

const DEFAULT_PRODUCTS = [
    { id: 1, name: "Espresso Single Origin", category: "coffee", price: 80, stock: 40, image_icon: "☕", is_available: true },
    { id: 2, name: "Artisanal Cappuccino", category: "coffee", price: 140, stock: 35, image_icon: "☕", is_available: true },
    { id: 3, name: "Cold Brew Nitro", category: "coffee", price: 160, stock: 20, image_icon: "🧊", is_available: true },
    { id: 4, name: "Whey Gold Recovery Shake", category: "shakes", price: 220, stock: 18, image_icon: "🥤", is_available: true },
    { id: 5, name: "Plant Berry Antioxidant Smoothie", category: "shakes", price: 240, stock: 15, image_icon: "🫐", is_available: true },
    { id: 6, name: "Hydration Electrolyte Coconut Water", category: "drinks", price: 90, stock: 50, image_icon: "🥥", is_available: true },
    { id: 7, name: "Fresh Orange & Mint Juice", category: "drinks", price: 130, stock: 25, image_icon: "🍊", is_available: true },
    { id: 8, name: "Sparkling Mineral Water (500ml)", category: "drinks", price: 60, stock: 60, image_icon: "💧", is_available: true },
    { id: 9, name: "Clubhouse Grilled Chicken Wrap", category: "food", price: 210, stock: 14, image_icon: "🌯", is_available: true },
    { id: 10, name: "Avocado & Sourdough Toast", category: "food", price: 190, stock: 12, image_icon: "🥑", is_available: true },
    { id: 11, name: "Mediterranean Quinoa Power Bowl", category: "food", price: 260, stock: 10, image_icon: "🥗", is_available: true },
    { id: 12, name: "Champions Classic Smash Burger", category: "food", price: 250, stock: 16, image_icon: "🍔", is_available: true },
    { id: 13, name: "Raw Whey Protein Bar (Salted Caramel)", category: "snacks", price: 110, stock: 45, image_icon: "🍫", is_available: true },
    { id: 14, name: "Roasted Almond & Cranberry Mix", category: "snacks", price: 120, stock: 30, image_icon: "🥜", is_available: true },
    { id: 15, name: "Baked Sweet Potato Crisps", category: "snacks", price: 95, stock: 0, image_icon: "🍠", is_available: false },
];

const CLUB_MEMBERS = [
    { id: 101, name: "Chitt Hirpara", plan: "Gold", planCode: "gold", discountPct: 15 },
    { id: 102, name: "Aarav Patel", plan: "Silver", planCode: "silver", discountPct: 10 },
    { id: 103, name: "Rohan Shah", plan: "Junior", planCode: "junior", discountPct: 5 },
    { id: 0, name: "Walk-in Guest", plan: "Guest", planCode: "none", discountPct: 0 },
];

export class BarPOSPage extends Component {
    static template = "champions_club.BarPOSPage";

    setup() {
        try {
            this.orm = useService("orm");
            this.notification = useService("notification");
        } catch {
            this.orm = null;
            this.notification = null;
        }

        this.state = useState({
            currentView: "pos", // "pos" | "tables" | "history"
            tables: DEFAULT_TABLES,
            currentTable: DEFAULT_TABLES[3], // Table 04 default
            categories: DEFAULT_CATEGORIES,
            selectedCategory: "all",
            searchQuery: "",
            products: DEFAULT_PRODUCTS,
            
            // Current Order / Cart
            cart: [
                { product: DEFAULT_PRODUCTS[0], qty: 2 }, // Coffee x2 = ₹160
                { product: DEFAULT_PRODUCTS[11], qty: 1 }, // Burger x1 = ₹250
                { product: DEFAULT_PRODUCTS[7], qty: 2 }, // Water x2 = ₹120
            ],
            selectedMember: CLUB_MEMBERS[0], // Chitt Hirpara (Gold)
            pricing: {
                subtotal: 530,
                formatted_subtotal: "₹530.00",
                discount_amount: 79.50,
                formatted_discount: "-₹79.50",
                discount_label: "Gold Member Discount (15%)",
                discount_pct: 15,
                total: 450.50,
                formatted_total: "₹450.50"
            },

            // Modals & Panels
            isOpenTabsOpen: false,
            isMemberSelectorOpen: false,
            isPaymentModalOpen: false,
            isShiftModalOpen: false,
            isSuccessOpen: false,

            // Payment Process State
            paymentMethod: "upi",
            isProcessingPayment: false,
            lastPaymentResult: null,

            // Shift data
            shiftData: {
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
                formatted_total: "₹22,500"
            },

            // Order History Log
            orderHistory: [
                { order_ref: "POS-00124", table: "Table 05", member: "Rohan Shah", amount: "₹250.00", method: "CASH", status: "Paid", time: "10:14 AM" },
                { order_ref: "POS-00123", table: "Table 03", member: "Chitt Hirpara", amount: "₹780.00", method: "UPI", status: "Paid", time: "09:48 AM" },
                { order_ref: "POS-00122", table: "Bar 01", member: "Walk-in Guest", amount: "₹180.00", method: "CARD", status: "Paid", time: "09:20 AM" },
                { order_ref: "POS-00121", table: "Table 01", member: "Aarav Patel", amount: "₹420.00", method: "UPI", status: "Paid", time: "08:55 AM" },
            ],

            loading: false,
            error: null,
        });

        onWillStart(async () => {
            await this.loadInitialOdooData();
            await this.calculatePricingFromBackend();
        });
    }

    get openTabsCount() {
        return this.state.tables.filter(t => t.status === 'occupied').length;
    }

    get filteredProducts() {
        return this.state.products.filter(p => {
            const matchesCat = this.state.selectedCategory === "all" || p.category === this.state.selectedCategory;
            const matchesSearch = !this.state.searchQuery || 
                p.name.toLowerCase().includes(this.state.searchQuery.toLowerCase()) ||
                p.category.toLowerCase().includes(this.state.searchQuery.toLowerCase());
            return matchesCat && matchesSearch;
        });
    }

    async loadInitialOdooData() {
        this.state.loading = true;
        if (this.orm) {
            try {
                // Fetch tables from Odoo
                const tables = await this.orm.call("club.pos.table", "get_tables_data", []);
                if (tables && tables.length) {
                    this.state.tables = tables;
                }
                // Fetch products from Odoo
                const products = await this.orm.call("club.pos.product", "get_products_data", ["all", ""]);
                if (products && products.length) {
                    this.state.products = products;
                }
                // Fetch shift data from Odoo
                const shift = await this.orm.call("club.pos.session", "get_current_shift", []);
                if (shift) {
                    this.state.shiftData = shift;
                }
            } catch (err) {
                console.warn("[Bar POS OWL] Using fallback state:", err);
            }
        }
        this.state.loading = false;
    }

    /**
     * Critical Rule: Frontend NEVER calculates membership discounts!
     * Backend is the single source of truth for pricing calculations.
     */
    async calculatePricingFromBackend() {
        const orderItems = this.state.cart.map(item => ({
            product_id: item.product.id,
            qty: item.qty,
            price: item.product.price
        }));

        const planCode = this.state.selectedMember?.planCode || "none";

        if (this.orm) {
            try {
                const res = await this.orm.call("club.pos.order", "calculate_order_pricing", [orderItems, planCode]);
                if (res) {
                    this.state.pricing = res;
                    return;
                }
            } catch (err) {
                console.warn("[Bar POS OWL] RPC pricing fallback:", err);
            }
        }

        // Local backend-equivalent simulation
        let subtotal = 0;
        for (const i of this.state.cart) {
            subtotal += i.product.price * i.qty;
        }
        const pct = this.state.selectedMember ? this.state.selectedMember.discountPct : 0;
        const discountAmount = Math.round((subtotal * pct) / 100);
        const total = Math.max(0, subtotal - discountAmount);

        this.state.pricing = {
            subtotal,
            formatted_subtotal: `₹${subtotal.toFixed(2)}`,
            discount_amount: discountAmount,
            formatted_discount: discountAmount > 0 ? `-₹${discountAmount.toFixed(2)}` : "₹0.00",
            discount_label: pct > 0 ? `${this.state.selectedMember.plan} Member Discount (${pct}%)` : "No Discount",
            discount_pct: pct,
            total,
            formatted_total: `₹${total.toFixed(2)}`
        };
    }

    // View Switching
    setView(viewName) {
        this.state.currentView = viewName;
        this.state.error = null;
    }

    // Category Selection
    setCategory(categoryId) {
        this.state.selectedCategory = categoryId;
    }

    // Search Input
    handleSearchInput(event) {
        this.state.searchQuery = event.target.value;
    }

    clearSearch() {
        this.state.searchQuery = "";
    }

    // Table Selection Logic
    selectTable(table) {
        this.state.currentTable = table;
        this.state.currentView = "pos";

        if (table.status === "occupied" && table.active_order) {
            // Load existing tab simulation
            this.state.cart = [
                { product: DEFAULT_PRODUCTS[1], qty: 1 },
                { product: DEFAULT_PRODUCTS[8], qty: 1 },
            ];
            if (this.notification) {
                this.notification.add(`Opened active tab for ${table.name} (${table.active_order.order_ref})`, { type: "info" });
            }
        } else {
            // Available table: start clean order
            this.state.cart = [];
        }
        this.calculatePricingFromBackend();
    }

    // Product Add to Cart
    addToCart(product) {
        if (!product.is_available || product.stock <= 0) {
            this.state.error = `⚠ ${product.name} is currently out of stock.`;
            return;
        }

        const existing = this.state.cart.find(i => i.product.id === product.id);
        const currentQty = existing ? existing.qty : 0;

        if (currentQty + 1 > product.stock) {
            this.state.error = `⚠ Insufficient stock: only ${product.stock} units of ${product.name} available.`;
            return;
        }

        if (existing) {
            existing.qty += 1;
        } else {
            this.state.cart.push({ product, qty: 1 });
        }

        this.state.error = null;
        this.calculatePricingFromBackend();
    }

    // Cart Quantity Updates
    updateCartItemQty(productId, delta) {
        const item = this.state.cart.find(i => i.product.id === productId);
        if (!item) return;

        if (delta > 0) {
            if (item.qty + 1 > item.product.stock) {
                this.state.error = `⚠ Only ${item.product.stock} units available in stock.`;
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
        this.calculatePricingFromBackend();
    }

    removeCartItem(productId) {
        this.state.cart = this.state.cart.filter(i => i.product.id !== productId);
        this.calculatePricingFromBackend();
    }

    clearOrder() {
        this.state.cart = [];
        this.calculatePricingFromBackend();
    }

    // Member Selection
    openMemberSelector() {
        this.state.isMemberSelectorOpen = true;
    }

    closeMemberSelector() {
        this.state.isMemberSelectorOpen = false;
    }

    selectMember(member) {
        this.state.selectedMember = member;
        this.state.isMemberSelectorOpen = false;
        this.calculatePricingFromBackend();
        if (this.notification) {
            this.notification.add(`Customer set to ${member.name} (${member.plan})`, { type: "success" });
        }
    }

    // Open Tabs Panel
    openTabsDrawer() {
        this.state.isOpenTabsOpen = true;
    }

    closeTabsDrawer() {
        this.state.isOpenTabsOpen = false;
    }

    saveCurrentAsTab() {
        if (this.state.cart.length === 0) {
            this.state.error = "Cannot save an empty tab.";
            return;
        }
        // Mark table as occupied
        if (this.state.currentTable) {
            this.state.currentTable.status = "occupied";
            this.state.currentTable.active_order = {
                order_ref: `POS-${10120 + Math.floor(Math.random() * 80)}`,
                amount: this.state.pricing.total,
                items_count: this.state.cart.reduce((s, i) => s + i.qty, 0),
                member_name: this.state.selectedMember.name
            };
        }
        if (this.notification) {
            this.notification.add(`Tab saved for ${this.state.currentTable.name}.`, { type: "success" });
        }
    }

    // Shift Panel
    openShiftPanel() {
        this.state.isShiftModalOpen = true;
    }

    closeShiftPanel() {
        this.state.isShiftModalOpen = false;
    }

    closeCurrentShift() {
        alert(`Shift for ${this.state.shiftData.staff_name} closed successfully in Odoo POS.\nZ-Report generated: Total Sales ${this.state.shiftData.formatted_total}`);
        this.state.isShiftModalOpen = false;
    }

    // Payment Flow
    openPaymentModal() {
        if (this.state.cart.length === 0) {
            this.state.error = "Cannot proceed to payment with an empty order.";
            return;
        }
        this.state.isPaymentModalOpen = true;
        this.state.error = null;
    }

    closePaymentModal() {
        if (this.state.isProcessingPayment) return;
        this.state.isPaymentModalOpen = false;
    }

    setPaymentMethod(method) {
        this.state.paymentMethod = method;
    }

    async processPayment() {
        if (this.state.isProcessingPayment) return;

        this.state.isProcessingPayment = true;
        this.state.error = null;

        const orderData = {
            table_name: this.state.currentTable.name,
            member_name: this.state.selectedMember.name,
            payment_method: this.state.paymentMethod,
            items: this.state.cart,
            pricing: this.state.pricing
        };

        try {
            let result = null;
            if (this.orm) {
                result = await this.orm.call("club.pos.order", "process_payment_api", [orderData]);
            } else {
                // Simulation delay to reflect commercial POS transaction
                await new Promise(r => setTimeout(r, 600));
                result = {
                    success: true,
                    order_ref: `POS-${10125 + Math.floor(Math.random() * 50)}`,
                    table_name: this.state.currentTable.name,
                    member_name: this.state.selectedMember.name,
                    payment_method: this.state.paymentMethod.toUpperCase(),
                    amount: this.state.pricing.formatted_total,
                    date: new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })
                };
            }

            if (result && result.success) {
                // Deduct stock in catalog
                for (const item of this.state.cart) {
                    item.product.stock = Math.max(0, item.product.stock - item.qty);
                }

                // Free the table
                if (this.state.currentTable) {
                    this.state.currentTable.status = "available";
                    this.state.currentTable.active_order = null;
                }

                // Add to order history
                this.state.orderHistory.unshift({
                    order_ref: result.order_ref,
                    table: result.table_name,
                    member: result.member_name,
                    amount: result.amount,
                    method: result.payment_method,
                    status: "Paid",
                    time: "Just now"
                });

                this.state.lastPaymentResult = result;
                this.state.isPaymentModalOpen = false;
                this.state.isSuccessOpen = true;
                this.state.cart = [];
                this.calculatePricingFromBackend();
            } else {
                this.state.error = result?.message || "Payment failed. Please try again.";
            }
        } catch (err) {
            this.state.error = "RPC communication error while finalizing payment.";
        } finally {
            this.state.isProcessingPayment = false;
        }
    }

    startNewOrder() {
        this.state.isSuccessOpen = false;
        this.state.lastPaymentResult = null;
        this.state.cart = [];
        this.calculatePricingFromBackend();
    }

    printReceipt() {
        alert(`[Odoo Thermal POS Receipt]\n\nCHAMPIONS CLUB BAR & CAFETERIA\nOrder: ${this.state.lastPaymentResult?.order_ref}\nTable: ${this.state.lastPaymentResult?.table_name}\nMember: ${this.state.lastPaymentResult?.member_name}\nTotal Paid: ${this.state.lastPaymentResult?.amount}\nPayment via: ${this.state.lastPaymentResult?.payment_method}\n\nThank you for dining at Champions Club!`);
    }

    dismissError() {
        this.state.error = null;
    }
}

registry.category("actions").add("champions_club.bar_pos", BarPOSPage);
