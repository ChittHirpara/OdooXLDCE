/**
 * Champions Club — Sports Club Management System
 * Modular Frontend Architecture for Court + Booking Module
 *
 * Components:
 * - CourtBookingPage (Root Orchestrator)
 * - DateSelector
 * - CourtGrid
 * - CourtRow
 * - TimeSlot
 * - BookingConfirmationModal
 * - MyBookings
 * - BookingCard
 */

// ==========================================================================
// 1. TimeSlot Component
// ==========================================================================
const TimeSlot = {
  render(court, time, isBooked, isSelected) {
    let stateClass = "available";
    let indicatorText = "Open";

    if (isSelected) {
      stateClass = "selected";
      indicatorText = "✓";
    } else if (isBooked) {
      stateClass = "booked";
      indicatorText = "Booked";
    }

    return `
      <div class="cc-slot-cell ${stateClass}" 
           data-court-id="${court.id}" 
           data-time="${time}" 
           title="${court.name} at ${time}">
        <span class="cc-slot-indicator ${stateClass}">${indicatorText}</span>
      </div>
    `;
  }
};

// ==========================================================================
// 2. CourtRow Component
// ==========================================================================
const CourtRow = {
  render(court, timeSlots, bookedSlots = [], selectedSlot = null) {
    const slotsHtml = timeSlots
      .map((time) => {
        const isBooked = bookedSlots.includes(time);
        const isSelected = selectedSlot?.courtId === court.id && selectedSlot?.time === time;
        return TimeSlot.render(court, time, isBooked, isSelected);
      })
      .join("");

    return `
      <div class="cc-grid-row" data-court-id="${court.id}">
        <div class="cc-court-label-cell cc-sticky-col">
          <div class="cc-court-meta">
            <span class="cc-court-name">${court.name}</span>
            <span class="cc-court-surface">${court.surface}</span>
          </div>
        </div>
        ${slotsHtml}
      </div>
    `;
  }
};

// ==========================================================================
// 3. CourtGrid Component
// ==========================================================================
const CourtGrid = {
  render(courts, timeSlots, availabilityMap, selectedSlot) {
    const timeHeaderHtml = timeSlots
      .map((time) => `<div class="cc-time-header-cell"><span>${time}</span></div>`)
      .join("");

    const rowsHtml = courts
      .map((court) => {
        const booked = availabilityMap[court.id] || [];
        return CourtRow.render(court, timeSlots, booked, selectedSlot);
      })
      .join("");

    return `
      <div class="cc-court-grid-container">
        <div class="cc-court-grid">
          <div class="cc-grid-row cc-header-row">
            <div class="cc-court-label-cell cc-sticky-col">
              <span>Court</span>
            </div>
            ${timeHeaderHtml}
          </div>
          ${rowsHtml}
        </div>
      </div>
    `;
  }
};

// ==========================================================================
// 4. DateSelector Component
// ==========================================================================
const DateSelector = {
  render(selectedDate) {
    const todayStr = new Date().toISOString().split("T")[0];
    const tm = new Date();
    tm.setDate(tm.getDate() + 1);
    const tomorrowStr = tm.toISOString().split("T")[0];

    return `
      <div class="cc-date-selector">
        <button class="cc-date-pill ${selectedDate === todayStr ? "active" : ""}" data-date="${todayStr}">
          Today
        </button>
        <button class="cc-date-pill ${selectedDate === tomorrowStr ? "active" : ""}" data-date="${tomorrowStr}">
          Tomorrow
        </button>
        <div class="cc-date-picker-wrap">
          <input type="date" value="${selectedDate}" class="cc-date-input" id="court-date-picker" />
        </div>
      </div>
    `;
  }
};

