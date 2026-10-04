/* Fix2Live Credit Solutions — interaction layer
   Motion: every transition uses cubic-bezier(0.32, 0.72, 0, 1) (declared in styles.css).
   Reveals: IntersectionObserver only. No scroll event listeners. */

(function () {
  'use strict';

  var EASE_MS = 800;
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function $(sel, ctx) { return (ctx || document).querySelector(sel); }
  function $$(sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); }

  /* ---------------------------------------------------------------
     1. Fluid island nav — hamburger morph + full screen glass modal
  --------------------------------------------------------------- */
  var burger = $('.nav-burger') || $('.nav-toggle') || $('[data-nav-toggle]');
  var modal = $('.nav-modal') || $('#nav-modal');
  var pill = $('.nav-pill');

  function setNav(open) {
    if (!modal) return;
    modal.classList.toggle('open', open);
    modal.classList.toggle('is-open', open);
    if (burger) {
      burger.classList.toggle('open', open);
      burger.classList.toggle('is-open', open);
      burger.setAttribute('aria-expanded', open ? 'true' : 'false');
      burger.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    }
    modal.setAttribute('aria-hidden', open ? 'false' : 'true');
    document.documentElement.style.overflow = open ? 'hidden' : '';
    document.body.style.overflow = open ? 'hidden' : '';
    if (open) {
      var first = modal.querySelector('a, button');
      if (first) { try { first.focus({ preventScroll: true }); } catch (e) { first.focus(); } }
    } else if (burger) {
      try { burger.focus({ preventScroll: true }); } catch (e) { burger.focus(); }
    }
  }

  if (burger && modal) {
    burger.setAttribute('aria-expanded', 'false');
    modal.setAttribute('aria-hidden', 'true');
    burger.addEventListener('click', function () {
      setNav(!modal.classList.contains('open'));
    });
    $$('a, .nav-modal-close, [data-nav-close]', modal).forEach(function (el) {
      el.addEventListener('click', function () { setNav(false); });
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && modal.classList.contains('open')) setNav(false);
    });
  }

  /* Condense the nav pill once the page leaves the hero (IntersectionObserver,
     never a scroll listener). */
  var heroSentinel = $('.hero') || $('#hero');
  if (pill && heroSentinel && 'IntersectionObserver' in window) {
    new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        pill.classList.toggle('is-condensed', !en.isIntersecting);
      });
    }, { rootMargin: '-120px 0px 0px 0px', threshold: 0 }).observe(heroSentinel);
  }

  /* ---------------------------------------------------------------
     2. Scroll interpolation — heavy fade up with blur
  --------------------------------------------------------------- */
  var revealables = $$('.reveal');

  if (reduced || !('IntersectionObserver' in window)) {
    revealables.forEach(function (el) { el.classList.add('in'); });
  } else {
    var revealObserver = new IntersectionObserver(function (entries, obs) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        var el = en.target;
        var delay = parseInt(el.getAttribute('data-delay') || '0', 10);
        window.setTimeout(function () { el.classList.add('in'); }, delay);
        obs.unobserve(el);
      });
    }, { rootMargin: '0px 0px -12% 0px', threshold: 0.12 });

    revealables.forEach(function (el) { revealObserver.observe(el); });

    /* Stagger cards inside any grid that opts in */
    $$('[data-stagger]').forEach(function (grid) {
      var step = parseInt(grid.getAttribute('data-stagger') || '100', 10);
      $$('.reveal', grid).forEach(function (child, i) {
        if (!child.getAttribute('data-delay')) {
          child.setAttribute('data-delay', String(i * step));
        }
      });
    });
  }

  /* ---------------------------------------------------------------
     3. Tagline reveal — words activate one at a time, in reading order
  --------------------------------------------------------------- */
  var tagline = $('.tagline-text') || $('[data-word-reveal]');

  if (tagline) {
    var words = $$('.w', tagline);

    /* If the markup did not pre-split, split it here. */
    if (!words.length) {
      var html = tagline.innerHTML.split(/<br\s*\/?>/i);
      tagline.innerHTML = html.map(function (line) {
        return line
          .replace(/<[^>]+>/g, '')
          .trim()
          .split(/\s+/)
          .filter(Boolean)
          .map(function (w) { return '<span class="w">' + w + '</span>'; })
          .join(' ');
      }).join('<br>');
      words = $$('.w', tagline);
    }

    /* Guarantee real whitespace between adjacent word spans */
    words.forEach(function (w) {
      var next = w.nextSibling;
      var needsSpace = !next || (next.nodeType === 1 && next.classList && next.classList.contains('w'));
      if (needsSpace && next && !(next.nodeType === 1 && next.tagName === 'BR')) {
        w.parentNode.insertBefore(document.createTextNode(' '), next);
      }
    });

    if (reduced || !('IntersectionObserver' in window)) {
      words.forEach(function (w) { w.classList.add('on'); });
    } else {
      /* Group words by their rendered line so the stagger follows reading order */
      var lineIndex = new Map();
      var buildLines = function () {
        var lines = {};
        words.forEach(function (w) {
          var top = Math.round(w.offsetTop / 6);
          lines[top] = lines[top] || [];
          lines[top].push(w);
        });
        Object.keys(lines).forEach(function (k) {
          lines[k].forEach(function (w, i) { lineIndex.set(w, i); });
        });
      };
      buildLines();

      var wordObserver = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (!en.isIntersecting) return;
          var w = en.target;
          if (w.classList.contains('on')) return;
          var i = lineIndex.get(w) || 0;
          w.style.transitionDelay = (i * 70) + 'ms';
          w.classList.add('on');
        });
      }, {
        /* A narrow trigger band near the middle of the viewport:
           words switch on as they cross it, never the whole block at once. */
        rootMargin: '-42% 0px -46% 0px',
        threshold: 0
      });

      words.forEach(function (w) { wordObserver.observe(w); });

      var resizeTick = null;
      window.addEventListener('resize', function () {
        window.clearTimeout(resizeTick);
        resizeTick = window.setTimeout(buildLines, 200);
      });
    }
  }

  /* ---------------------------------------------------------------
     4. Current section indicator in the nav
  --------------------------------------------------------------- */
  var navLinks = $$('.nav-links a[href^="#"], .nav-modal-links a[href^="#"], .nm-link[href^="#"]');
  if (navLinks.length && 'IntersectionObserver' in window) {
    var byId = {};
    navLinks.forEach(function (a) {
      var id = a.getAttribute('href').slice(1);
      if (!id) return;
      byId[id] = byId[id] || [];
      byId[id].push(a);
    });

    var targets = Object.keys(byId)
      .map(function (id) { return document.getElementById(id); })
      .filter(Boolean);

    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        navLinks.forEach(function (a) {
          a.classList.remove('is-current');
          a.removeAttribute('aria-current');
        });
        (byId[en.target.id] || []).forEach(function (a) {
          a.classList.add('is-current');
          a.setAttribute('aria-current', 'true');
        });
      });
    }, { rootMargin: '-45% 0px -50% 0px', threshold: 0 });

    targets.forEach(function (t) { spy.observe(t); });
  }

  /* ---------------------------------------------------------------
     5. Consultation form — inline validation, loading, success
  --------------------------------------------------------------- */
  var form = $('.lead-form') || $('form[data-lead]') || $('#consult-form') || $('form');

  if (form) {
    var EMAIL = /^[^\s@]+@[^\s@]+\.[a-z]{2,}$/i;

    function fieldOf(input) {
      return input.closest('.field') || input.parentNode;
    }

    function errorNode(input) {
      var box = fieldOf(input);
      var node = box.querySelector('.err');
      if (!node) {
        node = document.createElement('p');
        node.className = 'err';
        box.appendChild(node);
      }
      if (!node.id) node.id = (input.id || input.name || 'field') + '-error';
      return node;
    }

    function clear(input) {
      fieldOf(input).classList.remove('invalid');
      input.removeAttribute('aria-invalid');
      var node = fieldOf(input).querySelector('.err');
      if (node) node.textContent = '';
    }

    function fail(input, message) {
      var box = fieldOf(input);
      var node = errorNode(input);
      node.textContent = message;
      box.classList.add('invalid');
      input.setAttribute('aria-invalid', 'true');
      input.setAttribute('aria-describedby', node.id);
      return false;
    }

    function validate(input) {
      var value = (input.value || '').trim();
      var type = (input.getAttribute('type') || input.tagName).toLowerCase();
      var label = input.getAttribute('data-label') || input.getAttribute('placeholder') || 'This field';

      if (input.hasAttribute('required') && !value) {
        return fail(input, label + ' is required.');
      }
      if (!value) { clear(input); return true; }

      if (type === 'email' && !EMAIL.test(value)) {
        return fail(input, 'Enter an email in the format name@example.com');
      }
      if (type === 'tel') {
        var digits = value.replace(/\D/g, '');
        if (digits.length < 10) {
          return fail(input, 'Enter a 10 digit phone number, area code first.');
        }
      }
      if (input.name === 'name' && value.length < 2) {
        return fail(input, 'Enter your full name.');
      }
      clear(input);
      return true;
    }

    var fields = $$('input, select, textarea', form).filter(function (el) {
      return el.type !== 'hidden' && el.type !== 'submit';
    });

    fields.forEach(function (input) {
      input.addEventListener('blur', function () { validate(input); });
      input.addEventListener('input', function () {
        if (fieldOf(input).classList.contains('invalid')) validate(input);
      });
    });

    form.setAttribute('novalidate', 'novalidate');

    form.addEventListener('submit', function (e) {
      e.preventDefault();

      var ok = true;
      var firstBad = null;
      fields.forEach(function (input) {
        var valid = validate(input);
        if (!valid) {
          ok = false;
          if (!firstBad) firstBad = input;
        }
      });

      if (!ok) {
        if (firstBad) firstBad.focus();
        return;
      }

      var button = form.querySelector('[type="submit"]') || form.querySelector('button');
      if (button) {
        button.classList.add('is-loading');
        button.disabled = true;
        button.setAttribute('aria-busy', 'true');
      }

      window.setTimeout(function () {
        var success = $('.form-success');
        if (!success) {
          success = document.createElement('div');
          success.className = 'form-success';
          form.parentNode.insertBefore(success, form.nextSibling);
        }
        if (!success.textContent.trim()) {
          success.innerHTML =
            '<p class="mono-label">Request received</p>' +
            '<p>We have your details. A Fix2Live specialist calls back within one business day, ' +
            'usually the same afternoon. Prefer to talk now? Call (321) 337 4975.</p>';
        }
        form.classList.add('is-sent');
        form.setAttribute('hidden', 'hidden');
        success.classList.add('show');
        success.setAttribute('role', 'status');
        success.setAttribute('tabindex', '-1');
        try { success.focus({ preventScroll: true }); } catch (err) { success.focus(); }
      }, reduced ? 0 : EASE_MS);
    });
  }

  /* ---------------------------------------------------------------
     6. Small housekeeping
  --------------------------------------------------------------- */
  var year = $('[data-year]');
  if (year) year.textContent = String(new Date().getFullYear());

  /* Disable any button that has no destination rather than leaving a dead link */
  $$('a[href="#"], a:not([href])').forEach(function (a) {
    if (a.classList.contains('brand')) return;
    a.setAttribute('aria-disabled', 'true');
    a.classList.add('is-disabled');
  });
})();
