/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

// Seed Courts matching Champions Club Facility
const DEFAULT_COURTS = [
    { id: 1, name: "Court 1", court_type: "padel", surface: "Panoramic Glass", is_indoor: false, base_rate: 800 },
    { id: 2, name: "Court 2", court_type: "tennis", surface: "Red Clay", is_indoor: false, base_rate: 600 },
    { id: 3, name: "Court 3", court_type: "tennis", surface: "DecoTurf Hard Court", is_indoor: true, base_rate: 600 },
    { id: 4, name: "Court 4", court_type: "badminton", surface: "Sprung Hardwood", is_indoor: true, base_rate: 400 },
];

// 30-min time slots from 06:00 to 21:30 (Each booking = 1 hr)
const TIME_SLOTS = [
    "06:00", "06:30", "07:00", "07:30", "08:00", "08:30",
    "09:00", "09:30", "10:00", "10:30", "11:00", "11:30",
    "12:00", "12:30", "13:00", "13:30", "14:00", "14:30",
    "15:00", "15:30", "16:00", "16:30", "17:00", "17:30",
    "18:00", "18:30", "19:00", "19:30", "20:00", "20:30", "21:00"
];

// Current Member session
const CURRENT_MEMBER = {
    id: 101,
    name: "Chitt Hirpara",
    plan: "Gold",
    planCode: "gold",
    status: "active",
    memberId: "CC-MEM-00142",
};

// Initial Mock Bookings
let MOCK_EXISTING_BOOKINGS = [
    {
        id: "BK-00001",
        court_id: 2,
        court_name: "Court 2",
        date: new Date().toISOString().split("T")[0],
        start_time: "18:30",
        end_time: "19:30",
        price: "₹300",
        member_name: "Chitt Hirpara",
        plan_name: "Gold Member",
        state: "confirmed",
    },
    {
        id: "BK-00002",
        court_id: 1,
        court_name: "Court 1",
        date: new Date(Date.now() + 86400000).toISOString().split("T")[0],
        start_time: "07:30",
        end_time: "08:30",
        price: "₹0",
        member_name: "Chitt Hirpara",
        plan_name: "Gold Member",
        state: "confirmed",
    }
];

// Seed booked slot schedule by date
const MOCK_AVAILABILITY_MAP = {
    // court_id: array of booked start times
    1: ["06:30", "08:00", "17:00", "19:00"],
    2: ["07:30", "18:30", "20:00"],
    3: ["06:00", "09:30", "16:00"],
    4: ["07:00", "18:00", "19:30"],
};

export class CourtBookingPage extends Component {
    static template = "champions_club.CourtBookingPage";

    setup() {
        try {
            this.orm = useService("orm");
            this.notification = useService("notification");
        } catch {
            this.orm = null;
            this.notification = null;
        }

        const todayStr = new Date().toISOString().split("T")[0];

        this.state = useState({
            currentView: "grid", // "grid" | "my_bookings"
            selectedDate: todayStr,
            timeSlots: TIME_SLOTS,
            courts: DEFAULT_COURTS,
            availability: { ...MOCK_AVAILABILITY_MAP },
            
            // Slot selection
            selectedCourt: null,
            selectedSlot: null,
            slotEndTime: null,
            
            // Modal & Confirmation
            isModalOpen: false,
            modalPrice: "₹0",
            isConfirmationOpen: false,
            lastConfirmedBooking: null,

            // My Bookings
            myBookings: [...MOCK_EXISTING_BOOKINGS],
            bookingsTab: "upcoming", // "upcoming" | "completed" | "cancelled"
            isCancelModalOpen: false,
            bookingToCancel: null,

            // Status states
            loading: false,
            error: null,
        });

        onWillStart(async () => {
            await this.loadCourtsAndAvailability();
        });
    }

    get todayDateStr() {
        return new Date().toISOString().split("T")[0];
    }

    get tomorrowDateStr() {
        const tm = new Date();
        tm.setDate(tm.getDate() + 1);
        return tm.toISOString().split("T")[0];
    }

    get member() {
        return CURRENT_MEMBER;
    }

