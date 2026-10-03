/**
 * Champions Club — Sports Club Management System
 * Court & Booking Service Layer (Simulating Odoo 19 Backend RPC)
 *
 * Models:
 * - club.court
 * - club.booking
 * - club.member
 */

const COURTS_DATA = [
  { id: 1, name: "Court 1", court_type: "padel", surface: "Panoramic Glass", is_indoor: false, base_rate: 800 },
  { id: 2, name: "Court 2", court_type: "tennis", surface: "Red Clay", is_indoor: false, base_rate: 600 },
  { id: 3, name: "Court 3", court_type: "tennis", surface: "DecoTurf Hard Court", is_indoor: true, base_rate: 600 },
  { id: 4, name: "Court 4", court_type: "badminton", surface: "Sprung Hardwood", is_indoor: true, base_rate: 400 },
];

const TIME_SLOTS_DATA = [
  "06:00", "06:30", "07:00", "07:30", "08:00", "08:30",
  "09:00", "09:30", "10:00", "10:30", "11:00", "11:30",
  "12:00", "12:30", "13:00", "13:30", "14:00", "14:30",
  "15:00", "15:30", "16:00", "16:30", "17:00", "17:30",
  "18:00", "18:30", "19:00", "19:30", "20:00", "20:30", "21:00"
];

const CURRENT_MEMBER = {
  id: 101,
  name: "Chitt Hirpara",
  plan: "Gold",
  planCode: "gold",
  status: "active", // "active" | "expired"
  memberId: "CC-MEM-00142",
};

// Seed schedule of booked slots by date
const AVAILABILITY_SCHEDULE = {
  // court_id: array of booked start times
  1: ["06:30", "08:00", "17:00", "19:00"],
  2: ["07:30", "18:30", "20:00"],
  3: ["06:00", "09:30", "16:00"],
  4: ["07:00", "18:00", "19:30"],
};

// User bookings storage
let USER_BOOKINGS = [
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
    state: "confirmed", // "confirmed" | "completed" | "cancelled"
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

/**
 * Service Layer: CourtBookingService
 * Can seamlessly switch from this simulated RPC to real Odoo 19 `useService("orm")`
 */
const CourtBookingService = {
  async getCourts() {
    return [...COURTS_DATA];
  },

  async getAvailability(dateStr) {
    // Return copy of availability map
    const copy = {};
    for (const [k, v] of Object.entries(AVAILABILITY_SCHEDULE)) {
      copy[k] = [...v];
    }
    return copy;
  },

  async calculateBookingPrice(courtId, dateStr, startTime, memberId = 101) {
    // Backend pricing logic
    const court = COURTS_DATA.find((c) => c.id === Number(courtId));
    if (!court) throw new Error("Court not found");

    const hour = parseInt(startTime.split(":")[0]);
    const isPrimeTime = hour >= 17 && hour <= 21;

    let price = 0;
    if (CURRENT_MEMBER.planCode === "gold") {
      price = isPrimeTime ? 300 : 0;
    } else if (CURRENT_MEMBER.planCode === "silver") {
      price = isPrimeTime ? 500 : 350;
    } else if (CURRENT_MEMBER.planCode === "junior") {
      price = isPrimeTime ? 400 : 200;
    } else {
      price = court.base_rate;
    }

    return {
      court_id: court.id,
      court_name: court.name,
      price: price,
      formatted_price: `₹${price}`,
      is_prime_time: isPrimeTime,
    };
  },

  async createBooking(courtId, dateStr, startTime, memberId = 101) {
    // 1. Expired membership check
    if (CURRENT_MEMBER.status === "expired") {
      return {
        success: false,
        error_code: "EXPIRED_MEMBERSHIP",
        message: "⚠ Your membership has expired. Please renew your membership."
      };
    }

    // 2. Daily booking limit check (max 2 confirmed bookings per day)
    const sameDayCount = USER_BOOKINGS.filter(
      (b) => b.date === dateStr && b.state === "confirmed"
    ).length;

    if (sameDayCount >= 2) {
      return {
        success: false,
        error_code: "DAILY_LIMIT",
        message: "⚠ You have reached your maximum of 2 bookings for today."
      };
    }

    // 3. Double booking check
    const bookedList = AVAILABILITY_SCHEDULE[courtId] || [];
    if (bookedList.includes(startTime)) {
      return {
        success: false,
        error_code: "DOUBLE_BOOKING",
        message: "⚠ This court is no longer available."
      };
    }

    // Calculate end time
    const [h, m] = startTime.split(":").map(Number);
    const endHour = h + 1;
    const endTime = `${String(endHour).padStart(2, "0")}:${String(m).padStart(2, "0")}`;

    const priceInfo = await this.calculateBookingPrice(courtId, dateStr, startTime, memberId);
    const court = COURTS_DATA.find((c) => c.id === Number(courtId));

    const nextId = `BK-0000${USER_BOOKINGS.length + 1}`;
    const newBooking = {
      id: nextId,
      court_id: court.id,
      court_name: court.name,
      date: dateStr,
      start_time: startTime,
      end_time: endTime,
      price: priceInfo.formatted_price,
      member_name: CURRENT_MEMBER.name,
      plan_name: `${CURRENT_MEMBER.plan} Member`,
      state: "confirmed",
    };

    // Update availability
    if (!AVAILABILITY_SCHEDULE[courtId]) {
      AVAILABILITY_SCHEDULE[courtId] = [];
    }
    AVAILABILITY_SCHEDULE[courtId].push(startTime);

    // Save to user bookings
    USER_BOOKINGS.unshift(newBooking);

    return {
      success: true,
      booking: newBooking
    };
  },

  async getMyBookings() {
    return [...USER_BOOKINGS];
  },

  async cancelBooking(bookingId) {
    const booking = USER_BOOKINGS.find((b) => b.id === bookingId);
    if (!booking) return false;

    booking.state = "cancelled";

    // Free up court slot in availability schedule
    if (AVAILABILITY_SCHEDULE[booking.court_id]) {
      AVAILABILITY_SCHEDULE[booking.court_id] = AVAILABILITY_SCHEDULE[booking.court_id].filter(
        (time) => time !== booking.start_time
      );
    }

    return true;
  }
};