// ==========================================================================
// 5. BookingCard Component
// ==========================================================================
const BookingCard = {
  render(booking) {
    const [y, m, d] = booking.date.split("-").map(Number);
    const dateObj = new Date(y, m - 1, d);
    const formattedDate = dateObj.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });

    return `
      <div class="cc-booking-card" data-booking-id="${booking.id}">
        <div class="cc-booking-card-top">
          <div class="cc-booking-court-info">
            <h3 class="cc-b-court-name">${booking.court_name}</h3>
            <span class="cc-b-id">${booking.id}</span>
          </div>
          <span class="cc-status-badge ${booking.state}">
            ${booking.state.toUpperCase()}
          </span>
        </div>

        <div class="cc-booking-time-details">
          <div class="cc-b-detail-row">
            <span class="cc-b-icon">🗓️</span>
            <span>${formattedDate}</span>
          </div>
          <div class="cc-b-detail-row">
            <span class="cc-b-icon">⏰</span>
            <span>${CourtBookingPage.formatTimeDisplay(booking.start_time)} – ${CourtBookingPage.formatTimeDisplay(booking.end_time)}</span>
          </div>
          <div class="cc-b-detail-row">
            <span class="cc-b-icon">💳</span>
            <span>Fee: <strong>${booking.price}</strong> (${booking.plan_name})</span>
          </div>
        </div>

        <div class="cc-booking-card-bottom">
          ${
            booking.state === "confirmed"
              ? `<button class="cc-btn-cancel-booking" data-action="cancel" data-id="${booking.id}">
                  Cancel Booking
                </button>`
              : `<span class="cc-inactive-note">Reservation ${booking.state}</span>`
          }
        </div>
      </div>
    `;
  }
};

// ==========================================================================
// 6. MyBookings Component
// ==========================================================================
const MyBookings = {
  render(bookings, activeTab = "upcoming") {
    const filtered = bookings.filter((b) => {
      if (activeTab === "upcoming") return b.state === "confirmed";
      if (activeTab === "completed") return b.state === "completed";
      if (activeTab === "cancelled") return b.state === "cancelled";
      return true;
    });

    const cardsHtml =
      filtered.length === 0
        ? `
        <div class="cc-empty-state">
          <span class="cc-empty-icon">📅</span>
          <h3>No ${activeTab} reservations</h3>
          <p>You have no court bookings currently under this tab.</p>
          <button class="cc-btn-primary" id="btn-empty-book-now">
            Reserve a Court Now
          </button>
        </div>
      `
        : `
        <div class="cc-bookings-grid">
          ${filtered.map((b) => BookingCard.render(b)).join("")}
        </div>
      `;

    return `
      <section class="cc-my-bookings-container">
        <div class="cc-page-header">
          <div>
            <h2 class="cc-page-title">My Bookings</h2>
            <p class="cc-page-subtitle">View and manage your upcoming court reservations.</p>
          </div>
        </div>

        <div class="cc-tabs-bar">
          <button class="cc-tab-pill ${activeTab === "upcoming" ? "active" : ""}" data-tab="upcoming">
            Upcoming
          </button>
          <button class="cc-tab-pill ${activeTab === "completed" ? "active" : ""}" data-tab="completed">
            Completed
          </button>
          <button class="cc-tab-pill ${activeTab === "cancelled" ? "active" : ""}" data-tab="cancelled">
            Cancelled
          </button>
        </div>

        ${cardsHtml}
      </section>
    `;
  }
};

