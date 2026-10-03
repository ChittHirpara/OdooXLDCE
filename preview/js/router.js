/**
 * Champions Club — Sports Club Management System
 * Unified Client-Side SPA Router
 *
 * Implements seamless, zero-reload routing between:
 * - #/memberships -> Membership Plans UI
 * - #/courts      -> Court Booking Engine
 * - #/shop        -> Pro-Shop & Equipment eCommerce
 * - #/pos         -> Commercial Bar & Cafeteria POS
 */

class ChampionsClubRouter {
  constructor() {
    this.viewport = null;
    this.currentRoute = null;

    this.routes = {
      "#/memberships": () => this.mountMemberships(),
      "#/courts": () => this.mountCourts(),
      "#/shop": () => this.mountShop(),
      "#/pos": () => this.mountPOS(),
    };
  }

  init() {
    this.viewport = document.getElementById("app-viewport");
    if (!this.viewport) {
      this.viewport = document.createElement("div");
      this.viewport.id = "app-viewport";
      document.body.prepend(this.viewport);
    }

    // Listen to hash changes
    window.addEventListener("hashchange", () => this.handleRoute());

    // Listen to DOM events
    document.addEventListener("DOMContentLoaded", () => this.handleRoute());
    window.addEventListener("load", () => this.handleRoute());

    // Execute immediately so view is mounted without delay
    this.handleRoute();
  }

  getRouteKey() {
    const hash = window.location.hash.trim().toLowerCase();
    if (!hash || hash === "#" || hash === "#/" || hash === "#memberships") {
      return "#/memberships";
    }
    if (hash === "#courts") return "#/courts";
    if (hash === "#shop") return "#/shop";
    if (hash === "#pos") return "#/pos";

    // Standard hash format
    for (const key of Object.keys(this.routes)) {
      if (hash.startsWith(key)) {
        return key;
      }
    }
    return "#/memberships";
  }

  handleRoute() {
    const routeKey = this.getRouteKey();
    if (this.currentRoute === routeKey && this.viewport && this.viewport.children.length > 0) {
      this.updateActiveNavLinks(routeKey);
      return;
    }

    this.currentRoute = routeKey;

    // Execute route handler
    const handler = this.routes[routeKey] || this.routes["#/memberships"];
    try {
      handler();
    } catch (err) {
      console.error("Route handling failed for:", routeKey, err);
    }

    this.updateActiveNavLinks(routeKey);
    window.scrollTo({ top: 0, behavior: "instant" });
  }

  mountMemberships() {
    this.viewport.innerHTML = `<div id="app-root"></div>`;
    if (window.MembershipPage) {
      try {
        window.MembershipPage.init();
      } catch (e) {
        console.error("MembershipPage init error:", e);
      }
    }
  }

  mountCourts() {
    this.viewport.innerHTML = `<div id="booking-app-root"></div>`;
    if (window.CourtBookingPage) {
      try {
        window.CourtBookingPage.init();
      } catch (e) {
        console.error("CourtBookingPage init error:", e);
      }
    }
  }

  mountShop() {
    this.viewport.innerHTML = `<div id="shop-app-root"></div>`;
    const mountPoint = document.getElementById("shop-app-root");
    if (window.ShopPageController && mountPoint) {
      try {
        window.shopPageApp = new window.ShopPageController(mountPoint);
      } catch (e) {
        console.error("ShopPageController init error:", e);
      }
    }
  }

  mountPOS() {
    this.viewport.innerHTML = `<div id="pos-app-root"></div>`;
    const mountPoint = document.getElementById("pos-app-root");
    if (window.BarPOSController && mountPoint) {
      try {
        window.posApp = new window.BarPOSController(mountPoint);
      } catch (e) {
        console.error("BarPOSController init error:", e);
      }
    }
  }

  updateActiveNavLinks(routeKey) {
    const navLinks = document.querySelectorAll(".cc-nav-link, .cc-pos-nav-links a");
    navLinks.forEach((link) => {
      const href = link.getAttribute("href");
      if (href && (href.toLowerCase() === routeKey || (routeKey === "#/memberships" && href.includes("memberships")))) {
        link.classList.add("active");
      } else {
        link.classList.remove("active");
      }
    });
  }
}

// Global router instantiation
window.appRouter = new ChampionsClubRouter();
window.appRouter.init();
