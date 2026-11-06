
(function () {
  var root = document.documentElement, key = 'upsc-theme', saved = null;
  try { saved = localStorage.getItem(key); } catch (e) {}
  var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  root.setAttribute('data-theme', saved || (prefersDark ? 'dark' : 'light'));

  document.addEventListener('DOMContentLoaded', function () {
    var btn = document.getElementById('theme-toggle');
    function label() { if (btn) btn.textContent = root.getAttribute('data-theme') === 'dark' ? '☀️' : '🌙'; }
    if (btn) {
      label();
      btn.addEventListener('click', function () {
        var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        root.setAttribute('data-theme', next);
        try { localStorage.setItem(key, next); } catch (e) {}
        label();
      });
    }

    var bar = document.getElementById('progress');
    if (bar) {
      window.addEventListener('scroll', function () {
        var h = document.documentElement;
        var total = h.scrollHeight - h.clientHeight;
        bar.style.width = (total > 0 ? (h.scrollTop / total) * 100 : 0) + '%';
      }, { passive: true });
    }

    var q = document.getElementById('archive-search');
    if (q) {
      q.addEventListener('input', function () {
        var v = q.value.trim().toLowerCase();
        document.querySelectorAll('.edition').forEach(function (el) {
          var hit = el.getAttribute('data-date').toLowerCase().indexOf(v) > -1;
          el.style.display = hit ? '' : 'none';
        });
        document.querySelectorAll('.month-group').forEach(function (g) {
          var visible = Array.prototype.some.call(g.querySelectorAll('.edition'), function (el) {
            return el.style.display !== 'none';
          });
          g.style.display = visible ? '' : 'none';
        });
      });
    }
  });
})();
