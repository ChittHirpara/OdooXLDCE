/**
 * Champions Club — Sports Club Management System
 * Clean & Minimal Component Architecture for Membership Plans
 */

// 1. MembershipSelector (State & Event Controller)
const MembershipSelector = {
  selectedPlanId: "gold",

  init(initialPlanId = "gold") {
    this.selectedPlanId = initialPlanId;
  },

  getSelectedPlan() {
    return MEMBERSHIP_PLANS_DATA.find((p) => p.id === this.selectedPlanId);
  },

  selectPlan(planId) {
    if (this.selectedPlanId === planId) return;
    this.selectedPlanId = planId;
    this.updateUI();
    this.notifySelection(planId);
  },

  updateUI() {
    // 1. Update Card Selected States
    MEMBERSHIP_PLANS_DATA.forEach((plan) => {
      const cardEl = document.getElementById(`membership-card-${plan.id}`);
      const btnEl = document.getElementById(`btn-select-${plan.id}`);

      if (cardEl && btnEl) {
        if (plan.id === this.selectedPlanId) {
          cardEl.classList.add("selected");
          btnEl.innerHTML = `
            <svg width="15" height="15" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
            </svg>
            <span>Selected</span>
          `;
        } else {
          cardEl.classList.remove("selected");
          btnEl.innerHTML = `Choose ${this.capitalize(plan.name)}`;
        }
      }
    });

    // 2. Highlight corresponding column in comparison table
    const tableEl = document.getElementById("membership-comparison-table");
    if (tableEl) {
      ["gold", "silver", "junior"].forEach((tier) => {
        const cols = tableEl.querySelectorAll(`.col-${tier}`);
        cols.forEach((col) => {
          if (tier === this.selectedPlanId) {
            col.classList.add("selected-col");
          } else {
            col.classList.remove("selected-col");
          }
        });
      });
    }
  },

  capitalize(str) {
    if (!str) return "";
    return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
  },

  notifySelection(planId) {
    const plan = this.getSelectedPlan();
    if (!plan) return;

    const existingToast = document.querySelector(".cc-toast");
    if (existingToast) existingToast.remove();

    const toast = document.createElement("div");
    toast.className = "cc-toast";
    toast.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 20 20" fill="#10B981">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
      </svg>
      <span>Selected <strong>${plan.name}</strong> (${plan.currency}${plan.price.toLocaleString("en-IN")})</span>
    `;
    document.body.appendChild(toast);

    setTimeout(() => {
      toast.style.transition = "opacity 0.2s";
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 200);
    }, 2500);
  }
};

// 2. MembershipBenefits Component (Clean Minimal Rows)
const MembershipBenefits = {
  render(benefits = []) {
    const checkIcon = `
      <svg class="cc-check-icon" viewBox="0 0 20 20" fill="currentColor">
        <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
      </svg>
    `;

    return `
      <ul class="cc-benefits-list">
        ${benefits
          .map(
            (b) => `
          <li class="cc-benefit-item">
            ${checkIcon}
            <span>${b}</span>
          </li>
        `
          )
          .join("")}
      </ul>
    `;
  }
};

// 3. MembershipCard Component
const MembershipCard = {
  render(plan, isSelected) {
    const isGold = plan.id === "gold";
    const isJunior = plan.id === "junior";

    let badgeHtml = "";
    if (isGold && plan.badge) {
      badgeHtml = `<div class="cc-badge-popular">${plan.badge}</div>`;
    } else if (isJunior && plan.badge) {
      badgeHtml = `<div class="cc-badge-junior">${plan.badge}</div>`;
    }

    const buttonLabel = isSelected
      ? `
        <svg width="15" height="15" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
        </svg>
        <span>Selected</span>
      `
      : `Choose ${MembershipSelector.capitalize(plan.name)}`;

    return `
      <div class="cc-card cc-card-${plan.id} ${isSelected ? "selected" : ""}" 
           id="membership-card-${plan.id}" 
           data-plan-id="${plan.id}">
        
        ${badgeHtml}

        <div class="cc-card-header">
          <h3 class="cc-tier-name">${plan.name}</h3>
          <p class="cc-tier-desc">${plan.description}</p>
        </div>

        <div class="cc-price-wrap">
          <span class="cc-price-curr">${plan.currency}</span>
          <span class="cc-price-amount">${plan.price.toLocaleString("en-IN")}</span>
          <span class="cc-price-period">/ ${plan.billing_period}</span>
        </div>

        ${MembershipBenefits.render(plan.benefits)}

        <button class="cc-btn-select" id="btn-select-${plan.id}" data-plan-id="${plan.id}">
          ${buttonLabel}
        </button>
      </div>
    `;
  }
};

// 4. MembershipComparison Component
const MembershipComparison = {
  render(plans, selectedPlanId) {
    const goldPlan = plans.find((p) => p.id === "gold");
    const silverPlan = plans.find((p) => p.id === "silver");
    const juniorPlan = plans.find((p) => p.id === "junior");

    return `
      <section class="cc-comparison-card">
        <div class="cc-comparison-header">
          <h2 class="cc-comparison-title">Membership Comparison</h2>
          <p class="cc-comparison-subtitle">
            Compare access privileges, court benefits, and club discounts across all tiers.
          </p>
        </div>

        <div class="cc-table-wrapper">
          <table class="cc-table" id="membership-comparison-table">
            <thead>
              <tr>
                <th class="col-feature">Feature</th>
                <th class="col-gold ${selectedPlanId === "gold" ? "selected-col" : ""}">Gold</th>
                <th class="col-silver ${selectedPlanId === "silver" ? "selected-col" : ""}">Silver</th>
                <th class="col-junior ${selectedPlanId === "junior" ? "selected-col" : ""}">Junior</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td class="col-feature">Club access</td>
                <td class="col-gold col-val highlight ${selectedPlanId === "gold" ? "selected-col" : ""}">${goldPlan.features.club_access}</td>
                <td class="col-silver col-val ${selectedPlanId === "silver" ? "selected-col" : ""}">${silverPlan.features.club_access}</td>
                <td class="col-junior col-val ${selectedPlanId === "junior" ? "selected-col" : ""}">${juniorPlan.features.club_access}</td>
              </tr>
              <tr>
                <td class="col-feature">Court benefits</td>
                <td class="col-gold col-val highlight ${selectedPlanId === "gold" ? "selected-col" : ""}">${goldPlan.features.court_benefits}</td>
                <td class="col-silver col-val ${selectedPlanId === "silver" ? "selected-col" : ""}">${silverPlan.features.court_benefits}</td>
                <td class="col-junior col-val ${selectedPlanId === "junior" ? "selected-col" : ""}">${juniorPlan.features.court_benefits}</td>
              </tr>
              <tr>
                <td class="col-feature">Shop benefits</td>
                <td class="col-gold col-val highlight ${selectedPlanId === "gold" ? "selected-col" : ""}">${goldPlan.features.shop_benefits}</td>
                <td class="col-silver col-val ${selectedPlanId === "silver" ? "selected-col" : ""}">${silverPlan.features.shop_benefits}</td>
                <td class="col-junior col-val ${selectedPlanId === "junior" ? "selected-col" : ""}">${juniorPlan.features.shop_benefits}</td>
              </tr>
              <tr>
                <td class="col-feature">Bar benefits</td>
                <td class="col-gold col-val highlight ${selectedPlanId === "gold" ? "selected-col" : ""}">${goldPlan.features.bar_benefits}</td>
                <td class="col-silver col-val ${selectedPlanId === "silver" ? "selected-col" : ""}">${silverPlan.features.bar_benefits}</td>
                <td class="col-junior col-val ${selectedPlanId === "junior" ? "selected-col" : ""}">${juniorPlan.features.bar_benefits}</td>
              </tr>
              <tr>
                <td class="col-feature">Membership type</td>
                <td class="col-gold col-val highlight ${selectedPlanId === "gold" ? "selected-col" : ""}">${goldPlan.features.membership_type}</td>
                <td class="col-silver col-val ${selectedPlanId === "silver" ? "selected-col" : ""}">${silverPlan.features.membership_type}</td>
                <td class="col-junior col-val ${selectedPlanId === "junior" ? "selected-col" : ""}">${juniorPlan.features.membership_type}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    `;
  }
};

// 5. MembershipHero Component
const MembershipHero = {
  render() {
    return `
      <section class="cc-hero">
        <span class="cc-hero-pill">Memberships</span>
        <h1 class="cc-hero-heading">Choose Your Membership</h1>
        <p class="cc-hero-text">
          Get access to the club, courts and member benefits with a plan that fits you.
        </p>
      </section>
    `;
  }
};

// 6. MembershipHeader Component
const MembershipHeader = {
  render() {
    const navItemsHtml = CLUB_NAV_ITEMS.map(
      (item) => `
      <a href="${item.href}" class="cc-nav-link ${item.active ? "active" : ""}">
        ${item.label}
      </a>
    `
    ).join("");

    return `
      <header class="cc-header">
        <div class="cc-header-inner">
          <a href="#/memberships" class="cc-brand">
            <div class="cc-brand-emblem">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 2L3 7v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-9-5z"/>
              </svg>
            </div>
            <h1 class="cc-brand-title">Champions Club</h1>
          </a>

          <nav class="cc-nav">
            ${navItemsHtml}
          </nav>

          <div class="cc-header-right">
            <button class="cc-notification-btn" title="Notifications" aria-label="Notifications">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
              </svg>
              <span class="cc-notification-badge"></span>
            </button>

            <div class="cc-user-profile" title="Signed in as ${CURRENT_USER.name}">
              <div class="cc-user-avatar">${CURRENT_USER.initials}</div>
              <div class="cc-user-info">
                <span class="cc-user-name">${CURRENT_USER.name}</span>
                <span class="cc-user-role">${CURRENT_USER.role}</span>
              </div>
            </div>
          </div>
        </div>
      </header>
    `;
  }
};

// 7. MembershipPage (Root Orchestrator)
const MembershipPage = {
  init() {
    MembershipSelector.init("gold");
    this.render();
    this.bindEvents();
  },

  render() {
    const root = document.getElementById("app-root");
    if (!root) return;

    root.innerHTML = `
      ${MembershipHeader.render()}
      <main class="cc-main-container">
        ${MembershipHero.render()}
        
        <section class="cc-cards-grid" id="cards-grid">
          ${MEMBERSHIP_PLANS_DATA.map((plan) =>
            MembershipCard.render(plan, plan.id === MembershipSelector.selectedPlanId)
          ).join("")}
        </section>

        ${MembershipComparison.render(MEMBERSHIP_PLANS_DATA, MembershipSelector.selectedPlanId)}
      </main>
    `;
  },

  bindEvents() {
    const grid = document.getElementById("cards-grid");
    if (!grid) return;

    grid.addEventListener("click", (e) => {
      const card = e.target.closest(".cc-card");
      if (card) {
        const planId = card.getAttribute("data-plan-id");
        if (planId) {
          MembershipSelector.selectPlan(planId);
        }
      }
    });
  }
};

window.MembershipPage = MembershipPage;

document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("app-root")) {
    MembershipPage.init();
  }
});
