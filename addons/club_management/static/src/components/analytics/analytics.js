/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

const RANGES = [
    { months: 3, label: "3 months" },
    { months: 6, label: "6 months" },
    { months: 12, label: "12 months" },
];

export class ClubAnalytics extends Component {
    static template = "club_management.ClubAnalytics";

    setup() {
        this.orm = useService("orm");
        this.ranges = RANGES;
        this.state = useState({ months: 6, data: null, loading: true });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.data = await this.orm.call("club.dashboard", "get_analytics", [this.state.months]);
        this.state.loading = false;
    }

    async setRange(months) {
        this.state.months = months;
        await this.load();
    }

    money(amount) {
        const symbol = this.state.data ? this.state.data.currency_symbol : "";
        return symbol + Math.round(amount || 0).toLocaleString("en-IN");
    }

    /** Bar width in percent of the largest value, never below a sliver so a small value stays visible. */
    width(value, rows, key) {
        const max = Math.max(...rows.map((row) => row[key] || 0), 0);
        return max ? Math.max(2, Math.round((100 * (value || 0)) / max)) : 0;
    }
}

registry.category("actions").add("club_management.analytics", ClubAnalytics);
