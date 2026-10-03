/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";

const CLUB_TZ = "Asia/Kolkata";
const FRIDAY_NOTE =
    "Friday is social play: several players share a court, so a slot stays open until the court is full.";

const escapeHtml = (value) =>
    String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/** Current wall-clock time at the club as "HH:MM", to grey out slots that have passed today. */
function clubNow() {
    return new Intl.DateTimeFormat("en-GB", {
        timeZone: CLUB_TZ, hour: "2-digit", minute: "2-digit", hour12: false,
    }).format(new Date());
}

function clubToday() {
    return new Intl.DateTimeFormat("en-CA", { timeZone: CLUB_TZ }).format(new Date());
}

publicWidget.registry.ClubCourtAvailability = publicWidget.Widget.extend({
    selector: ".club-availability",
    events: {
        "change .js-date": "_load",
        "change .js-sport": "_load",
    },

    start() {
        this.gridEl = this.el.querySelector(".js-grid");
        this.noteEl = this.el.querySelector(".js-note");
        return this._super(...arguments).then(() => this._load());
    },

    async _load() {
        const date = this.el.querySelector(".js-date").value || clubToday();
        const sport = this.el.querySelector(".js-sport").value;
        const url = new URL(this.el.dataset.endpoint, window.location.origin);
        url.searchParams.set("date", date);
        if (sport) {
            url.searchParams.set("sport", sport);
        }
        this.gridEl.innerHTML = '<p class="club-muted">Loading availability…</p>';
        try {
            const response = await fetch(url, { headers: { Accept: "application/json" } });
            if (!response.ok) {
                throw new Error(response.status);
            }
            this._render(await response.json());
        } catch (error) {
            this.gridEl.innerHTML =
                '<p class="club-error">We could not load availability. Please try again in a moment.</p>';
        }
    },

    _render(data) {
        const today = clubToday();
        const now = clubNow();
        const courts = data.courts || [];
        const social = courts.some((court) => court.is_social);
        this.noteEl.textContent = FRIDAY_NOTE;
        this.noteEl.classList.toggle("d-none", !social);
        if (!courts.length) {
            this.gridEl.innerHTML = '<p class="club-muted">No courts match that choice.</p>';
            return;
        }
        this.gridEl.innerHTML = courts.map((court) => this._renderCourt(court, data.date, today, now)).join("");
    },

    _renderCourt(court, date, today, now) {
        const slots = court.slots
            .map((slot) => {
                const passed = date === today && slot.start <= now;
                if (passed) {
                    return `<span class="club-slot club-slot-off" title="Passed">${escapeHtml(slot.start)}</span>`;
                }
                if (!slot.available) {
                    return `<span class="club-slot club-slot-booked" title="Booked">${escapeHtml(slot.start)}</span>`;
                }
                const message = `${court.court} on ${date} at ${slot.start}`;
                const href =
                    `/join?type=court&sport=${encodeURIComponent(court.sport)}` +
                    `&message=${encodeURIComponent("I would like to request " + message + ".")}`;
                const left = court.is_social ? `<small>${slot.places_left} left</small>` : "";
                return `<a class="club-slot club-slot-free" href="${href}" title="Request ${escapeHtml(message)}">` +
                    `${escapeHtml(slot.start)}${left}</a>`;
            })
            .join("");
        return `<div class="club-court-row" data-court="${court.court_id}">
            <div class="club-court-head">
                <h5>${escapeHtml(court.court)}</h5>
                <span class="club-muted">${escapeHtml(court.sport)}${court.is_social ? " · social play" : ""} · ₹${Math.round(court.list_price)}/hr</span>
            </div>
            <div class="club-slots">${slots}</div>
        </div>`;
    },
});

export default publicWidget.registry.ClubCourtAvailability;
