/** @odoo-module **/

import { Component, useState, onMounted, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const STORAGE_KEY = "club_acting_member";

/** Nobody picked: a walk-in pays full price. */
export const WALK_IN = {
    id: 0,
    name: "Walk-in guest",
    plan: "Guest",
    planCode: "none",
    status: "none",
    memberId: "",
    active: true,
    discountPct: 0,
    shopDiscountPct: 0,
    expiry: null,
};

function remembered() {
    try {
        return Number(window.sessionStorage.getItem(STORAGE_KEY) || 0);
    } catch {
        return 0;
    }
}

/**
 * "Booking for" / "Selling to": who the front desk is serving. It replaces the fixed demo
 * member the screens used to show. The choice is remembered for the browser session, so the
 * court, shop and bar screens agree. Prices and limits are always decided by the server.
 */
export class ClubMemberPicker extends Component {
    static template = "club_management.ClubMemberPicker";
    static props = { onChange: Function, label: { type: String, optional: true }, guestLabel: { type: String, optional: true }, guestHint: { type: String, optional: true } };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ members: [WALK_IN], selectedId: remembered() });
        onWillStart(async () => {
            try {
                const rows = await this.orm.call("res.partner", "get_members_list", []);
                const members = rows
                    .filter((row) => row.id > 0)
                    .map((row) => ({
                        id: row.id,
                        name: row.name,
                        plan: row.plan,
                        planCode: row.plan_code || row.planCode,
                        status: row.status,
                        memberId: row.member_id,
                        active: !!row.is_active && row.status === "active",
                        discountPct: row.discountPct || 0,
                        shopDiscountPct: row.shopDiscountPct || 0,
                        expiry: row.expiry_date,
                    }));
                this.state.members = [WALK_IN, ...members];
            } catch (err) {
                console.warn("[Club] Could not load the member list:", err);
            }
            if (!this.state.members.some((m) => m.id === this.state.selectedId)) {
                this.state.selectedId = 0;
            }
        });
        // Tell the screen who is selected only once mounted: changing the parent's state while this
        // component is still starting would restart the parent's first render, over and over.
        onMounted(() => this.props.onChange(this.selected));
    }

    get selected() {
        return this.state.members.find((m) => m.id === this.state.selectedId) || WALK_IN;
    }

    optionLabel(member) {
        if (!member.id) {
            return this.props.guestLabel || member.name;
        }
        const ended = member.status === "expired" ? ", expired" : "";
        return `${member.name} (${member.memberId}, ${member.plan}${ended})`;
    }

    onSelect(ev) {
        this.state.selectedId = Number(ev.target.value);
        try {
            window.sessionStorage.setItem(STORAGE_KEY, String(this.state.selectedId));
        } catch {
            /* the choice just is not remembered */
        }
        this.props.onChange(this.selected);
    }
}
