/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

const PERIODS = [
    { key: "today", label: "Today" },
    { key: "week", label: "This week" },
    { key: "month", label: "This month" },
    { key: "all", label: "All time" },
];

export class OwnerDashboard extends Component {
    static template = "club_management.OwnerDashboard";

    setup() {
        this.orm = useService("orm");
        this.periods = PERIODS;
        this.state = useState({ period: "month", data: null, loading: true });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.data = await this.orm.call("club.dashboard", "get_dashboard_data", [this.state.period]);
        this.state.loading = false;
    }

    async setPeriod(period) {
        this.state.period = period;
        await this.load();
    }

    money(amount) {
        const symbol = this.state.data ? this.state.data.currency_symbol : "";
        return symbol + Math.round(amount || 0).toLocaleString("en-IN");
    }
}

registry.category("actions").add("club_management.owner_dashboard", OwnerDashboard);
