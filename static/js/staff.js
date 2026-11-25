document.addEventListener('alpine:init', function () {
  Alpine.data('staffLayout', function () {
    return {
      isDesktop: window.innerWidth >= 1024,
      sidebarOpen: window.innerWidth >= 1024,

      init: function () {
        var self = this;
        window.addEventListener('resize', function () {
          var nowDesktop = window.innerWidth >= 1024;
          if (nowDesktop !== self.isDesktop) {
            self.isDesktop = nowDesktop;
            self.sidebarOpen = nowDesktop;
          }
        });
      },

      toggleSidebar: function () {
        this.sidebarOpen = !this.sidebarOpen;
      },

      closeSidebar: function () {
        this.sidebarOpen = false;
      },

      get asideClasses() {
        return this.sidebarOpen ? 'translate-x-0' : '-translate-x-full';
      },

      get mainClasses() {
        return (this.isDesktop && this.sidebarOpen) ? 'lg:pl-64' : 'pl-0';
      },

      get showBackdrop() {
        return !this.isDesktop && this.sidebarOpen;
      }
    };
  });

  Alpine.data('reportsPage', function () {
    return {
      printReport: function () {
        window.print();
      }
    };
  });

  Alpine.data('cancelBookingPanel', function () {
    return {
      open: false,
      show: function () { this.open = true; },
      hide: function () { this.open = false; },
    };
  });
});

document.addEventListener('DOMContentLoaded', function () {
  // Login form keyboard handling (CSP-safe external script)
  var usernameInput = document.getElementById('id_username');
  var passwordInput = document.getElementById('id_password');
  var loginForm = usernameInput ? usernameInput.closest('form') : null;

  if (usernameInput && passwordInput) {
    function handleUsernameEnter(e) {
      if (e.key === 'Enter' || e.keyCode === 13) {
        e.preventDefault();
        e.stopPropagation();
        passwordInput.focus();
        return false;
      }
    }

    usernameInput.addEventListener('keydown', handleUsernameEnter);
    usernameInput.addEventListener('keypress', handleUsernameEnter);

    if (loginForm) {
      loginForm.addEventListener('submit', function (e) {
        if (document.activeElement === usernameInput || !passwordInput.value.trim()) {
          e.preventDefault();
          e.stopPropagation();
          passwordInput.focus();
          return false;
        }
      });
    }
  }

  // Confirmation modal handling for staff operations
  var modal = document.getElementById('confirmModal');
  var modalMessage = document.getElementById('confirmModalMessage');
  var btnCancel = document.getElementById('confirmModalCancel');
  var btnOk = document.getElementById('confirmModalOk');
  var pendingAction = null;

  if (modal && modalMessage && btnCancel && btnOk) {
    function openModal(msg, onConfirm) {
      modalMessage.textContent = msg;
      pendingAction = onConfirm;
      modal.classList.remove('hidden');
      requestAnimationFrame(function () {
        modal.classList.remove('opacity-0');
      });
    }

    function closeModal() {
      modal.classList.add('opacity-0');
      setTimeout(function () {
        modal.classList.add('hidden');
        pendingAction = null;
      }, 150);
    }

    btnCancel.addEventListener('click', function (e) {
      e.preventDefault();
      closeModal();
    });

    modal.addEventListener('click', function (e) {
      e.target === modal && closeModal();
    });

    btnOk.addEventListener('click', function (e) {
      e.preventDefault();
      if (typeof pendingAction === 'function') {
        var callback = pendingAction;
        pendingAction = null;
        modal.classList.add('hidden');
        modal.classList.add('opacity-0');
        callback();
      }
    });

    document.body.addEventListener('click', function (e) {
      var target = e.target.closest('[data-confirm]');
      if (target) {
        var msg = target.getAttribute('data-confirm');
        if (msg) {
          e.preventDefault();
          e.stopPropagation();

          openModal(msg, function () {
            if (target.tagName === 'A') {
              var href = target.getAttribute('href');
              if (href) {
                window.location.href = href;
              }
            } else {
              var form = target.form || target.closest('form');
              if (form) {
                HTMLFormElement.prototype.submit.call(form);
              }
            }
          });
        }
      }
    });
  }
});
