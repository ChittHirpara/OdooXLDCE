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
        this.action = useService("action");
        this.periods = PERIODS;
        this.notification = useService("notification");
        this.state = useState({ period: "month", data: null, loading: true, shareTo: "", sharing: false, shareMessage: "" });
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

    openLeave() {
        this.action.doAction("hr_holidays.hr_leave_action_action_approve_department");
    }

    downloadCsv() {
        window.location.href = `/club/report.csv?period=${this.state.period}`;
    }

    async emailReport() {
        if (this.state.sharing) {
            return;
        }
        this.state.sharing = true;
        this.state.shareMessage = "";
        try {
            const sent = await this.orm.call("club.dashboard", "email_report", [this.state.period, this.state.shareTo]);
            this.state.shareMessage = `Sent to ${sent}.`;
            this.notification.add(this.state.shareMessage, { type: "success" });
        } catch (err) {
            const message = (err.data && err.data.message) || "The report could not be sent.";
            this.notification.add(message, { type: "danger" });
        } finally {
            this.state.sharing = false;
        }
    }

    openReports() {
        this.action.doAction("club_management.action_club_analytics");
    }

    money(amount) {
        const symbol = this.state.data ? this.state.data.currency_symbol : "";
        return symbol + Math.round(amount || 0).toLocaleString("en-IN");
    }
}

registry.category("actions").add("club_management.owner_dashboard", OwnerDashboard);
