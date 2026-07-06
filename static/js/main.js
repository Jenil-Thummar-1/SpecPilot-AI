/*
   SpecPilot AI — Interaction & Motion Engine
   Splash sequence, theme system, sidebar, scroll reveal, magnetic buttons,
   ripple feedback, animated counters/progress, and misc premium touches.
*/

(function () {
  'use strict';

  /* ---------------------------------------------------------------- *
   * 0. SPLASH SCREEN (first paint only, per browser tab session)
   * ---------------------------------------------------------------- */
  function runSplash() {
    var seen = sessionStorage.getItem('specpilot-splash-seen');
    var splash = document.getElementById('sp-splash');
    if (!splash) return;

    if (seen) {
      splash.remove();
      return;
    }

    var statusEl = splash.querySelector('.sp-splash-status');
    var percentEl = splash.querySelector('.sp-splash-percent');
    var progressEl = splash.querySelector('.sp-splash-progress');

    var duration = 2200;
    var startTime = null;

    var phases = [
      { start: 0, end: 20, text: 'Initializing architectural agents...' },
      { start: 20, end: 50, text: 'Spawning Alpha Architect & Beta Planner...' },
      { start: 50, end: 75, text: 'Mounting vector memory vault...' },
      { start: 75, end: 90, text: 'Verifying 15-stage FSM compiler...' },
      { start: 90, end: 100, text: 'Booting technical blueprint UI...' }
    ];

    function updateSplash(timestamp) {
      if (!startTime) startTime = timestamp;
      var elapsed = timestamp - startTime;
      var progress = Math.min(elapsed / duration, 1);
      
      // Easing curve (ease-out cubic)
      var eased = 1 - Math.pow(1 - progress, 3);
      var currentPercent = Math.floor(eased * 100);

      if (percentEl) percentEl.textContent = currentPercent + '%';
      if (progressEl) progressEl.style.width = currentPercent + '%';

      // Find appropriate text status
      var textStatus = 'Preparing Workspace...';
      for (var j = 0; j < phases.length; j++) {
        if (currentPercent >= phases[j].start && currentPercent <= phases[j].end) {
          textStatus = phases[j].text;
          break;
        }
      }
      if (statusEl && statusEl.textContent !== textStatus) {
        statusEl.style.opacity = 0.5;
        statusEl.textContent = textStatus;
        statusEl.style.opacity = 1;
      }

      if (progress < 1) {
        requestAnimationFrame(updateSplash);
      } else {
        setTimeout(function () {
          splash.classList.add('sp-splash-hidden');
          sessionStorage.setItem('specpilot-splash-seen', '1');
          setTimeout(function () { splash.remove(); }, 750);
        }, 200);
      }
    }

    requestAnimationFrame(updateSplash);
  }

  /* ---------------------------------------------------------------- *
   * 1. THEME SYSTEM
   * ---------------------------------------------------------------- */
  function initTheme() {
    var saved = localStorage.getItem('specpilot-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);
    updateThemeIcon(saved);

    var btn = document.getElementById('theme-toggler');
    if (btn) {
      btn.addEventListener('click', function () {
        var current = document.documentElement.getAttribute('data-theme');
        var next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('specpilot-theme', next);
        updateThemeIcon(next);
      });
    }
  }

  function updateThemeIcon(theme) {
    var icon = document.querySelector('#theme-toggler i');
    if (icon) {
      icon.className = theme === 'light' ? 'bi bi-moon-stars-fill' : 'bi bi-sun-fill';
    }
  }

  /* ---------------------------------------------------------------- *
   * 2. RESPONSIVE SIDEBAR
   * ---------------------------------------------------------------- */
  function initSidebar() {
    var toggler = document.getElementById('sidebar-toggler');
    var sidebar = document.querySelector('.sidebar');
    if (!toggler || !sidebar) return;

    toggler.addEventListener('click', function (e) {
      e.stopPropagation();
      sidebar.classList.toggle('active');
    });

    document.addEventListener('click', function (e) {
      if (sidebar.classList.contains('active') && !sidebar.contains(e.target) && e.target !== toggler) {
        sidebar.classList.remove('active');
      }
    });
  }

  /* ---------------------------------------------------------------- *
   * 3. TOAST AUTO-DISMISS
   * ---------------------------------------------------------------- */
  function initToasts() {
    document.querySelectorAll('.toast-alert').forEach(function (toast) {
      setTimeout(function () {
        toast.style.transition = 'all 0.4s cubic-bezier(0.16, 1, 0.3, 1)';
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-20px) scale(0.95)';
        setTimeout(function () { toast.remove(); }, 400);
      }, 5000);
    });
  }

  /* ---------------------------------------------------------------- *
   * 4. TAB SYNC (Bootstrap pills/tabs styled as buttons)
   * ---------------------------------------------------------------- */
  function initTabs() {
    var tabs = [].slice.call(document.querySelectorAll('button[data-bs-toggle="tab"], button[data-bs-toggle="pill"]'));
    tabs.forEach(function (tabEl) {
      tabEl.addEventListener('shown.bs.tab', function (event) {
        tabs.forEach(function (btn) {
          if (btn !== event.target) {
            btn.classList.remove('text-white', 'active');
          } else {
            btn.classList.add('text-white', 'active');
          }
        });
      });
    });
  }

  /* ---------------------------------------------------------------- *
   * 5. PROGRESS BARS (animate width from data-progress)
   * ---------------------------------------------------------------- */
  function initProgressBars() {
    var bars = document.querySelectorAll('.progress-bar[data-progress]');
    var observer = ('IntersectionObserver' in window) ? new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          var bar = entry.target;
          var progress = bar.getAttribute('data-progress') || '0';
          requestAnimationFrame(function () { bar.style.width = progress + '%'; });
          observer.unobserve(bar);
        }
      });
    }, { threshold: 0.2 }) : null;

    bars.forEach(function (bar) {
      bar.style.width = '0%';
      if (observer) {
        observer.observe(bar);
      } else {
        bar.style.width = (bar.getAttribute('data-progress') || '0') + '%';
      }
    });
  }

  /* ---------------------------------------------------------------- *
   * 6. SCROLL REVEAL
   * ---------------------------------------------------------------- */
  function initScrollReveal() {
    var targets = document.querySelectorAll('.sp-reveal');
    if (!targets.length) return;

    if (!('IntersectionObserver' in window)) {
      targets.forEach(function (t) { t.classList.add('sp-in'); });
      return;
    }

    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry, idx) {
        if (entry.isIntersecting) {
          var el = entry.target;
          var delay = el.getAttribute('data-reveal-delay') || (idx * 40);
          setTimeout(function () { el.classList.add('sp-in'); }, delay);
          observer.unobserve(el);
        }
      });
    }, { threshold: 0.12 });

    targets.forEach(function (t) { observer.observe(t); });
  }



  /* ---------------------------------------------------------------- *
   * 8. RIPPLE FEEDBACK
   * ---------------------------------------------------------------- */
  function initRipple() {
    document.querySelectorAll('.btn-primary-custom, .btn-secondary-custom, .btn-outline-primary').forEach(function (btn) {
      btn.classList.add('btn-ripple');
      btn.addEventListener('click', function (e) {
        var rect = btn.getBoundingClientRect();
        var circle = document.createElement('span');
        var size = Math.max(rect.width, rect.height);
        circle.className = 'ripple';
        circle.style.width = circle.style.height = size + 'px';
        circle.style.left = (e.clientX - rect.left - size / 2) + 'px';
        circle.style.top = (e.clientY - rect.top - size / 2) + 'px';
        btn.appendChild(circle);
        setTimeout(function () { circle.remove(); }, 650);
      });
    });
  }

  /* ---------------------------------------------------------------- *
   * 9. ANIMATED COUNTERS (elements with data-count-to)
   * ---------------------------------------------------------------- */
  function initCounters() {
    var counters = document.querySelectorAll('[data-count-to]');
    if (!counters.length) return;
    var observer = ('IntersectionObserver' in window) ? new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          animateCount(entry.target);
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.4 }) : null;

    counters.forEach(function (el) {
      if (observer) observer.observe(el); else animateCount(el);
    });
  }

  function animateCount(el) {
    var end = parseFloat(el.getAttribute('data-count-to')) || 0;
    var duration = 900;
    var start = 0;
    var startTime = null;
    function step(ts) {
      if (!startTime) startTime = ts;
      var progress = Math.min((ts - startTime) / duration, 1);
      var eased = 1 - Math.pow(1 - progress, 3);
      el.textContent = Math.round(start + (end - start) * eased);
      if (progress < 1) requestAnimationFrame(step);
      else el.textContent = end;
    }
    requestAnimationFrame(step);
  }

  /* ---------------------------------------------------------------- *
   * 10. MARQUEE DUPLICATION (auto clone content for seamless loop)
   * ---------------------------------------------------------------- */
  function initMarquee() {
    document.querySelectorAll('.sp-marquee-track').forEach(function (track) {
      if (track.dataset.cloned) return;
      track.innerHTML += track.innerHTML;
      track.dataset.cloned = 'true';
    });
  }



  /* ---------------------------------------------------------------- *
   * 12. AMBIENT ORB FIELD (inserted once per page for background depth)
   * ---------------------------------------------------------------- */
  function initOrbField() {
    if (document.querySelector('.sp-orb-field')) return;
    var field = document.createElement('div');
    field.className = 'sp-orb-field';
    field.setAttribute('aria-hidden', 'true');
    field.innerHTML = '<span class="sp-orb o1"></span><span class="sp-orb o2"></span><span class="sp-orb o3"></span>';
    document.body.prepend(field);
  }

  function initHeroPipeline() {
    var cards = document.querySelectorAll('.sp-flow-card');
    var activeLine = document.querySelector('.sp-flow-line-active');
    if (!cards.length) return;

    var activeIdx = 0;

    setInterval(function () {
      cards.forEach(function (card, idx) {
        if (idx === activeIdx) {
          card.classList.add('active');
        } else {
          card.classList.remove('active');
        }
      });

      if (activeLine) {
        var percentages = ['10%', '32%', '55%', '78%', '100%'];
        activeLine.setAttribute('y2', percentages[activeIdx]);
      }

      activeIdx = (activeIdx + 1) % cards.length;
    }, 2500);
  }

  /* ---------------------------------------------------------------- *
   * 14. PASSWORD REVEAL TOGGLE
   * ---------------------------------------------------------------- */
  function initPasswordReveal() {
    var buttons = document.querySelectorAll('.form-icon-btn.sp-pw-toggle');
    buttons.forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        var input = btn.closest('.form-group-custom').querySelector('input');
        var icon = btn.querySelector('i');
        if (!input || !icon) return;
        if (input.type === 'password') {
          input.type = 'text';
          icon.className = 'bi bi-eye-slash-fill';
        } else {
          input.type = 'password';
          icon.className = 'bi bi-eye-fill';
        }
      });
    });
  }

  /* ---------------------------------------------------------------- *
   * 15. PASSWORD STRENGTH METER & VALIDATION
   * ---------------------------------------------------------------- */
  function initPasswordStrength() {
    var pwInput = document.querySelector('input[name="password"]');
    var confirmInput = document.querySelector('input[name="password_confirm"]');
    var strengthFill = document.querySelector('.sp-pw-strength-fill');
    var strengthText = document.querySelector('.sp-pw-strength-text');
    
    if (!pwInput) return;

    pwInput.addEventListener('input', function () {
      var val = pwInput.value;
      var score = 0;
      if (val.length >= 8) score += 25;
      if (/[a-z]/.test(val) && /[A-Z]/.test(val)) score += 25;
      if (/\d/.test(val)) score += 25;
      if (/[^a-zA-Z\d]/.test(val)) score += 25;

      if (strengthFill) {
        strengthFill.style.width = score + '%';
        if (score <= 25) {
          strengthFill.style.backgroundColor = 'var(--danger)';
          if (strengthText) strengthText.textContent = 'Weak Password';
        } else if (score <= 50) {
          strengthFill.style.backgroundColor = 'var(--warning)';
          if (strengthText) strengthText.textContent = 'Medium Password';
        } else if (score <= 75) {
          strengthFill.style.backgroundColor = 'var(--info)';
          if (strengthText) strengthText.textContent = 'Strong Password';
        } else {
          strengthFill.style.backgroundColor = 'var(--success)';
          if (strengthText) strengthText.textContent = 'Excellent Password';
        }
      }
    });

    if (confirmInput) {
      confirmInput.addEventListener('input', function () {
        if (confirmInput.value === pwInput.value) {
          confirmInput.classList.remove('is-invalid');
          confirmInput.classList.add('is-valid');
        } else {
          confirmInput.classList.remove('is-valid');
          confirmInput.classList.add('is-invalid');
        }
      });
    }
  }

  /* ---------------------------------------------------------------- *
   * 16. COPY CODE BLOCK UTILITY
   * ---------------------------------------------------------------- */
  function initCopyCode() {
    var blocks = document.querySelectorAll('pre code');
    blocks.forEach(function (code) {
      var pre = code.parentNode;
      var wrapper = pre.parentNode;
      if (!wrapper.classList.contains('sp-code-block-wrapper')) {
        wrapper = document.createElement('div');
        wrapper.className = 'sp-code-block-wrapper';
        pre.parentNode.insertBefore(wrapper, pre);
        wrapper.appendChild(pre);
      }
      
      var btn = document.createElement('button');
      btn.className = 'sp-copy-btn';
      btn.type = 'button';
      btn.innerHTML = '<i class="bi bi-copy"></i> Copy';
      wrapper.appendChild(btn);

      btn.addEventListener('click', function () {
        navigator.clipboard.writeText(code.textContent).then(function () {
          btn.innerHTML = '<i class="bi bi-check-lg text-success"></i> Copied!';
          setTimeout(function () {
            btn.innerHTML = '<i class="bi bi-copy"></i> Copy';
          }, 2000);
        });
      });
    });
  }

  /* ---------------------------------------------------------------- *
   * INIT
   * ---------------------------------------------------------------- */
  document.addEventListener('DOMContentLoaded', function () {
    runSplash();
    initTheme();
    initSidebar();
    initToasts();
    initTabs();
    initProgressBars();
    initScrollReveal();
    initRipple();
    initCounters();
    initMarquee();
    initOrbField();
    initHeroPipeline();
    initPasswordReveal();
    initPasswordStrength();
    initCopyCode();
  });
})();
