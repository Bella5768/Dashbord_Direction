/*
 * Helpers Chart.js partagés (CSIG).
 *
 * Objectifs :
 *  - rendre lisible un indicateur même très faible (valeur centrale + étiquettes) ;
 *  - garantir un arc minimum visible sur les donuts ;
 *  - permettre une redirection au clic sur une barre / un arc.
 *
 * Tout est opt-in : les plugins ne s'activent que si l'option
 * `options.plugins.csigCenter` / `options.plugins.csigValues` est définie.
 */
(function () {
  'use strict';
  if (typeof Chart === 'undefined') return;

  var DEFAULT_MIN_SHARE = 0.02; // 2 % d'arc minimum visible

  // Chart.js résout les options de plugin comme des options « scriptable » :
  // toute fonction d'options.plugins.<id> est rappelée avec un objet contexte
  // {chart,type,...}. On lit donc la config BRUTE (chart.config.options) pour
  // récupérer les callbacks `format` tels quels, et non la version résolue.
  //
  // On ne retombe PAS sur chart.options.plugins : Chart.js y synthétise un
  // objet vide pour les plugins enregistrés mais non configurés sur ce graphe,
  // ce qui activerait les plugins partout (total fantôme, étiquettes parasites).
  function pluginOptions(chart, id) {
    var raw = chart.config && chart.config.options && chart.config.options.plugins;
    return (raw && raw[id]) || null;
  }

  // Valeur affichée au centre d'un doughnut / pie.
  var centerValue = {
    id: 'csigCenter',
    beforeDatasetsDraw: function (chart) {
      var cfg = pluginOptions(chart, 'csigCenter');
      if (!cfg || cfg.enabled === false) return;
      var ds = chart.data.datasets && chart.data.datasets[0];
      if (!ds) return;
      var data = ds.data || [];
      var real = (cfg.real && cfg.real.length === data.length) ? cfg.real : data;
      var total = real.reduce(function (a, b) { return a + (Number(b) || 0); }, 0);
      var fmt = cfg.format || function (v) { return String(v); };
      var active = chart.getActiveElements ? chart.getActiveElements() : [];
      var main, sub = '';
      if (active && active.length && cfg.percentOnHover !== false) {
        var i = active[0].index;
        var v = Number(real[i]) || 0;
        main = fmt(v);
        sub = (cfg.showSub !== false && total) ? (Math.round((v / total) * 1000) / 10) + '%' : '';
      } else {
        if (cfg.hideIdleTotal) return;
        main = fmt(total);
        sub = cfg.label || '';
      }
      var area = chart.chartArea;
      if (!area) return;
      var ctx = chart.ctx;
      var x = (area.left + area.right) / 2;
      var y = (area.top + area.bottom) / 2;
      ctx.save();
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = cfg.color || '#1e293b';
      ctx.font = cfg.font || '700 16px Inter, system-ui, sans-serif';
      ctx.fillText(main, x, y - (sub ? 8 : 0));
      if (sub) {
        ctx.font = cfg.subFont || '600 11px Inter, system-ui, sans-serif';
        ctx.fillStyle = cfg.subColor || '#64748b';
        ctx.fillText(sub, x, y + 13);
      }
      ctx.restore();
    }
  };

  // Étiquette de valeur sur chaque barre (utile pour les barres très courtes).
  var valueLabels = {
    id: 'csigValues',
    afterDatasetsDraw: function (chart) {
      var cfg = pluginOptions(chart, 'csigValues');
      if (!cfg || cfg.enabled === false) return;
      var fmt = cfg.format || function (v) { return String(v); };
      var ctx = chart.ctx;
      var horizontal = chart.options.indexAxis === 'y';
      ctx.save();
      ctx.font = cfg.font || '600 10px Inter, system-ui, sans-serif';
      ctx.fillStyle = cfg.color || '#475569';
      chart.data.datasets.forEach(function (ds, di) {
        var meta = chart.getDatasetMeta(di);
        if (!meta || meta.hidden) return;
        meta.data.forEach(function (el, i) {
          var v = Number(ds.data[i]) || 0;
          if (!v) return;
          if (horizontal) {
            ctx.textAlign = 'left';
            ctx.textBaseline = 'middle';
            ctx.fillText(fmt(v), el.x + 6, el.y);
          } else {
            ctx.textAlign = 'center';
            ctx.textBaseline = 'bottom';
            ctx.fillText(fmt(v), el.x, el.y - 3);
          }
        });
      });
      ctx.restore();
    }
  };

  Chart.register(centerValue, valueLabels);

  var API = {
    // Étalonne les valeurs > 0 pour garantir un arc minimal, en conservant la somme.
    spread: function (data, minShare) {
      minShare = minShare || DEFAULT_MIN_SHARE;
      var real = data.map(function (v) { return Number(v) || 0; });
      var total = real.reduce(function (a, b) { return a + b; }, 0);
      if (!total) return real.slice();
      var floor = total * minShare;
      var spread = real.map(function (v) { return v > 0 ? Math.max(v, floor) : 0; });
      var s = spread.reduce(function (a, b) { return a + b; }, 0);
      var k = s ? total / s : 1;
      return spread.map(function (v) { return v * k; });
    },
    // Valeurs « réelles » du centre (sans étalonnage d'arc minimum).
    centerReal: function (chart) {
      var cfg = pluginOptions(chart, 'csigCenter');
      return (cfg && cfg.real) || [];
    },
    setCenterReal: function (chart, real) {
      var cfg = pluginOptions(chart, 'csigCenter');
      if (cfg) cfg.real = real;
    },
    // Renvoie un handler onClick qui redirige selon le segment cliqué.
    redirect: function (resolve) {
      return function (evt, elements, chart) {
        if (!elements || !elements.length) return;
        var i = elements[0].index;
        var url = resolve(i, chart, elements[0]);
        if (url) window.location.href = url;
      };
    },
    // Curseur pointeur sur les éléments cliquables.
    pointerOnHover: function (resolve) {
      return function (evt, elements) {
        if (evt.native && evt.native.target) {
          evt.native.target.style.cursor = (elements && elements.length) ? 'pointer' : 'default';
        }
      };
    }
  };

  window.CSIGCharts = API;
})();
