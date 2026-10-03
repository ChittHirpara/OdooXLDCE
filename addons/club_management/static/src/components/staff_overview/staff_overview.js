/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

export class StaffOverview extends Component {
    static template = "club_management.StaffOverview";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: null, loading: true });
        onWillStart(async () => {
            this.state.data = await this.orm.call("club.dashboard", "get_staff_overview", []);
            this.state.loading = false;
        });
    }

    open(xmlid) {
        this.action.doAction(xmlid);
    }
}

registry.category("actions").add("club_management.staff_overview", StaffOverview);
