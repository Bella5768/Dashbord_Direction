/* Validation métier côté client — helpers partagés (CSIGV). */
(function () {
  'use strict';

  if (window.CSIGV) return;
  var CSIGV = (window.CSIGV = {});

  function parseDate(s) {
    if (!s) return null;
    var p = String(s).trim().split('-');
    if (p.length !== 3) return null;
    var y = +p[0], m = +p[1], d = +p[2];
    if (!y || !m || !d) return null;
    return new Date(y, m - 1, d);
  }

  function pad(n) { return (n < 10 ? '0' : '') + n; }

  CSIGV.today = function () {
    var d = new Date();
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
  };

  /* Nombre de jours entre aujourd'hui (minuit) et la date donnée (yyyy-mm-dd). */
  CSIGV.daysFrom = function (dateStr) {
    var t = parseDate(dateStr);
    if (!t) return null;
    var now = new Date();
    var today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    return Math.round((t - today) / 86400000);
  };

  /* Comparaison de dates au format yyyy-mm-dd. 0 si une des deux manque.
     Retourne -1 si a < b, 1 si a > b. */
  CSIGV.compareDate = function (a, b) {
    if (!a || !b) return 0;
    a = a.trim(); b = b.trim();
    return a === b ? 0 : (a < b ? -1 : 1);
  };

  CSIGV.val = function (id) {
    var el = document.getElementById(id);
    return el ? String(el.value == null ? '' : el.value).trim() : '';
  };

  CSIGV.checked = function (id) {
    var el = document.getElementById(id);
    return !!(el && el.checked);
  };

  CSIGV.isNegative = function (id) {
    var v = CSIGV.val(id);
    if (v === '') return false;
    var n = Number(v);
    return isNaN(n) ? false : n < 0;
  };

  function wrapper(input) {
    return input.closest('.form-group, .lf-group') || input.parentElement;
  }

  CSIGV.setError = function (input, msg, className) {
    if (!input) return;
    var w = wrapper(input);
    if (!w) return;
    var id = input.id || input.name || '';
    var el = w.querySelector('.csigv-err[data-for="' + id + '"]');
    if (!el) {
      el = document.createElement('p');
      el.className = (className || 'form-error') + ' csigv-err';
      el.setAttribute('data-for', id);
      w.appendChild(el);
    }
    if (msg) {
      el.textContent = msg;
      input.classList.add('csigv-invalid');
    } else {
      el.remove();
      input.classList.remove('csigv-invalid');
    }
  };

  CSIGV.clearErrors = function (form) {
    form.querySelectorAll('.csigv-err').forEach(function (el) { el.remove(); });
    form.querySelectorAll('.csigv-invalid').forEach(function (el) { el.classList.remove('csigv-invalid'); });
  };

  CSIGV.focusFirstError = function (form) {
    var first = form.querySelector('.csigv-err');
    if (!first) return;
    var w = first.closest('.form-group, .lf-group');
    if (!w) return;
    var f = w.querySelector('input, select, textarea');
    if (f) f.focus();
  };

  /* Validation du formulaire au submit.
     checks : tableau de fonctions -> { el, msg, cls } | null */
  CSIGV.wire = function (form, checks) {
    if (!form) return;
    form.addEventListener('submit', function (e) {
      CSIGV.clearErrors(form);
      var valid = true;
      checks.forEach(function (check) {
        var r = check();
        if (r && r.msg) {
          CSIGV.setError(r.el, r.msg, r.cls);
          valid = false;
        }
      });
      if (!valid) {
        e.preventDefault();
        e.stopPropagation();
        var firstInvalid = form.querySelector('.csigv-invalid');
        if (firstInvalid) {
          firstInvalid.scrollIntoView({ block: 'center', behavior: 'smooth' });
        }
        CSIGV.focusFirstError(form);
      }
    });
  };

  /* Re-validation live : à chaque saisie, les erreurs sont recalculées.
     On n'affiche une erreur que si le champ est en train d'être saisi ou
     s'il était déjà en erreur ; une erreur disparaît dès que la règle passe. */
  CSIGV.live = function (ids, checks) {
    var form = null;

    function revalidate(e) {
      if (!form) return;
      var target = e && e.target;
      var had = [];
      form.querySelectorAll('.csigv-invalid').forEach(function (el) { had.push(el); });
      CSIGV.clearErrors(form);
      checks.forEach(function (check) {
        var r = check();
        if (!r || !r.msg || !r.el) return;
        if (r.el === target || had.indexOf(r.el) !== -1) {
          CSIGV.setError(r.el, r.msg, r.cls);
        }
      });
    }

    ids.forEach(function (id) {
      var el = document.getElementById(id);
      if (!el) return;
      if (!form) form = el.form || (el.closest && el.closest('form'));
      el.addEventListener('input', revalidate);
      el.addEventListener('change', revalidate);
    });
  };
})();