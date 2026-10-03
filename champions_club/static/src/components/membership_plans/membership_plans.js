/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

// Default mock data mapping to Odoo ORM models
const DEFAULT_PLANS = [
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

export class MembershipPlans extends Component {
    static template = "champions_club.MembershipPlans";

    setup() {
        try {
            this.orm = useService("orm");
            this.notification = useService("notification");
        } catch {
            this.orm = null;
            this.notification = null;
        }

        this.state = useState({
            selectedPlanId: "gold",
            plans: DEFAULT_PLANS,
            isLoading: false,
        });

        onWillStart(async () => {
            await this.loadPlans();
        });
    }

    async loadPlans() {
        if (this.orm) {
            try {
                this.state.isLoading = true;
                const result = await this.orm.call(
                    "champions.membership.plan",
                    "get_frontend_plans",
                    []
                );
                if (result && result.length) {
                    this.state.plans = result;
                }
            } catch (err) {
                console.warn("[Champions Club OWL] Using default plans:", err);
            } finally {
                this.state.isLoading = false;
            }
        }
    }

    selectPlan(planId) {
        this.state.selectedPlanId = planId;
        const selected = this.state.plans.find((p) => p.id === planId);
        
        if (this.notification && selected) {
            this.notification.add(
                `Selected ${selected.name} Plan (${selected.currency}${selected.price.toLocaleString('en-IN')} / ${selected.billing_period})`,
                { type: "success" }
            );
        }
    }

    get selectedPlan() {
        return this.state.plans.find((p) => p.id === this.state.selectedPlanId) || this.state.plans[0];
    }
}

// Register as an Odoo 19 Client Action
registry.category("actions").add("champions_club.membership_plans", MembershipPlans);
