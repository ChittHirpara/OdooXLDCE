/**
 * Champions Club — Sports Club Management System
 * Membership Plan Data Model (Odoo 19 ORM Schema Compatible)
 *
 * Exactly 3 tiers as per challenge brief:
 * 1. GOLD   (Premium / Full Access)
 * 2. SILVER (Standard)
 * 3. JUNIOR (Under 18 / Discounted)
 */

const MEMBERSHIP_PLANS_DATA = [
  {
    id: "gold",
    name: "GOLD",
    code: "gold",
    badge: "MOST POPULAR",
    description: "Premium access for members who want the complete club experience.",
    price: 5000,
    currency: "₹",
    billing_period: "year",
    is_featured: true,
    benefits: [
      "Full club access",
      "Premium court benefits",
      "Shop benefits",
      "Bar benefits"
    ],
    // Detailed attributes for comparison & Odoo backend mapping
    features: {
      club_access: "Full club access (All facilities & lounges)",
      court_benefits: "Priority prime-time booking & 7 days advance",
      shop_benefits: "20% member discount on all gear",
      bar_benefits: "15% discount at cafeteria & sports bar",
      membership_type: "Premium / Full Access VIP"
    },
    active: true
  },
  {
    id: "silver",
    name: "SILVER",
    code: "silver",
    badge: null,
    description: "Standard membership for regular club users.",
    price: 3000,
    currency: "₹",
    billing_period: "year",
    is_featured: false,
    benefits: [
      "Standard club access",
      "Court benefits",
      "Shop benefits"
    ],
    features: {
      club_access: "Standard club access (Courts & locker room)",
      court_benefits: "Standard booking window (4 days advance)",
      shop_benefits: "10% member discount on gear",
      bar_benefits: "Standard member rates (No discount)",
      membership_type: "Standard Adult Membership"
    },
    active: true
  },
  {
    id: "junior",
    name: "JUNIOR",
    code: "junior",
    badge: "UNDER 18",
    description: "Discounted membership for members under 18.",
    price: 1500,
    currency: "₹",
    billing_period: "year",
    is_featured: false,
    benefits: [
      "Junior access",
      "Discounted court rates",
      "Junior benefits"
    ],
    features: {
      club_access: "Junior access (Academy & off-peak hours)",
      court_benefits: "Discounted court rates (Off-peak & clinics)",
      shop_benefits: "5% discount on junior equipment",
      bar_benefits: "10% smoothie bar & snacks discount",
      membership_type: "Youth & Academy (< 18 yrs)"
    },
    active: true
  }
];

// Navigation menu definition for Champions Club SaaS
const CLUB_NAV_ITEMS = [
  { label: "Memberships", href: "#/memberships", active: true },
  { label: "Courts", href: "#/courts", active: false },
  { label: "Shop", href: "#/shop", active: false },
  { label: "Bar + POS", href: "#/pos", active: false },
];

// Current logged in user context (mocking Odoo session info)
const CURRENT_USER = {
  name: "Vikram Mehta",
  role: "Club Operations Director",
  initials: "VM",
  avatarUrl: null,
  unreadNotifications: 3,
};
