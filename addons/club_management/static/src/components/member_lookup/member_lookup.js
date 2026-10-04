/** @odoo-module **/

import { Component, useState, useRef, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

/**
 * Front-desk member lookup: scan the card QR (it types the member ID), or search by name, e-mail
 * or phone. Shows the plan and what it gives, the history with the club, and checks them in.
 */
export class MemberLookup extends Component {
    static template = "club_management.MemberLookup";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.input = useRef("query");
        this.state = useState({ query: "", member: null, matches: [], searched: false, busy: false });
        onMounted(() => this.input.el && this.input.el.focus());
    }

    async search() {
        const query = this.state.query.trim();
        if (query.length < 2) {
            return;
        }
        this.state.busy = true;
        try {
            const result = await this.orm.call("club.member.lookup", "find", [query]);
            this.state.member = result.member;
            this.state.matches = result.matches;
            this.state.searched = true;
        } catch (err) {
            this.notification.add((err.data && err.data.message) || "The search failed.", { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    onKeydown(ev) {
        if (ev.key === "Enter") {
            this.search();
        }
    }

    async open(id) {
        this.state.member = await this.orm.call("club.member.lookup", "profile", [id]);
        this.state.matches = [];
    }

    async checkIn() {
        try {
            this.state.member = await this.orm.call("club.member.lookup", "check_in", [this.state.member.id]);
            this.notification.add(`${this.state.member.name} is checked in.`, { type: "success" });
        } catch (err) {
            this.notification.add((err.data && err.data.message) || "Could not check in.", { type: "danger" });
        }
    }

    clear() {
        this.state.query = "";
        this.state.member = null;
        this.state.matches = [];
        this.state.searched = false;
        if (this.input.el) {
            this.input.el.focus();
        }
    }

    money(amount) {
        return "₹" + Math.round(amount || 0).toLocaleString("en-IN");
    }

    get statusClass() {
        const m = this.state.member;
        return m && m.status === "active" ? "text-bg-success" : "text-bg-danger";
    }
}

registry.category("actions").add("club_management.member_lookup", MemberLookup);
