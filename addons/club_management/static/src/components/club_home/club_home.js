/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

// What the team can do from here, grouped the way a day at the club goes. `count` names a number
// shown on the tile; `manager` tiles only appear for club managers.
const GROUPS = [
    {
        title: "At the front desk",
        tiles: [
            { icon: "fa-calendar-check-o", name: "Book a court", text: "See free slots and book for a member or a walk-in.", action: "club_management.action_club_court_booking_ui", count: "bookings_today", countLabel: "today" },
            { icon: "fa-shopping-bag", name: "Pro-Shop", text: "Sell rackets, balls and gear. Member prices apply.", action: "club_management.action_club_shop_ui" },
            { icon: "fa-coffee", name: "Bar & POS", text: "Take a bar or cafeteria order and settle the tab.", action: "club_management.action_club_bar_pos_ui" },
            { icon: "fa-id-card-o", name: "Membership plans", text: "Compare Gold, Silver and Junior at a glance.", action: "club_management.action_club_membership_plans_ui" },
        ],
    },
    {
        title: "Members and enquiries",
        tiles: [
            { icon: "fa-users", name: "Members", text: "Everyone with a membership, with status and expiry.", action: "club_management.action_club_members", count: "expiring", countLabel: "expiring soon" },
            { icon: "fa-inbox", name: "Enquiries", text: "New people asking to join. Press Join to make them members.", action: "club_management.action_club_enquiries", count: "open_enquiries", countLabel: "open" },
            { icon: "fa-calendar", name: "All bookings", text: "Every court booking: move, cancel or invoice.", action: "club_management.action_club_booking" },
            { icon: "fa-list-alt", name: "Bar & shop orders", text: "What was sold, to whom and how it was paid.", action: "club_management.action_club_order" },
        ],
    },
    {
        title: "Help and feedback",
        tiles: [
            { icon: "fa-life-ring", name: "Support tickets", text: "Complaints, booking and order issues, refund requests.", action: "club_management.action_club_tickets", count: "open_tickets", countLabel: "open" },
            { icon: "fa-star-o", name: "Feedback and ratings", text: "What members think of the courts, the bar and the shop.", action: "club_management.action_club_feedback" },
        ],
    },
    {
        title: "For the owner",
        manager: true,
        tiles: [
            { icon: "fa-tachometer", name: "Owner dashboard", text: "Revenue, members and today's sales.", action: "club_management.action_club_owner_dashboard" },
            { icon: "fa-bar-chart", name: "Reports & analytics", text: "Monthly revenue, tiers, utilization and best sellers.", action: "club_management.action_club_analytics" },
            { icon: "fa-heartbeat", name: "System monitoring", text: "What needs attention: payments, stock, expiries, shifts.", action: "club_management.action_club_monitoring", count: "low_stock", countLabel: "low stock" },
            { icon: "fa-user-circle-o", name: "Staff", text: "Team, shifts, roles and who did what.", action: "club_management.action_club_staff_overview" },
        ],
    },
    {
        title: "Setup",
        manager: true,
        tiles: [
            { icon: "fa-th-large", name: "Courts", text: "Courts, prices per hour and opening hours.", action: "club_management.action_club_court" },
            { icon: "fa-sliders", name: "Plan settings", text: "Prices, validity and discounts of each plan.", action: "club_management.action_club_membership_plan" },
            { icon: "fa-cube", name: "Products", text: "Shop and bar products, prices and pictures.", action: "club_management.action_club_products" },
            { icon: "fa-envelope-o", name: "Notifications", text: "The emails members receive.", action: "club_management.action_club_email_templates" },
        ],
    },
];

export class ClubHome extends Component {
    static template = "club_management.ClubHome";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: null });
        onWillStart(async () => {
            this.state.data = await this.orm.call("club.dashboard", "get_home", []);
        });
    }

    get groups() {
        const manager = this.state.data && this.state.data.is_manager;
        return GROUPS.filter((group) => !group.manager || manager);
    }

    count(tile) {
        return tile.count ? this.state.data.counts[tile.count] : null;
    }

    open(tile) {
        this.action.doAction(tile.action);
    }
}

registry.category("actions").add("club_management.club_home", ClubHome);