// ==========================================================================
// 7. CourtBookingPage Component (Root Controller)
// ==========================================================================
const CourtBookingPage = {
  state: {
    currentView: "grid", // "grid" | "my_bookings"
    selectedDate: new Date().toISOString().split("T")[0],
    courts: [],
    availabilityMap: {},
    timeSlots: TIME_SLOTS_DATA,
    selectedSlot: null, // { courtId, courtName, surface, time, endTime }
    modalPrice: "₹0",
    isModalOpen: false,
    isConfirmedOpen: false,
    lastConfirmedBooking: null,
    isCancelModalOpen: false,
    bookingToCancel: null,
    activeBookingsTab: "upcoming",
    loading: false,
    error: null,
  },

  async init() {
    if (!this.state.courts || this.state.courts.length === 0) {
      this.state.courts = typeof COURTS_DATA !== "undefined" ? COURTS_DATA : [];
    }
    if (!this.state.availabilityMap || Object.keys(this.state.availabilityMap).length === 0) {
      this.state.availabilityMap = typeof AVAILABILITY_SCHEDULE !== "undefined" ? AVAILABILITY_SCHEDULE : {};
    }

    // Render immediately so there is zero blank screen
    this.render();
    this.bindEvents();

    try {
      this.state.loading = true;
      this.state.courts = await CourtBookingService.getCourts();
      this.state.availabilityMap = await CourtBookingService.getAvailability(this.state.selectedDate);
    } catch (e) {
      console.warn("Using offline court schedule:", e);
    } finally {
      this.state.loading = false;
      this.render();
    }
  },

  formatTimeDisplay(timeStr) {
    if (!timeStr) return "";
    const [h, m] = timeStr.split(":").map(Number);
    const period = h >= 12 ? "PM" : "AM";
    const hour12 = h % 12 || 12;
    return `${hour12}:${String(m).padStart(2, "0")} ${period}`;
  },

  formatDateDisplay(dateStr) {
    if (!dateStr) return "";
    const [y, m, d] = dateStr.split("-").map(Number);
    const dateObj = new Date(y, m - 1, d);
    return dateObj.toLocaleDateString("en-IN", { day: "2-digit", month: "long", year: "numeric" });
  },

  render() {
    const root = document.getElementById("booking-app-root");
    if (!root) return;

    const userBookings = USER_BOOKINGS;

    root.innerHTML = `
      <!-- Top Bar Navigation -->
      <header class="cc-header">
        <div class="cc-header-inner">
          <a href="#/memberships" class="cc-brand">
            <div class="cc-brand-emblem">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="2" x2="12" y2="22"/>
                <path d="M12 6a6 6 0 0 1 6 6 6 6 0 0 1-6 6"/>
              </svg>
            </div>
            <h1 class="cc-brand-title">Champions Club</h1>
          </a>

          <nav class="cc-nav">
            <a href="#/memberships" class="cc-nav-link">Memberships</a>
            <a href="#/courts" class="cc-nav-link active">Courts</a>
            <a href="#/shop" class="cc-nav-link">Shop</a>
            <a href="#/pos" class="cc-nav-link">Bar + POS</a>
          </nav>

          <div class="cc-header-right">
            <div class="cc-user-profile" title="Member: ${CURRENT_MEMBER.name}">
              <div class="cc-user-avatar">CH</div>
              <div class="cc-user-info">
                <span class="cc-user-name">${CURRENT_MEMBER.name}</span>
                <span class="cc-user-role">${CURRENT_MEMBER.plan} Member</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main class="cc-main-container">
        <!-- View Switcher -->
        <div class="cc-view-switcher">
          <button class="cc-view-btn ${this.state.currentView === "grid" ? "active" : ""}" id="btn-view-grid">
            Book a Court
          </button>
          <button class="cc-view-btn ${this.state.currentView === "my_bookings" ? "active" : ""}" id="btn-view-bookings">
            My Bookings
            <span class="cc-counter-pill">${userBookings.length}</span>
          </button>
        </div>

        ${
          this.state.currentView === "grid"
            ? this.renderGridView()
            : MyBookings.render(userBookings, this.state.activeBookingsTab)
        }

        <!-- Modals -->
        ${this.renderModals()}
      </main>
    `;
  },

  renderGridView() {
    return `
      <section class="cc-page-header">
        <div class="cc-header-text">
          <h2 class="cc-page-title">Book a Court</h2>
          <p class="cc-page-subtitle">Choose a court and time that works for you.</p>
        </div>
        ${DateSelector.render(this.state.selectedDate)}
      </section>

      ${
        this.state.error
          ? `
        <div class="cc-error-banner">
          <div class="cc-error-content">
            <span class="cc-error-icon">⚠</span>
            <span>${this.state.error}</span>
          </div>
          <button class="cc-error-dismiss" id="btn-dismiss-error">✕</button>
        </div>
      `
          : ""
      }

      <div class="cc-grid-legend">
        <div class="cc-legend-item">
          <span class="cc-legend-box available"></span>
          <span>Available</span>
        </div>
        <div class="cc-legend-item">
          <span class="cc-legend-box booked"></span>
          <span>Booked</span>
        </div>
        <div class="cc-legend-item">
          <span class="cc-legend-box selected"></span>
          <span>Selected</span>
        </div>
        <div class="cc-legend-note">
          <span>* 1 hour per booking • Starts every 30 mins</span>
        </div>
      </div>

      ${CourtGrid.render(
        this.state.courts,
        this.state.timeSlots,
        this.state.availabilityMap,
        this.state.selectedSlot
      )}

      <!-- Selected Slot Floating Action Bar -->
      ${
        this.state.selectedSlot
          ? `
        <div class="cc-selection-bar">
          <div class="cc-selection-details">
            <div class="cc-selection-icon">🎾</div>
            <div class="cc-selection-text">
              <div class="cc-selection-title">
                ${this.state.selectedSlot.courtName}
                <span class="cc-dot-divider">•</span>
                ${this.formatTimeDisplay(this.state.selectedSlot.time)} – ${this.formatTimeDisplay(this.state.selectedSlot.endTime)}
              </div>
              <div class="cc-selection-subtitle">
                ${this.formatDateDisplay(this.state.selectedDate)}
                <span class="cc-dot-divider">•</span>
                <span class="cc-tag-gold">${CURRENT_MEMBER.plan} Member</span>
              </div>
            </div>
          </div>

          <div class="cc-selection-actions">
            <button class="cc-btn-secondary" id="btn-clear-selection">Clear</button>
            <button class="cc-btn-primary" id="btn-continue-booking">
              Continue
              <svg width="15" height="15" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z" clip-rule="evenodd"/>
              </svg>
            </button>
          </div>
        </div>
      `
          : ""
      }
    `;
  },

  renderModals() {
    let html = "";

    // 1. BookingConfirmationModal
    if (this.state.isModalOpen && this.state.selectedSlot) {
      html += `
        <div class="cc-modal-backdrop" id="modal-backdrop-confirmation">
          <div class="cc-modal-dialog">
            <button class="cc-modal-close" id="btn-close-modal">✕</button>

            <h3 class="cc-modal-title">Confirm Court Reservation</h3>
            <p class="cc-modal-subtitle">Review your reservation details before confirming.</p>

            <div class="cc-modal-summary-box">
              <div class="cc-summary-row">
                <span class="cc-label">Court:</span>
                <span class="cc-val bold">${this.state.selectedSlot.courtName} (${this.state.selectedSlot.surface})</span>
              </div>
              <div class="cc-summary-row">
                <span class="cc-label">Date:</span>
                <span class="cc-val">${this.formatDateDisplay(this.state.selectedDate)}</span>
              </div>
              <div class="cc-summary-row">
                <span class="cc-label">Time:</span>
                <span class="cc-val bold">${this.formatTimeDisplay(this.state.selectedSlot.time)} – ${this.formatTimeDisplay(this.state.selectedSlot.endTime)} (1 hr)</span>
              </div>
              <div class="cc-summary-row">
                <span class="cc-label">Member:</span>
                <span class="cc-val">${CURRENT_MEMBER.name}</span>
              </div>
              <div class="cc-summary-row">
                <span class="cc-label">Plan:</span>
                <span class="cc-val"><span class="cc-tag-gold">${CURRENT_MEMBER.plan} Member</span></span>
              </div>
              <div class="cc-summary-divider"></div>
              <div class="cc-summary-row cc-price-row">
                <span class="cc-label">Total Price:</span>
                <span class="cc-price-highlight">${this.state.modalPrice}</span>
              </div>
            </div>

            <div class="cc-modal-footer">
              <button class="cc-btn-secondary" id="btn-modal-cancel">Cancel</button>
              <button class="cc-btn-primary" id="btn-modal-confirm">Confirm Booking</button>
            </div>
          </div>
        </div>
      `;
    }

    // 2. Confirmed Screen Modal
    if (this.state.isConfirmedOpen && this.state.lastConfirmedBooking) {
      const b = this.state.lastConfirmedBooking;
      html += `
        <div class="cc-modal-backdrop">
          <div class="cc-modal-dialog cc-confirmed-dialog">
            <div class="cc-confirmed-badge">✓</div>
            <h3 class="cc-confirmed-title">Booking Confirmed</h3>
            
            <div class="cc-confirmed-card">
              <h4 class="cc-conf-court">${b.court_name}</h4>
              <div class="cc-conf-date">${this.formatDateDisplay(b.date)}</div>
              <div class="cc-conf-time">${this.formatTimeDisplay(b.start_time)} – ${this.formatTimeDisplay(b.end_time)}</div>
              <div class="cc-conf-id">Booking ID: <strong>${b.id}</strong></div>
            </div>

            <button class="cc-btn-primary cc-btn-full" id="btn-done-confirmation">
              Done
            </button>
          </div>
        </div>
      `;
    }

    // 3. Cancel Dialog Modal
    if (this.state.isCancelModalOpen && this.state.bookingToCancel) {
      const b = this.state.bookingToCancel;
      html += `
        <div class="cc-modal-backdrop" id="modal-backdrop-cancel">
          <div class="cc-modal-dialog cc-cancel-dialog">
            <h3 class="cc-modal-title">Cancel this booking?</h3>
            <p class="cc-modal-subtitle">
              Are you sure you want to cancel your reservation for 
              <strong>${b.court_name}</strong> on 
              <strong>${this.formatDateDisplay(b.date)}</strong>?
              The court slot will become immediately available for other members.
            </p>

            <div class="cc-modal-footer">
              <button class="cc-btn-secondary" id="btn-keep-booking">Keep Booking</button>
              <button class="cc-btn-danger" id="btn-confirm-cancel">Cancel Booking</button>
            </div>
          </div>
        </div>
      `;
    }

    return html;
  },

  bindEvents() {
    const root = document.getElementById("booking-app-root");
    if (!root) return;

    root.addEventListener("click", async (e) => {
      // 1. View Switching
      if (e.target.closest("#btn-view-grid")) {
        this.state.currentView = "grid";
        this.render();
        return;
      }
      if (e.target.closest("#btn-view-bookings")) {
        this.state.currentView = "my_bookings";
        this.render();
        return;
      }
      if (e.target.closest("#btn-empty-book-now")) {
        this.state.currentView = "grid";
        this.render();
        return;
      }

      // 2. Date Selection (Today / Tomorrow)
      const datePill = e.target.closest(".cc-date-pill");
      if (datePill) {
        const dateStr = datePill.getAttribute("data-date");
        this.changeDate(dateStr);
        return;
      }

      // 3. Slot Click inside Grid
      const slotCell = e.target.closest(".cc-slot-cell");
      if (slotCell && !slotCell.classList.contains("booked")) {
        const courtId = Number(slotCell.getAttribute("data-court-id"));
        const time = slotCell.getAttribute("data-time");
        this.handleSlotClick(courtId, time);
        return;
      }

      // 4. Clear Selection Button
      if (e.target.closest("#btn-clear-selection")) {
        this.state.selectedSlot = null;
        this.render();
        return;
      }

      // 5. Continue to Modal Button
      if (e.target.closest("#btn-continue-booking")) {
        if (!this.state.selectedSlot) return;
        // Fetch price dynamically from backend/service
        const priceInfo = await CourtBookingService.calculateBookingPrice(
          this.state.selectedSlot.courtId,
          this.state.selectedDate,
          this.state.selectedSlot.time,
          CURRENT_MEMBER.id
        );
        this.state.modalPrice = priceInfo.formatted_price;
        this.state.isModalOpen = true;
        this.render();
        return;
      }

      // 6. Close / Cancel Modal
      if (e.target.closest("#btn-close-modal") || e.target.closest("#btn-modal-cancel")) {
        this.state.isModalOpen = false;
        this.render();
        return;
      }

      // 7. Confirm Booking Button
      if (e.target.closest("#btn-modal-confirm")) {
        await this.handleConfirmBooking();
        return;
      }

      // 8. Dismiss Confirmation Screen ("Done")
      if (e.target.closest("#btn-done-confirmation")) {
        this.state.isConfirmedOpen = false;
        this.state.selectedSlot = null;
        this.render();
        return;
      }

      // 9. Cancel Booking Prompt
      const btnCancel = e.target.closest("button[data-action='cancel']");
      if (btnCancel) {
        const id = btnCancel.getAttribute("data-id");
        this.state.bookingToCancel = USER_BOOKINGS.find((b) => b.id === id);
        this.state.isCancelModalOpen = true;
        this.render();
        return;
      }

      // 10. Keep Booking (dismiss cancel dialog)
      if (e.target.closest("#btn-keep-booking")) {
        this.state.isCancelModalOpen = false;
        this.state.bookingToCancel = null;
        this.render();
        return;
      }

      // 11. Confirm Cancel Booking
      if (e.target.closest("#btn-confirm-cancel")) {
        await this.handleCancelBooking();
        return;
      }

      // 12. Bookings Tab Switcher
      const tabPill = e.target.closest(".cc-tab-pill");
      if (tabPill) {
        this.state.activeBookingsTab = tabPill.getAttribute("data-tab");
        this.render();
        return;
      }

      // 13. Dismiss error banner
      if (e.target.closest("#btn-dismiss-error")) {
        this.state.error = null;
        this.render();
        return;
      }
    });

    // Date Picker Input change listener
    root.addEventListener("change", (e) => {
      if (e.target && e.target.id === "court-date-picker") {
        this.changeDate(e.target.value);
      }
    });
  },

  async changeDate(dateStr) {
    if (this.state.selectedDate === dateStr) return;
    this.state.selectedDate = dateStr;
    this.state.selectedSlot = null;
    this.state.loading = true;
    this.render();

    this.state.availabilityMap = await CourtBookingService.getAvailability(dateStr);
    this.state.loading = false;
    this.render();
  },

  handleSlotClick(courtId, time) {
    // If clicking already selected, deselect
    if (this.state.selectedSlot?.courtId === courtId && this.state.selectedSlot?.time === time) {
      this.state.selectedSlot = null;
      this.render();
      return;
    }

    const court = this.state.courts.find((c) => c.id === courtId);
    const [h, m] = time.split(":").map(Number);
    const endHour = h + 1;
    const endTime = `${String(endHour).padStart(2, "0")}:${String(m).padStart(2, "0")}`;

    this.state.selectedSlot = {
      courtId,
      courtName: court.name,
      surface: court.surface,
      time,
      endTime,
    };

    this.render();
  },

  async handleConfirmBooking() {
    this.state.loading = true;
    this.state.error = null;

    const res = await CourtBookingService.createBooking(
      this.state.selectedSlot.courtId,
      this.state.selectedDate,
      this.state.selectedSlot.time,
      CURRENT_MEMBER.id
    );

    this.state.loading = false;

    if (!res.success) {
      this.state.error = res.message;
      this.state.isModalOpen = false;
      this.render();
      return;
    }

    // Refresh availability
    this.state.availabilityMap = await CourtBookingService.getAvailability(this.state.selectedDate);
    this.state.lastConfirmedBooking = res.booking;
    this.state.isModalOpen = false;
    this.state.isConfirmedOpen = true;

    this.render();
  },

  async handleCancelBooking() {
    if (!this.state.bookingToCancel) return;

    await CourtBookingService.cancelBooking(this.state.bookingToCancel.id);
    this.state.availabilityMap = await CourtBookingService.getAvailability(this.state.selectedDate);

    this.state.isCancelModalOpen = false;
    this.state.bookingToCancel = null;
    this.render();
  }
};

window.CourtBookingPage = CourtBookingPage;

document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("booking-app-root")) {
    CourtBookingPage.init();
  }
});
