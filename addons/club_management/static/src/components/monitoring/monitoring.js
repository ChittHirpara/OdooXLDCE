/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

const BADGES = { ok: "text-bg-success", warn: "text-bg-warning", alert: "text-bg-danger" };
const WORDS = { ok: "All clear", warn: "Needs attention", alert: "Action needed" };

export class ClubMonitoring extends Component {
    static template = "club_management.ClubMonitoring";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: null, loading: true });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.data = await this.orm.call("club.dashboard", "get_monitoring", []);
        this.state.loading = false;
    }

    badge(status) {
        return BADGES[status];
    }

    word(status) {
        return WORDS[status];
    }

    open(check) {
        this.action.doAction(check.action);
    }
}

registry.category("actions").add("club_management.monitoring", ClubMonitoring);
