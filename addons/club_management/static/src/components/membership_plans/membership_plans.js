/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { ClubMemberPicker } from "../common/member_picker";

const COMPARISON_ROWS = [
    { key: "club_access", label: "Club access" },
    { key: "court_benefits", label: "Court benefits" },
    { key: "shop_benefits", label: "Shop benefits" },
    { key: "bar_benefits", label: "Bar benefits" },
    { key: "membership_type", label: "Membership type" },
];

const EMPTY_PERSON = { name: "", email: "", phone: "", dob: "" };

/**
 * Staff view of the three plans. Choosing a plan opens the "Enrol at the desk" panel: renew an
 * existing member, or sign up a new person and take payment. The server runs the same chain as
 * the website (enquiry, quotation, invoice, member, payment) in `club.membership.purchase.desk_enroll`.
 */
export class MembershipPlans extends Component {
    static template = "club_management.MembershipPlans";
    static components = { ClubMemberPicker };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            selectedPlanId: "gold",
            plans: [],
            isLoading: true,
            error: "",
            member: null,
            person: { ...EMPTY_PERSON },
            method: "cash",
            busy: false,
            formKey: 0,
            done: null,
        });
        onWillStart(() => this.loadPlans());
    }

    get comparisonRows() {
        return COMPARISON_ROWS;
    }

    async loadPlans() {
        try {
            const result = await this.orm.call("club.membership.plan", "get_frontend_plans", []);
            this.state.plans = result || [];
            if (this.state.plans.length && !this.state.plans.some((p) => p.id === this.state.selectedPlanId)) {
                this.state.selectedPlanId = this.state.plans[0].id;
            }
        } catch (err) {
            this.state.error = "The plans could not be loaded. Refresh the page or ask an administrator.";
            console.warn("[Club] Could not load the plans:", err);
        } finally {
            this.state.isLoading = false;
        }
    }

    selectPlan(planId) {
        this.state.selectedPlanId = planId;
        this.state.done = null;
    }

    onMemberChange(member) {
        this.state.member = member;
        this.state.done = null;
    }

    get selectedPlan() {
        return this.state.plans.find((p) => p.id === this.state.selectedPlanId) || this.state.plans[0];
    }

    get isNewPerson() {
        return !this.state.member || !this.state.member.id;
    }

    get enrolLabel() {
        const plan = this.selectedPlan;
        if (!plan) {
            return "Enrol";
        }
        const name = plan.name.charAt(0) + plan.name.slice(1).toLowerCase();
        const price = `${plan.currency}${plan.price.toLocaleString("en-IN")}`;
        return `${this.isNewPerson ? "Enrol" : "Renew"} on ${name} and take ${price}`;
    }

    async enrol() {
        const plan = this.selectedPlan;
        if (!plan || this.state.busy) {
            return;
        }
        const person = this.state.person;
        this.state.busy = true;
        this.state.done = null;
        try {
            const result = await this.orm.call("club.membership.purchase", "desk_enroll_api", [plan.code], {
                partner_id: this.isNewPerson ? false : this.state.member.id,
                name: person.name,
                email: person.email,
                phone: person.phone,
                date_of_birth: person.dob || false,
                method: this.state.method,
            });
            this.state.done = result;
            this.state.person = { ...EMPTY_PERSON };
            this.state.formKey++;
            this.notification.add(result.message, { type: "success" });
        } catch (err) {
            const message = (err.data && err.data.message) || err.message || "The membership could not be started.";
            this.notification.add(message, { type: "danger", sticky: false });
        } finally {
            this.state.busy = false;
        }
    }
}

// Register as an Odoo Client Action
registry.category("actions").add("club_management.membership_plans", MembershipPlans);
