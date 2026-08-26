/* Doggy Duty, LLC — interactions
   Motion: custom easing only. Reveals: IntersectionObserver only. */

(function () {
  'use strict';

  var EASE = 'cubic-bezier(0.32,0.72,0,1)';
  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var $$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };

  /* ---------------------------------------------------------------
     1. Island nav: hamburger morph + full screen glass overlay
  ---------------------------------------------------------------- */
  var burger = $('.burger');
  var overlay = $('.overlay');

  function setMenu(open) {
    if (!overlay || !burger) return;
    overlay.classList.toggle('open', open);
    burger.classList.toggle('is-open', open);
    burger.setAttribute('aria-expanded', open ? 'true' : 'false');
    burger.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    document.documentElement.style.overflow = open ? 'hidden' : '';
    if (open) {
      var first = $('a, button', overlay);
      if (first) { window.setTimeout(function () { first.focus(); }, 260); }
    }
  }

  if (burger) {
    burger.addEventListener('click', function () {
      setMenu(!(overlay && overlay.classList.contains('open')));
    });
  }
  if (overlay) {
    $$('a, button', overlay).forEach(function (el) {
      el.addEventListener('click', function () { setMenu(false); });
    });
  }
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { setMenu(false); }
  });

  /* ---------------------------------------------------------------
     2. Scroll reveals: heavy fade up with blur
  ---------------------------------------------------------------- */
  var revealables = $$('.reveal');
  if ('IntersectionObserver' in window && revealables.length) {
    var revealObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('in');
          revealObserver.unobserve(entry.target);
        }
      });
    }, { rootMargin: '0px 0px -12% 0px', threshold: 0.12 });
    revealables.forEach(function (el) { revealObserver.observe(el); });
  } else {
    revealables.forEach(function (el) { el.classList.add('in'); });
  }

  /* ---------------------------------------------------------------
     3. Tagline reveal: each word warms up as it crosses the line
  ---------------------------------------------------------------- */
  $$('.tagline').forEach(function (block) {
    var lines = $$('.tagline-line', block);
    var hosts = lines.length ? lines : [block];

    hosts.forEach(function (host) {
      if ($('.word', host)) return; // already split
      var raw = host.textContent.replace(/\s+/g, ' ').trim();
      host.textContent = '';
      raw.split(' ').forEach(function (word, i) {
        var span = document.createElement('span');
        span.className = 'word';
        span.textContent = word;
        span.style.transitionDelay = (i % 8) * 40 + 'ms';
        span.style.transitionTimingFunction = EASE;
        host.appendChild(span);
        host.appendChild(document.createTextNode(' '));
      });
    });

    var words = $$('.word', block);
    if (!words.length) return;

    if (!('IntersectionObserver' in window)) {
      words.forEach(function (w) { w.classList.add('on'); });
      return;
    }

    var wordObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('on');
          wordObserver.unobserve(entry.target);
        }
      });
    }, { rootMargin: '-45% 0px -40% 0px', threshold: 0 });

    words.forEach(function (w) { wordObserver.observe(w); });

    // Safety net: if the block is fully passed, warm any leftovers.
    var tail = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.boundingClientRect.bottom < 0) {
          words.forEach(function (w) { w.classList.add('on'); });
        }
      });
    }, { threshold: 0 });
    tail.observe(block);
  });

  /* ---------------------------------------------------------------
     4. Schedule picker: empty state until a plan is chosen
  ---------------------------------------------------------------- */
  var picker = $('.picker');
  var pane = $('.pane');

  var PLANS = {
    weekly: {
      title: 'Once per week',
      lead: 'The most common plan for single family and townhome communities.',
      items: [
        'Every station emptied and wiped down on the same weekday',
        'Fresh bag rolls loaded, spares left inside the triple storage box',
        'Loose waste picked up inside a 15 foot radius of each station',
        'Photo log of every station emailed to the manager after the route'
      ]
    },
    twice: {
      title: 'Twice per week',
      lead: 'Built for dense condo and apartment properties with heavy dog traffic.',
      items: [
        'Two servicing days, usually Monday and Thursday',
        'Bag rolls counted and topped off at both visits',
        'Common lawns, breezeways and dog runs swept for missed waste',
        'Overflow bins swapped out before weekend showings'
      ]
    },
    valet: {
      title: 'Nightly valet trash',
      lead: 'Door pickup five nights per week, paired with your station service.',
      items: [
        'Collection outside every resident door between 7:00 pm and 10:00 pm',
        'Uniformed technicians with photo identification and route tracking',
        'Violation notes for improperly bagged trash, sent to the office',
        'Bulk item reporting so nothing sits by the compactor for days'
      ]
    }
  };

  function renderPlan(key) {
    if (!pane) return;
    var plan = PLANS[key];
    if (!plan) return;
    pane.classList.remove('empty');
    var list = plan.items.map(function (i) {
      return '<li><i class="ph ph-check-circle" aria-hidden="true"></i><span>' + i + '</span></li>';
    }).join('');
    pane.innerHTML =
      '<h3>' + plan.title + '</h3>' +
      '<p>' + plan.lead + '</p>' +
      '<ul class="pane-list">' + list + '</ul>' +
      '<p class="fine">Quoted per station and per door after a short walk of the property. ' +
      'No charge for the visit or the quote.</p>';
  }

  if (picker) {
    $$('button', picker).forEach(function (btn) {
      btn.addEventListener('click', function () {
        $$('button', picker).forEach(function (b) {
          b.classList.remove('on');
          b.setAttribute('aria-pressed', 'false');
        });
        btn.classList.add('on');
        btn.setAttribute('aria-pressed', 'true');
        renderPlan(btn.getAttribute('data-plan'));
      });
    });
  }

  /* ---------------------------------------------------------------
     5. Quote form: inline validation, skeleton loading, success
  ---------------------------------------------------------------- */
  var form = $('form[data-quote]') || $('main form');

  function fieldWrap(input) {
    return input.closest('.field') || input.parentNode;
  }

  function showError(input, message) {
    var wrap = fieldWrap(input);
    var msg = $('.err', wrap);
    if (!msg) {
      msg = document.createElement('p');
      msg.className = 'err';
      wrap.appendChild(msg);
    }
    msg.textContent = message;
    msg.hidden = false;
    input.setAttribute('aria-invalid', 'true');
  }

  function clearError(input) {
    var wrap = fieldWrap(input);
    var msg = $('.err', wrap);
    if (msg) { msg.textContent = ''; msg.hidden = true; }
    input.removeAttribute('aria-invalid');
  }

  function validate(input) {
    var value = (input.value || '').trim();
    var type = input.getAttribute('type');
    if (input.hasAttribute('required') && !value) {
      showError(input, 'This field is required.');
      return false;
    }
    if (type === 'email' && value && !/^[^\s@]+@[^\s@]+\.[a-z]{2,}$/i.test(value)) {
      showError(input, 'Enter a valid email address, like manager@yourcommunity.com');
      return false;
    }
    if (type === 'tel' && value && value.replace(/\D/g, '').length < 10) {
      showError(input, 'Enter a 10 digit phone number so we can call you back.');
      return false;
    }
    clearError(input);
    return true;
  }

  if (form) {
    var fields = $$('input, select, textarea', form);
    fields.forEach(function (input) {
      input.addEventListener('blur', function () { validate(input); });
      input.addEventListener('input', function () {
        if (input.getAttribute('aria-invalid') === 'true') { validate(input); }
      });
    });

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var ok = true;
      fields.forEach(function (input) { if (!validate(input)) { ok = false; } });
      if (!ok) {
        var bad = $('[aria-invalid="true"]', form);
        if (bad) { bad.focus(); }
        return;
      }

      var button = $('button[type="submit"], .btn-primary', form);
      var skeleton = $('.skel', form);
      if (button) {
        button.disabled = true;
        button.dataset.label = button.textContent;
        button.textContent = 'Sending your request';
      }
      if (skeleton) { skeleton.hidden = false; }

      window.setTimeout(function () {
        if (skeleton) { skeleton.hidden = true; }
        var name = ($('[name="name"]', form) || {}).value || '';
        var first = name.trim().split(' ')[0];
        var done = $('.ok', form) || document.createElement('div');
        done.className = 'ok';
        done.setAttribute('role', 'status');
        done.innerHTML =
          '<i class="ph ph-paw-print" aria-hidden="true"></i>' +
          '<p><strong>Request received' + (first ? ', ' + first : '') + '.</strong> ' +
          'A route manager replies within one business day, usually the same afternoon. ' +
          'Need it sooner, call (863) 399 5176.</p>';
        form.replaceChildren(done);
        done.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 900);
    });
  }

  /* ---------------------------------------------------------------
     6. Footer year
  ---------------------------------------------------------------- */
  var year = $('[data-year]');
  if (year) { year.textContent = new Date().getFullYear(); }
})();