    get filteredMyBookings() {
        return this.state.myBookings.filter((b) => {
            if (this.state.bookingsTab === "upcoming") return b.state === "confirmed";
            if (this.state.bookingsTab === "completed") return b.state === "completed";
            if (this.state.bookingsTab === "cancelled") return b.state === "cancelled";
            return true;
        });
    }

    async loadCourtsAndAvailability() {
        this.state.loading = true;
        this.state.error = null;

        if (this.orm) {
            try {
                const courts = await this.orm.call("club.court", "get_courts_list", []);
                if (courts && courts.length) this.state.courts = courts;

                const avail = await this.orm.call("club.booking", "get_availability", [this.state.selectedDate]);
                if (avail) this.state.availability = avail;
            } catch (err) {
                console.warn("[CourtBooking] Offline/mock mode:", err);
            }
        }
        
        // Simulating 180ms network latency for smooth UI feel
        setTimeout(() => {
            this.state.loading = false;
        }, 180);
    }

    // Date selection
    selectDate(dateStr) {
        if (this.state.selectedDate === dateStr) return;
        this.state.selectedDate = dateStr;
        this.clearSelection();
        this.loadCourtsAndAvailability();
    }

    clearSelection() {
        this.state.selectedCourt = null;
        this.state.selectedSlot = null;
        this.state.slotEndTime = null;
    }

