/* Validation des mots de passe côté client — logique partagée (CSIGPW).
   Factorise la logique dupliquée des pages mot de passe (changement,
   réinitialisation, activation) : évaluation des règles, niveau de force
   et blocage de la soumission tant que les règles ne sont pas satisfaites. */
(function () {
  'use strict';

  if (window.CSIGPW) return;
  var CSIGPW = (window.CSIGPW = {});

  CSIGPW.MIN_LENGTH = 8;

  /* Évalue un couple (saisie, confirmation).
     rules : 'ok' | 'fail' | 'neutral' (champ vide -> neutre, aucune erreur).
     score : 0..5 ; level : 0..4 ; valid : règles minimales satisfaites. */
  CSIGPW.evaluate = function (v1, v2) {
    v1 = v1 || '';
    v2 = v2 || '';

    function state(ok) {
      if (v1.length === 0) return 'neutral';
      return ok ? 'ok' : 'fail';
    }

    var hasUpperLower = /[A-Z]/.test(v1) && /[a-z]/.test(v1);
    var hasDigit = /\d/.test(v1);

    var rules = {
      len:   state(v1.length >= CSIGPW.MIN_LENGTH),
      upper: state(hasUpperLower),
      digit: state(hasDigit),
      match: v2.length === 0 ? 'neutral' : ((v1 === v2 && v1.length > 0) ? 'ok' : 'fail')
    };

    var score = 0;
    if (v1.length >= 8) score++;
    if (v1.length >= 12) score++;
    if (hasUpperLower) score++;
    if (hasDigit) score++;
    if (/[^a-zA-Z0-9]/.test(v1)) score++;

    var valid = v1.length >= CSIGPW.MIN_LENGTH && hasUpperLower && hasDigit
      && v2.length > 0 && v1 === v2;

    return { rules: rules, score: score, level: Math.min(score, 4), valid: valid };
  };

  /* Bloque la soumission du formulaire tant que isValid() est faux. */
  CSIGPW.block = function (form, isValid) {
    if (!form) return;
    form.addEventListener('submit', function (e) {
      if (!isValid()) {
        e.preventDefault();
        e.stopPropagation();
      }
    });
  };
})();
