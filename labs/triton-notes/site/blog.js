
(function () {
  'use strict';

  var root = document.documentElement;
  var reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

  var frames = [].slice.call(document.querySelectorAll('.figure iframe'));

  function figureTheme() {
    return root.dataset.theme === 'light' ? 'light' : 'dark';
  }

  function tellFrame(frame) {
    try {
      frame.contentWindow.postMessage({
        type: 'ds:theme',
        theme: figureTheme(),
        bg: getComputedStyle(root).getPropertyValue('--ground').trim()
      }, '*');
    } catch (e) {}
  }

  function setTheme(theme, remember) {
    root.dataset.theme = theme;
    if (remember) { try { localStorage.setItem('tn-theme', theme); } catch (e) {} }
    frames.forEach(tellFrame);
  }

  var toggle = document.getElementById('theme-toggle');
  if (toggle) {
    toggle.addEventListener('click', function () {
      setTheme(root.dataset.theme === 'dark' ? 'light' : 'dark', true);
    });
  }

  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function (e) {
    var saved = null;
    try { saved = localStorage.getItem('tn-theme'); } catch (err) {}
    if (!saved) setTheme(e.matches ? 'dark' : 'light', false);
  });

  window.addEventListener('message', function (e) {
    var d = e.data;
    if (!d || typeof d !== 'object') return;
    var frame = frames.filter(function (f) { return f.contentWindow === e.source; })[0];
    if (!frame) return;
    if (d.type === 'ds:ready') tellFrame(frame);
    if (d.type === 'ds:height' && d.h > 0) {
      frame.dataset.h = Math.ceil(d.h);
      if (d.w > 0) frame.dataset.w = Math.ceil(d.w);
      fit(frame);
    }
  });

  var LOGICAL = 880;

  function fit(frame) {
    var h = parseInt(frame.dataset.h || 0, 10);
    var wrap = frame.parentElement;
    var box = wrap.getBoundingClientRect().width;
    if (!box) return;

    var want = parseInt(frame.dataset.w || 0, 10) || LOGICAL;

    if (want <= box + 1) {
      frame.style.width = want + 'px';
      frame.style.transform = '';
      frame.style.height = h ? h + 'px' : '';
      wrap.style.height = '';
      return;
    }

    var scale = box / want;
    frame.style.width = want + 'px';
    frame.style.height = (h || 400) + 'px';
    frame.style.transformOrigin = '0 0';
    frame.style.transform = 'scale(' + scale.toFixed(4) + ')';
    wrap.style.height = Math.ceil((h || 400) * scale) + 'px';
  }

  var refit;
  window.addEventListener('resize', function () {
    clearTimeout(refit);
    refit = setTimeout(function () { frames.forEach(fit); }, 120);
    if (window.innerWidth > 1000) setDrawer(false);
  });

  frames.forEach(function (f) {
    f.addEventListener('load', function () { tellFrame(f); });
  });

  var reveal = [].slice.call(document.querySelectorAll('.figure'));
  if (reduced || !('IntersectionObserver' in window)) {
    reveal.forEach(function (el) { el.classList.add('in'); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('in');
          io.unobserve(entry.target);
        }
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.04 });
    reveal.forEach(function (el) { io.observe(el); });
  }

  var links = [].slice.call(document.querySelectorAll('[data-toc]'));
  var marker = document.getElementById('marker') || document.getElementById('rail-marker');
  var masthead = document.querySelector('.masthead');
  var bar = document.getElementById('progress-bar');
  var totop = document.getElementById('totop');
  var railIn = document.querySelector('.rail-in');

  var targets = links.map(function (a) {
    return { id: a.dataset.toc, el: document.getElementById(a.dataset.toc), link: a };
  }).filter(function (t) { return t.el; });

  var ticks = document.getElementById('rail-ticks');
  if (ticks) {
    targets.forEach(function (t) {
      var level = (t.link.parentElement.className.match(/toc-item--h(\d)/) || [, '2'])[1];
      var b = document.createElement('span');
      b.className = 'tick tick--h' + level;
      ticks.appendChild(b);
      t.tick = b;
    });
  }

  var current = null;

  function markActive(entry) {
    if (entry === current) return;
    current = entry;
    links.forEach(function (a) { a.classList.remove('on'); });
    targets.forEach(function (t) { if (t.tick) t.tick.classList.remove('on'); });
    if (entry && entry.tick) entry.tick.classList.add('on');
    if (!entry) {
      if (marker) marker.style.opacity = '0';
      return;
    }
    entry.link.classList.add('on');
    if (marker) {
      marker.style.opacity = '1';
      marker.style.height = entry.link.offsetHeight - 8 + 'px';
      marker.style.transform = 'translateY(' + (entry.link.offsetTop + 4) + 'px)';
    }
    keepVisible(entry.link);
  }

  function keepVisible(link) {
    if (!railIn || railIn.scrollHeight <= railIn.clientHeight) return;
    var top = link.offsetTop, bottom = top + link.offsetHeight;
    var viewTop = railIn.scrollTop, viewBottom = viewTop + railIn.clientHeight;
    if (top < viewTop + 48) {
      railIn.scrollTo({ top: Math.max(0, top - 96), behavior: reduced ? 'auto' : 'smooth' });
    } else if (bottom > viewBottom - 48) {
      railIn.scrollTo({ top: bottom - railIn.clientHeight + 96, behavior: reduced ? 'auto' : 'smooth' });
    }
  }

  var ticking = false;
  function onScroll() {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(function () {
      ticking = false;
      var y = window.scrollY;
      var line = y + window.innerHeight * 0.22;

      var active = null;
      for (var i = 0; i < targets.length; i++) {
        if (targets[i].el.getBoundingClientRect().top + y <= line) active = targets[i];
        else break;
      }
      markActive(active);

      if (masthead) masthead.classList.toggle('is-stuck', y > 8);
      if (totop) totop.classList.toggle('on', y > window.innerHeight * 0.9);
      if (bar) {
        var max = document.documentElement.scrollHeight - window.innerHeight;
        bar.style.width = (max > 0 ? Math.min(100, (y / max) * 100) : 0) + '%';
      }
    });
  }

  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll);
  onScroll();

  if (totop) {
    totop.addEventListener('click', function () {
      window.scrollTo({ top: 0, behavior: reduced ? 'auto' : 'smooth' });

      var head = document.querySelector('.post-title') || document.body;
      head.setAttribute('tabindex', '-1');
      head.focus({ preventScroll: true });
    });
  }

  var rail = document.getElementById('rail');
  var railOpen = document.getElementById('rail-open');
  var railPanel = document.getElementById('rail-panel');
  var scrim = document.getElementById('scrim');

  function setDrawer(on) {
    if (!rail) return;
    rail.classList.toggle('on', on);
    if (scrim) scrim.classList.toggle('on', on && window.innerWidth <= 1000);
    if (railOpen) railOpen.setAttribute('aria-expanded', String(on));
    if (ticks) ticks.setAttribute('aria-expanded', String(on));
    if (railPanel) {
      railPanel.toggleAttribute('inert', !on);
      railPanel.setAttribute('aria-hidden', String(!on));
    }
  }
  if (ticks) ticks.addEventListener('click', function () { setDrawer(!rail.classList.contains('on')); });
  if (railOpen) railOpen.addEventListener('click', function () { setDrawer(!rail.classList.contains('on')); });
  if (scrim) scrim.addEventListener('click', function () { setDrawer(false); });
  links.forEach(function (a) { a.addEventListener('click', function () { setDrawer(false); }); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') setDrawer(false); });
  document.addEventListener('click', function (e) {
    if (!rail || !rail.classList.contains('on')) return;
    if (rail.contains(e.target) || (railOpen && railOpen.contains(e.target))) return;
    setDrawer(false);
  });

  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-copy]');
    if (!btn) return;
    var code = btn.closest('.code').querySelector('code');
    var text = code ? code.innerText : '';
    var done = function () {
      btn.textContent = 'Copied';
      btn.classList.add('done');
      setTimeout(function () { btn.textContent = 'Copy'; btn.classList.remove('done'); }, 1600);
    };
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(done, function () {});
    } else {
      var ta = document.createElement('textarea');
      ta.value = text; document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); done(); } catch (err) {}
      document.body.removeChild(ta);
    }
  });

  document.addEventListener('click', function (e) {
    var a = e.target.closest('a[href^="#"]');
    if (!a) return;
    var id = a.getAttribute('href').slice(1);
    var el = id ? document.getElementById(id) : document.body;
    if (!el) return;
    e.preventDefault();
    el.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: id ? 'start' : 'start' });
    if (id) history.replaceState(null, '', '#' + id);
    else history.replaceState(null, '', location.pathname);
  });
})();