    // Slot click handler
    handleSlotClick(court, time) {
        // If slot is booked, ignore
        if (this.isSlotBooked(court.id, time)) return;

        // If clicking already selected, toggle off
        if (this.state.selectedCourt?.id === court.id && this.state.selectedSlot === time) {
            this.clearSelection();
            return;
        }

        // Set selected court and slot
        this.state.selectedCourt = court;
        this.state.selectedSlot = time;

        // Calculate 1-hour end time (e.g. 18:30 -> 19:30)
        const [h, m] = time.split(":").map(Number);
        const endHour = h + 1;
        this.state.slotEndTime = `${String(endHour).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
    }

    isSlotBooked(courtId, time) {
        const booked = this.state.availability[courtId] || [];
        return booked.includes(time);
    }

    isSlotSelected(courtId, time) {
        return this.state.selectedCourt?.id === courtId && this.state.selectedSlot === time;
    }

    formatTimeDisplay(timeStr) {
        if (!timeStr) return "";
        const [h, m] = timeStr.split(":").map(Number);
        const period = h >= 12 ? "PM" : "AM";
        const hour12 = h % 12 || 12;
        return `${hour12}:${String(m).padStart(2, "0")} ${period}`;
    }

    formatDateDisplay(dateStr) {
        if (!dateStr) return "";
        const [y, m, d] = dateStr.split("-").map(Number);
        const dateObj = new Date(y, m - 1, d);
        return dateObj.toLocaleDateString("en-IN", { day: "2-digit", month: "long", year: "numeric" });
    }

    // Proceed to Confirmation Modal
    async openBookingModal() {
        if (!this.state.selectedCourt || !this.state.selectedSlot) return;

        this.state.loading = true;

        // Fetch price dynamically from backend/RPC
        if (this.orm) {
            try {
                const priceInfo = await this.orm.call("club.booking", "calculate_booking_price", [
                    this.state.selectedCourt.id,
                    this.state.selectedDate,
                    this.state.selectedSlot,
                    CURRENT_MEMBER.id
                ]);
                this.state.modalPrice = priceInfo.formatted_price;
            } catch (err) {
                this.state.modalPrice = this.calculateMockPrice();
            }
        } else {
            this.state.modalPrice = this.calculateMockPrice();
        }

        this.state.loading = false;
        this.state.isModalOpen = true;
    }

    calculateMockPrice() {
        const hour = parseInt(this.state.selectedSlot.split(":")[0]);
        const isPrimeTime = hour >= 17 && hour <= 21;
        if (CURRENT_MEMBER.planCode === "gold") {
            return isPrimeTime ? "₹300" : "₹0";
        } else if (CURRENT_MEMBER.planCode === "silver") {
            return isPrimeTime ? "₹500" : "₹350";
        }
        return "₹800";
    }

    closeModal() {
        this.state.isModalOpen = false;
    }

    // Confirm Booking Action
    async confirmBooking() {
        this.state.loading = true;
        this.state.error = null;

        // Check simulated daily booking limits
        const sameDayCount = this.state.myBookings.filter(
            (b) => b.date === this.state.selectedDate && b.state === "confirmed"
        ).length;

        if (sameDayCount >= 2) {
            this.state.loading = false;
            this.state.isModalOpen = false;
            this.state.error = "⚠ You have reached your maximum of 2 bookings for today.";
            return;
        }

        // Check double booking simulation
        if (this.isSlotBooked(this.state.selectedCourt.id, this.state.selectedSlot)) {
            this.state.loading = false;
            this.state.isModalOpen = false;
            this.state.error = "⚠ This court is no longer available.";
            return;
        }

        let newBooking = null;

        if (this.orm) {
            try {
                const res = await this.orm.call("club.booking", "create_booking_api", [
                    this.state.selectedCourt.id,
                    this.state.selectedDate,
                    this.state.selectedSlot,
                    CURRENT_MEMBER.id,
                ]);
                if (res.success) {
                    newBooking = res.booking;
                } else {
                    this.state.error = res.message || "Something went wrong. Please try again.";
                    this.state.isModalOpen = false;
                    this.state.loading = false;
                    return;
                }
            } catch (err) {
                this.state.error = "Something went wrong. Please try again.";
                this.state.isModalOpen = false;
                this.state.loading = false;
                return;
            }
        }

        // Local State update
        if (!newBooking) {
            const nextNum = this.state.myBookings.length + 1;
            newBooking = {
                id: `BK-0000${nextNum}`,
                court_id: this.state.selectedCourt.id,
                court_name: this.state.selectedCourt.name,
                date: this.state.selectedDate,
                start_time: this.state.selectedSlot,
                end_time: this.state.slotEndTime,
                price: this.state.modalPrice,
                member_name: CURRENT_MEMBER.name,
                plan_name: "Gold Member",
                state: "confirmed",
            };
        }

        // Add to booked availability
        const courtId = this.state.selectedCourt.id;
        if (!this.state.availability[courtId]) {
            this.state.availability[courtId] = [];
        }
        this.state.availability[courtId].push(this.state.selectedSlot);

        // Add to My Bookings
        this.state.myBookings.unshift(newBooking);

        this.state.lastConfirmedBooking = newBooking;
        this.state.isModalOpen = false;
        this.state.isConfirmationOpen = true;
        this.state.loading = false;
    }

    dismissConfirmation() {
        this.state.isConfirmationOpen = false;
        this.clearSelection();
    }

    // Cancel Booking workflow
    promptCancelBooking(booking) {
        this.state.bookingToCancel = booking;
        this.state.isCancelModalOpen = true;
    }

    closeCancelModal() {
        this.state.isCancelModalOpen = false;
        this.state.bookingToCancel = null;
    }

    async confirmCancelBooking() {
        const b = this.state.bookingToCancel;
        if (!b) return;

        this.state.loading = true;

        if (this.orm && b.odoo_id) {
            try {
                await this.orm.call("club.booking", "action_cancel", [[b.odoo_id]]);
            } catch (err) {
                console.warn("[Cancel booking RPC error]:", err);
            }
        }

        // Update booking state in list
        b.state = "cancelled";

        // Free up slot in availability grid
        if (this.state.availability[b.court_id]) {
            this.state.availability[b.court_id] = this.state.availability[b.court_id].filter(
                (time) => time !== b.start_time
            );
        }

        this.state.loading = false;
        this.closeCancelModal();

        if (this.notification) {
            this.notification.add("Booking cancelled. The court slot is now available.", { type: "info" });
        }
    }

    switchTab(tab) {
        this.state.bookingsTab = tab;
    }

    setView(view) {
        this.state.currentView = view;
        this.state.error = null;
    }
}

registry.category("actions").add("champions_club.court_booking", CourtBookingPage);
