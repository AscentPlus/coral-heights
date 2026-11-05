/**
 * Hotel Coral Heights — Site JavaScript
 * ─────────────────────────────────────
 * Alpine.js CSP-safe component registrations,
 * scroll-reveal animations, staggered children reveal,
 * and parallax background handling.
 */

/* ── Alpine.js Named Components (CSP-safe) ───────────────── */

document.addEventListener('alpine:init', () => {

  // Helper to format dates from YYYY-MM-DD to DD-MM-YYYY
  function formatDateDMY(dateStr) {
    if (!dateStr) return '';
    const str = String(dateStr).trim();
    const match = str.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
    if (match) {
      const day = match[3].padStart(2, '0');
      const month = match[2].padStart(2, '0');
      const year = match[1];
      return `${day}-${month}-${year}`;
    }
    return str;
  }

  // Navigation bar: scroll-aware + mobile menu toggle
  Alpine.data('navState', () => ({
    scrolled: false,
    mobileOpen: false,

    init() {
      const updateScroll = () => {
        this.scrolled = (window.pageYOffset || document.documentElement.scrollTop) > 50;
      };
      window.addEventListener('scroll', updateScroll, { passive: true });
      updateScroll();
    },

    get navClasses() {
      return this.scrolled ? 'nav-solid' : '';
    },

    get isMobileClosed() {
      return !this.mobileOpen;
    },

    toggleMobile() {
      this.mobileOpen = !this.mobileOpen;
    },

    closeMobile() {
      this.mobileOpen = false;
    }
  }));

  // Shared Alpine store for room details modal
  Alpine.store('roomDetails', {
    open: false,
    activeSlug: '',

    openRoom(slug) {
      this.activeSlug = slug;
      this.open = true;
      document.body.classList.add('overflow-hidden');
    },

    closeModal() {
      this.open = false;
      this.activeSlug = '';
      document.body.classList.remove('overflow-hidden');
    }
  });

  // CSP-safe bridge component for room cards
  Alpine.data('roomCard', () => ({
    openDetails() {
      const card = this.$el.closest('[data-room-slug]');
      const slug = card ? card.dataset.roomSlug : '';
      if (slug) {
        Alpine.store('roomDetails').openRoom(slug);
      }
    }
  }));

  // CSP-safe modal container component for room details
  Alpine.data('roomDetailsModal', () => ({
    get isOpen() {
      return Alpine.store('roomDetails').open;
    },
    closeModal() {
      Alpine.store('roomDetails').closeModal();
    }
  }));

  // CSP-safe item component for each room in details modal
  Alpine.data('roomDetailsItem', () => ({
    get isActive() {
      const slug = this.$el.dataset.roomDetailsSlug;
      return Alpine.store('roomDetails').open && Alpine.store('roomDetails').activeSlug === slug;
    }
  }));

  // Check-availability widget with stepper controls & real API integration
  Alpine.data('availabilityWidget', () => ({
    checkin: '',
    checkout: '',
    roomType: '',
    adults: 2,
    children: 0,
    selectedMaxOccupancy: 6,
    showResults: false,
    resultPrice: 0,
    resultAvail: 0,
    selectedRoomName: '',
    loading: false,
    errorMessage: '',

    init() {
      const today = new Date();
      const tomorrow = new Date(today);
      tomorrow.setDate(tomorrow.getDate() + 1);

      const formatDate = (d) => {
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
      };

      const todayStr = formatDate(today);
      const tomorrowStr = formatDate(tomorrow);

      this.$nextTick(() => {
        const checkinEl = document.getElementById('checkin');
        const checkoutEl = document.getElementById('checkout');
        const selectEl = document.getElementById('room-type');

        if (checkinEl) {
          checkinEl.min = todayStr;
          if (!this.checkin) {
            this.checkin = checkinEl.value || todayStr;
          }
        } else if (!this.checkin) {
          this.checkin = todayStr;
        }

        if (checkoutEl) {
          checkoutEl.min = tomorrowStr;
          if (!this.checkout) {
            this.checkout = checkoutEl.value || tomorrowStr;
          }
        } else if (!this.checkout) {
          this.checkout = tomorrowStr;
        }

        if (selectEl) {
          this.roomType = selectEl.value || '';
          const selectedOpt = selectEl.options[selectEl.selectedIndex];
          const maxOcc = selectedOpt ? parseInt(selectedOpt.dataset.maxOccupancy, 10) : 0;
          if (maxOcc > 0) this.selectedMaxOccupancy = maxOcc;
        }
      });
    },

    setCheckin() {
      this.checkin = this.$event.target.value;
      this.showResults = false;
    },
    setCheckout() {
      this.checkout = this.$event.target.value;
      this.showResults = false;
    },

    onRoomTypeChange() {
      const selectEl = document.getElementById('room-type');
      if (selectEl) {
        this.roomType = selectEl.value;
        const selectedOpt = selectEl.options[selectEl.selectedIndex];
        const maxOcc = selectedOpt ? parseInt(selectedOpt.dataset.maxOccupancy, 10) : 0;
        this.selectedMaxOccupancy = maxOcc > 0 ? maxOcc : 6;
        if (this.adults + this.children > this.selectedMaxOccupancy) {
          if (this.adults > this.selectedMaxOccupancy) {
            this.adults = Math.max(1, this.selectedMaxOccupancy);
            this.children = 0;
          } else {
            this.children = Math.max(0, this.selectedMaxOccupancy - this.adults);
          }
        }
      }
      this.showResults = false;
      this.errorMessage = '';
    },

    get checkinText() {
      return formatDateDMY(this.checkin) || 'Selected dates';
    },

    get checkoutText() {
      return formatDateDMY(this.checkout) || 'Selected dates';
    },

    get hasMultipleAdults() {
      return this.adults > 1;
    },

    get hasChildren() {
      return this.children > 0;
    },

    get hasMultipleChildren() {
      return this.children > 1;
    },

    get formattedPrice() {
      if (!this.resultPrice) return '0';
      const num = typeof this.resultPrice === 'number' ? this.resultPrice : parseFloat(this.resultPrice);
      return isNaN(num) ? '0' : num.toLocaleString('en-IN');
    },

    get availabilityText() {
      if (!this.resultAvail || this.resultAvail <= 0) {
        return 'Room type unavailable for these dates';
      }
      return `${this.resultAvail} room${this.resultAvail > 1 ? 's' : ''} available`;
    },

    get availabilityBadgeClasses() {
      if (!this.resultAvail || this.resultAvail <= 0) {
        return 'px-3 py-1 bg-rose-100 text-rose-800 text-xs font-semibold rounded-full border border-rose-300';
      }
      return 'px-3 py-1 bg-emerald-100 text-emerald-800 text-xs font-semibold rounded-full border border-emerald-300';
    },

    get resultsClasses() {
      return (this.showResults && !this.errorMessage) ? 'open mt-8 pt-8 border-t border-gray-100' : '';
    },

    get isNotLoading() {
      return !this.loading;
    },

    get isLoading() {
      return this.loading;
    },

    get hasErrorMessage() {
      return !!this.errorMessage;
    },

    get isReserveDisabled() {
      return !this.resultAvail || this.resultAvail <= 0;
    },

    get reserveButtonClasses() {
      const base = 'btn-gold px-8 py-3 bg-gold text-teal-950 font-bold rounded-lg tracking-wide whitespace-nowrap focus:outline-none focus:ring-4 focus:ring-gold/30 shadow-md transition-all';
      if (!this.resultAvail || this.resultAvail <= 0) {
        return `${base} opacity-50 cursor-not-allowed hover:bg-gold`;
      }
      return `${base} hover:bg-gold-light`;
    },

    reserveNow() {
      if (this.isReserveDisabled) return;
      const params = new URLSearchParams({
        room_type: this.roomType || '',
        check_in: this.checkin || '',
        check_out: this.checkout || '',
        adults: this.adults || 2,
        children: this.children || 0
      });
      window.location.href = `/booking/?${params.toString()}`;
    },

    async checkAvailability() {
      this.errorMessage = '';
      
      const checkinEl = document.getElementById('checkin');
      const checkoutEl = document.getElementById('checkout');
      const selectEl = document.getElementById('room-type');

      if (!this.checkin && checkinEl && checkinEl.value) {
        this.checkin = checkinEl.value;
      }
      if (!this.checkout && checkoutEl && checkoutEl.value) {
        this.checkout = checkoutEl.value;
      }
      if (!this.roomType && selectEl && selectEl.value) {
        this.roomType = selectEl.value;
      }

      if (!this.checkin || !this.checkout || !this.roomType) {
        this.errorMessage = 'Please select dates and a room type.';
        this.showResults = false;
        return;
      }

      this.loading = true;

      try {
        const params = new URLSearchParams({
          room_type: this.roomType,
          check_in: this.checkin,
          check_out: this.checkout,
          adults: this.adults,
          children: this.children
        });
        const res = await fetch(`/availability/check/?${params.toString()}`);
        const data = await res.json();

        if (!res.ok) {
          this.errorMessage = data.error || 'Something went wrong, please try again.';
          this.showResults = false;
        } else {
          this.resultPrice = data.price_per_night;
          this.resultAvail = data.count;
          this.selectedRoomName = data.room_type_name;
          this.showResults = true;
        }
      } catch (err) {
        this.errorMessage = 'Something went wrong, please try again.';
        this.showResults = false;
      } finally {
        this.loading = false;
      }
    },

    incrementAdults() {
      const maxLimit = this.selectedMaxOccupancy || 6;
      if (this.adults < maxLimit && (this.adults + this.children) < maxLimit) {
        this.adults++;
      }
    },
    decrementAdults() {
      if (this.adults > 1) this.adults--;
    },
    incrementChildren() {
      const maxLimit = this.selectedMaxOccupancy || 4;
      if (this.children < 4 && (this.adults + this.children) < maxLimit) {
        this.children++;
      }
    },
    decrementChildren() {
      if (this.children > 0) this.children--;
    }
  }));


  // Dedicated Booking Page component (CSP-safe)
  Alpine.data('bookingPage', () => ({
    step: 'details', // 'details' | 'otp' | 'payment' | 'confirmed'
    guestName: '',
    phone: '',
    email: '',
    code: '',
    cooldown: 0,
    cooldownTimer: null,
    loading: false,
    errorMessage: '',
    bookingData: null,
    paymentToken: '',
    debugOtp: '',
    receiptUrl: '',
    receiptPdfUrl: '',
    receiptDownloaded: false,

    // Reservation state
    roomTypeSlug: '',
    roomTypeName: '',
    checkin: '',
    checkout: '',
    adults: 2,
    children: 0,
    pricePerNight: 0,
    nights: 1,
    totalAmount: '0.00',
    isAvailable: true,

    init() {
      const ds = this.$el.dataset;
      const urlParams = new URLSearchParams(window.location.search);

      this.roomTypeSlug = ds.roomTypeSlug || urlParams.get('room_type') || '';
      this.roomTypeName = ds.roomTypeName || '';
      this.checkin = ds.checkin || urlParams.get('check_in') || '';
      this.checkout = ds.checkout || urlParams.get('check_out') || '';
      this.adults = parseInt(ds.adults || urlParams.get('adults') || '2', 10);
      this.children = parseInt(ds.children || urlParams.get('children') || '0', 10);
      this.pricePerNight = parseFloat(ds.pricePerNight || '0');
      this.nights = parseInt(ds.nights || '1', 10);
      this.totalAmount = ds.totalAmount || '0.00';
      this.isAvailable = ds.isAvailable !== 'false';
      if (ds.errorMessage) {
        this.errorMessage = ds.errorMessage;
      }

      if ((!this.totalAmount || this.totalAmount === '0.00') && this.pricePerNight > 0) {
        this.totalAmount = (this.pricePerNight * this.nights).toFixed(2);
      }
    },

    setGuestName() {
      this.guestName = this.$event.target.value;
    },
    setPhone() {
      const cleaned = this.$event.target.value.replace(/[^0-9]/g, '').slice(0, 10);
      this.$event.target.value = cleaned;
      this.phone = cleaned;
    },
    setEmail() {
      this.email = this.$event.target.value;
    },
    setCode() {
      this.code = this.$event.target.value;
    },

    goToDetails() {
      this.step = 'details';
    },

    get isDetailsStep() {
      return this.step === 'details';
    },
    get isOtpStep() {
      return this.step === 'otp';
    },
    get isPaymentStep() {
      return this.step === 'payment';
    },
    get isConfirmedStep() {
      return this.step === 'confirmed';
    },

    // Step state getters for stepper (CSP-safe single identifiers)
    get isStep1Active() {
      return this.step === 'details';
    },
    get isStep1Done() {
      return this.step !== 'details';
    },
    get isStep2Active() {
      return this.step === 'otp';
    },
    get isStep2Done() {
      return this.step === 'payment' || this.step === 'confirmed';
    },
    get isStep2Pending() {
      return this.step === 'details';
    },
    get isStep3Active() {
      return this.step === 'payment';
    },
    get isStep3Done() {
      return this.step === 'confirmed';
    },
    get isStep3Pending() {
      return this.step === 'details' || this.step === 'otp';
    },
    get isStep4Active() {
      return this.step === 'confirmed';
    },
    get isStep4Pending() {
      return this.step !== 'confirmed';
    },

    // Stepper Circle class getters (100% CSP compliant)
    get step1CircleClass() {
      return this.isStep1Active ? 'step-circle-active' : 'step-circle-done';
    },
    get step2CircleClass() {
      if (this.isStep2Active) return 'step-circle-active';
      if (this.isStep2Done) return 'step-circle-done';
      return 'step-circle-pending';
    },
    get step3CircleClass() {
      if (this.isStep3Active) return 'step-circle-active';
      if (this.isStep3Done) return 'step-circle-done';
      return 'step-circle-pending';
    },
    get step4CircleClass() {
      return this.isStep4Active ? 'step-circle-active' : 'step-circle-pending';
    },

    // Stepper Text class getters (100% CSP compliant)
    get step1TextClass() {
      return this.isStep1Active ? 'step-text-active' : 'step-text-done';
    },
    get step2TextClass() {
      if (this.isStep2Active) return 'step-text-active';
      if (this.isStep2Done) return 'step-text-done';
      return 'step-text-pending';
    },
    get step3TextClass() {
      if (this.isStep3Active) return 'step-text-active';
      if (this.isStep3Done) return 'step-text-done';
      return 'step-text-pending';
    },
    get step4TextClass() {
      return this.isStep4Active ? 'step-text-active' : 'step-text-pending';
    },
    get hasErrorMessage() {
      return !!this.errorMessage;
    },
    get hasDebugOtp() {
      return !!this.debugOtp;
    },
    get isNotLoading() {
      return !this.loading;
    },
    get canResend() {
      return this.cooldown <= 0;
    },
    get isCooldownActive() {
      return this.cooldown > 0;
    },
    get cooldownText() {
      return `Resend in ${this.cooldown}s`;
    },
    get isResendDisabled() {
      return this.cooldown > 0 || this.loading;
    },
    get displayCheckin() {
      return formatDateDMY(this.checkin);
    },
    get displayCheckout() {
      return formatDateDMY(this.checkout);
    },
    get summaryDateText() {
      if (!this.checkin || !this.checkout) return '';
      return `${formatDateDMY(this.checkin)} to ${formatDateDMY(this.checkout)}`;
    },
    get summaryGuestText() {
      const nightsStr = `${this.nights} night${this.nights > 1 ? 's' : ''}`;
      const adultsStr = `${this.adults} adult${this.adults > 1 ? 's' : ''}`;
      const kidsStr = this.children > 0 ? `, ${this.children} child${this.children > 1 ? 'ren' : ''}` : '';
      return `${nightsStr} · ${adultsStr}${kidsStr}`;
    },
    get summaryTotalText() {
      return `₹${this.totalAmount}`;
    },
    get bookingReferenceText() {
      return this.bookingData ? this.bookingData.booking_reference : '';
    },
    get bookingRoomNameText() {
      return (this.bookingData && this.bookingData.room_type_name) ? this.bookingData.room_type_name : this.roomTypeName;
    },
    get bookingDatesText() {
      if (this.bookingData && this.bookingData.check_in) {
        return `${formatDateDMY(this.bookingData.check_in)} to ${formatDateDMY(this.bookingData.check_out)}`;
      }
      return this.summaryDateText;
    },
    get bookingTotalAmountText() {
      if (this.bookingData && this.bookingData.total_amount) {
        return `₹${this.bookingData.total_amount}`;
      }
      return `₹${this.totalAmount}`;
    },
    get hasReceiptDownloaded() {
      return !!this.receiptDownloaded;
    },
    get hasReceiptUrl() {
      return !!this.receiptUrl;
    },

    triggerReceiptDownload() {
      if (!this.receiptPdfUrl) return;
      try {
        const link = document.createElement('a');
        link.href = this.receiptPdfUrl;
        link.download = `Coral_Heights_Receipt_${this.bookingReferenceText || 'CH'}.pdf`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        this.receiptDownloaded = true;
      } catch (e) {
        console.warn('Auto PDF download failed, guest can use the manual link.', e);
      }
    },

    startCooldown(seconds) {
      this.cooldown = seconds;
      if (this.cooldownTimer) clearInterval(this.cooldownTimer);
      this.cooldownTimer = setInterval(() => {
        if (this.cooldown > 0) {
          this.cooldown--;
        } else {
          clearInterval(this.cooldownTimer);
          this.cooldownTimer = null;
        }
      }, 1000);
    },

    async sendOtp() {
      this.errorMessage = '';
      const cleanPhone = this.phone.replace(/[^0-9]/g, '');

      if (!this.guestName.trim()) {
        this.errorMessage = 'Please enter your full name.';
        return;
      }
      if (cleanPhone.length !== 10) {
        this.errorMessage = 'Phone number must be exactly 10 digits.';
        return;
      }

      this.loading = true;
      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

      try {
        const response = await fetch('/bookings/otp/send/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest'
          },
          body: JSON.stringify({ phone: cleanPhone })
        });
        const data = await response.json();

        if (response.ok && data.success) {
          this.step = 'otp';
          this.startCooldown(data.cooldown_seconds || 30);
          if (data.debug_otp) {
            this.debugOtp = data.debug_otp;
          }
        } else {
          this.errorMessage = data.error || 'Failed to send verification code. Please try again.';
        }
      } catch (err) {
        this.errorMessage = 'Network error. Please try again later.';
      } finally {
        this.loading = false;
      }
    },

    async resendOtp() {
      if (this.cooldown > 0 || this.loading) return;
      await this.sendOtp();
    },

    async verifyAndHold() {
      this.errorMessage = '';
      const cleanCode = this.code.trim();
      const cleanPhone = this.phone.replace(/[^0-9]/g, '');

      if (!cleanCode || cleanCode.length !== 6) {
        this.errorMessage = 'Please enter the 6-digit verification code.';
        return;
      }

      this.loading = true;
      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

      try {
        const response = await fetch('/bookings/otp/verify-and-hold/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest'
          },
          body: JSON.stringify({
            phone: cleanPhone,
            code: cleanCode,
            guest_name: this.guestName.trim(),
            guest_email: this.email.trim() || null,
            room_type: this.roomTypeSlug,
            check_in: this.checkin,
            check_out: this.checkout,
            adults: this.adults,
            children: this.children
          })
        });
        const data = await response.json();

        if (response.ok && data.success) {
          this.bookingData = data;
          this.paymentToken = data.payment_token || '';
          this.step = 'payment';
        } else {
          if (response.status === 409) {
            this.step = 'details';
            this.errorMessage = data.error || 'This room type just sold out for these dates. Please search again.';
          } else {
            this.errorMessage = data.error || 'Invalid verification code. Please try again.';
          }
        }
      } catch (err) {
        this.errorMessage = 'Network error. Please try again later.';
      } finally {
        this.loading = false;
      }
    },

    async mockPay() {
      this.errorMessage = '';
      if (!this.bookingData || !this.bookingData.booking_id) {
        this.errorMessage = 'Booking session expired. Please start again.';
        return;
      }

      this.loading = true;
      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
      const token = this.paymentToken || (this.bookingData && this.bookingData.payment_token) || '';

      try {
        const response = await fetch(`/bookings/${this.bookingData.booking_id}/mock-pay/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest',
            'X-Payment-Token': token
          },
          body: JSON.stringify({
            payment_token: token
          })
        });
        const data = await response.json();

        if (response.ok && data.success) {
          this.bookingData = { ...this.bookingData, ...data };
          this.receiptUrl = data.receipt_url || '';
          this.receiptPdfUrl = data.receipt_pdf_url || '';
          this.step = 'confirmed';
          this.$nextTick(() => this.triggerReceiptDownload());
        } else {
          this.errorMessage = data.error || 'Payment confirmation failed. Please try again.';
        }
      } catch (err) {
        this.errorMessage = 'Network error. Please try again later.';
      } finally {
        this.loading = false;
      }
    }
  }));

  // Catering & Event Enquiry Form component (CSP-safe)
  Alpine.data('enquiryForm', () => ({
    submitting: false,
    submitted: false,
    errors: {},

    onPhoneInput(e) {
      if (e && e.target) {
        e.target.setCustomValidity('');
        e.target.value = e.target.value.replace(/[^0-9]/g, '').slice(0, 10);
      }
    },

    init() {
      const urlParams = new URLSearchParams(window.location.search);
      if (urlParams.get('submitted') === 'true') {
        this.submitted = true;
        this.$nextTick(() => {
          const enquirySection = document.getElementById('enquiry');
          if (enquirySection) {
            enquirySection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          }
        });
      }
    },

    get isNotSubmitting() {
      return !this.submitting;
    },

    get isSubmitting() {
      return this.submitting;
    },

    get isSubmitted() {
      return this.submitted;
    },

    get isNotSubmitted() {
      return !this.submitted;
    },

    hasFieldError(fieldName) {
      return !!(this.errors && this.errors[fieldName] && this.errors[fieldName].length);
    },

    getFieldError(fieldName) {
      if (this.hasFieldError(fieldName)) {
        return this.errors[fieldName][0];
      }
      return '';
    },

    resetForm() {
      this.submitted = false;
      this.errors = {};
      // Remove ?submitted=true from URL cleanly without reloading
      if (window.history && window.history.replaceState) {
        const cleanUrl = window.location.pathname + window.location.hash;
        window.history.replaceState({}, document.title, cleanUrl);
      }
      this.$nextTick(() => {
        const form = document.getElementById('enquiry-form');
        if (form) form.reset();
      });
    },

    async submitForm(e) {
      if (e && typeof e.preventDefault === 'function') {
        e.preventDefault();
      }
      this.submitting = true;
      this.errors = {};

      const form = document.getElementById('enquiry-form') || (e ? e.target : null);
      if (!form) {
        this.submitting = false;
        return;
      }

      const formData = new FormData(form);

      // Client-side phone number validation (must be 10 digits)
      const phone = (formData.get('contact_phone') || '').toString().trim();
      if (!phone || !/^\d{10}$/.test(phone)) {
        this.errors = { contact_phone: ['Phone number must be exactly 10 digits.'] };
        this.submitting = false;
        this.$nextTick(() => {
          const el = document.getElementById('id_contact_phone');
          if (el) {
            el.setCustomValidity('Phone number must be exactly 10 digits.');
            el.focus();
            el.reportValidity();
          }
        });
        return;
      }

      const csrfToken = form.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

      try {
        const response = await fetch('/enquiries/submit/', {
          method: 'POST',
          body: formData,
          headers: {
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest'
          }
        });

        const data = await response.json();

        if (response.ok && data.success) {
          form.reset();
          this.submitted = true;
          const enquirySection = document.getElementById('enquiry');
          if (enquirySection) {
            enquirySection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          }
        } else {
          this.errors = data.errors || { non_field_errors: ['Failed to submit enquiry. Please check fields and try again.'] };
          this.$nextTick(() => {
            if (this.hasFieldError('contact_phone')) {
              const el = document.getElementById('id_contact_phone');
              if (el) {
                const msg = this.getFieldError('contact_phone');
                el.setCustomValidity(msg);
                el.focus();
                el.reportValidity();
              }
            }
          });
        }
      } catch (err) {
        this.errors = { non_field_errors: ['Network error. Please try again later.'] };
      } finally {
        this.submitting = false;
      }
    }
  }));

});

/* ── Scroll-reveal & Parallax (runs after DOM ready) ─────── */

document.addEventListener('DOMContentLoaded', () => {
  // 1. IntersectionObserver for scroll-reveal animations
  const observerOptions = { threshold: 0.12, rootMargin: '0px 0px -40px 0px' };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    });
  }, observerOptions);

  document.querySelectorAll('.reveal').forEach(el => observer.observe(el));

  // Staggered children reveal
  const childObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const parent = entry.target.parentElement;
        const children = parent.querySelectorAll('.reveal-child');
        children.forEach((child, i) => {
          setTimeout(() => child.classList.add('visible'), i * 120);
        });
        childObserver.unobserve(entry.target);
      }
    });
  }, observerOptions);

  const groups = new Set();
  document.querySelectorAll('.reveal-child').forEach(el => {
    const parent = el.parentElement;
    if (!groups.has(parent)) {
      groups.add(parent);
      childObserver.observe(el);
    }
  });
  
  const parallaxBgElements = document.querySelectorAll('.parallax-bg');
  let ticking = false;

  function updateParallax() {
    const scrollY = window.pageYOffset || document.documentElement.scrollTop;

    parallaxBgElements.forEach(el => {
      const container = el.closest('.parallax-window');
      if (!container) return;

      const rect = container.getBoundingClientRect();
      const windowHeight = window.innerHeight;

      // Check if container is in viewport
      if (rect.bottom >= 0 && rect.top <= windowHeight) {
        const speed = parseFloat(el.getAttribute('data-parallax-speed')) || 0.3;
        // Calculate relative offset from top of section
        const elementOffset = rect.top;
        const translateY = elementOffset * speed;
        el.style.transform = `translate3d(0, ${translateY}px, 0)`;
      }
    });

    ticking = false;
  }

  window.addEventListener('scroll', () => {
    if (!ticking) {
      window.requestAnimationFrame(updateParallax);
      ticking = true;
    }
  }, { passive: true });

  // Initial parallax calculation
  updateParallax();
});
