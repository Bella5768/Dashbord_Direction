// Main JavaScript file for Dashboard CSIG

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips and interactions
    initializeApp();
});

function getUserLocale() {
    return document.documentElement.lang || 'fr';
}

// ── Devise & unités (GNF <-> USD) ─────────────────────────────────────────
// Un switch global « devise » par page pilote tous les montants budget.
// Unités compactes adaptées à la langue : FR (K, M, Md, Bi) / EN (K, M, B, T).
window.CSIGMoney = (function () {
    var STORAGE_KEY = 'csig_currency';
    var UNIT = {
        fr: { k: 'K', m: 'M', b: 'Md', t: 'Bi' },
        en: { k: 'K', m: 'M', b: 'B',  t: 'T'  }
    };
    var SUPPORTED = ['GNF', 'USD'];

    function lang() {
        return ((document.documentElement.lang || 'fr').slice(0, 2).toLowerCase()) === 'en' ? 'en' : 'fr';
    }
    function units() { return UNIT[lang()] || UNIT.fr; }
    function norm(c) { return SUPPORTED.indexOf(c) >= 0 ? c : 'GNF'; }
    function preferred() {
        if (window.CSIG_PREFS && window.CSIG_PREFS.currency) return norm(window.CSIG_PREFS.currency);
        return 'GNF';
    }

    var _cur = null;
    function currency() {
        if (_cur) return _cur;
        var stored = null;
        try { stored = localStorage.getItem(STORAGE_KEY); } catch (e) {}
        _cur = norm(stored || preferred());
        return _cur;
    }

    function num(value, digits) {
        return (Number(value) || 0).toLocaleString(lang(), {
            minimumFractionDigits: digits, maximumFractionDigits: digits
        });
    }
    function scale(abs) {
        var u = units();
        if (abs >= 1e12) return [1e12, u.t];
        if (abs >= 1e9)  return [1e9,  u.b];
        if (abs >= 1e6)  return [1e6,  u.m];
        if (abs >= 1e3)  return [1e3,  u.k];
        return [1, ''];
    }
    function decimalsFor(f) { return f >= 1e9 ? 2 : (f >= 1e6 ? 1 : 0); }

    // « 4,25 Md » (sans devise) — pour les axes de graphes.
    function compactNumber(value) {
        var v = Number(value) || 0;
        var abs = Math.abs(v);
        var s = scale(abs);
        var text = num(abs / s[0], s[0] === 1 ? 0 : decimalsFor(s[0]));
        return (v < 0 ? '-' : '') + text + (s[1] ? ' ' + s[1] : '');
    }
    // « 4,25 Md GNF » — pour les tooltips et libellés.
    function compact(value, cur) {
        return compactNumber(value) + ' ' + norm(cur || currency());
    }
    // « 4 250 000 000 GNF » — montant complet.
    function full(value, cur) {
        return num(value, 0) + ' ' + norm(cur || currency());
    }
    function format(value, opts) {
        opts = opts || {};
        return opts.full ? full(value, opts.currency) : compact(value, opts.currency);
    }

    // Rend tous les [data-money] selon la devise courante.
    function apply(root) {
        root = root || document;
        var nodes = root.querySelectorAll('[data-money]');
        for (var i = 0; i < nodes.length; i++) {
            var el = nodes[i];
            var gnf = parseFloat(el.getAttribute('data-gnf'));
            var usd = parseFloat(el.getAttribute('data-usd'));
            var value = currency() === 'USD' ? usd : gnf;
            if (isNaN(value)) value = 0;
            el.textContent = el.getAttribute('data-money') === 'full'
                ? full(value) : compact(value);
        }
    }

    function onChange(fn) {
        if (typeof fn === 'function') window.addEventListener('csig:curexchange', fn);
    }

    function set(c) {
        c = norm(c);
        if (c === currency()) { apply(); return; }
        _cur = c;
        try { localStorage.setItem(STORAGE_KEY, c); } catch (e) {}
        document.querySelectorAll('[data-currency-switch] .cur-switch-btn').forEach(function (b) {
            b.classList.toggle('active', b.getAttribute('data-cur') === c);
        });
        apply();
        var detail = { currency: c };
        var ev;
        try { ev = new CustomEvent('csig:curexchange', { detail: detail }); }
        catch (e) { ev = document.createEvent('CustomEvent'); ev.initCustomEvent('csig:curexchange', false, false, detail); }
        window.dispatchEvent(ev);
    }

    // Construit les boutons du switch dans chaque [data-currency-switch].
    function mount(root) {
        root = root || document;
        var holders = root.querySelectorAll('[data-currency-switch]');
        for (var i = 0; i < holders.length; i++) {
            (function (holder) {
                if (holder.getAttribute('data-mounted') === '1') return;
                holder.setAttribute('data-mounted', '1');
                holder.classList.add('cur-switch');
                SUPPORTED.forEach(function (c) {
                    var b = document.createElement('button');
                    b.type = 'button';
                    b.className = 'cur-switch-btn' + (c === currency() ? ' active' : '');
                    b.setAttribute('data-cur', c);
                    b.textContent = c;
                    b.addEventListener('click', function () { set(c); });
                    holder.appendChild(b);
                });
            })(holders[i]);
        }
    }

    return {
        get currency() { return currency(); },
        set: set,
        onChange: onChange,
        compact: compact,
        compactNumber: compactNumber,
        full: full,
        format: format,
        apply: apply,
        mount: mount
    };
})();

document.addEventListener('DOMContentLoaded', function () {
    window.CSIGMoney.mount();
    window.CSIGMoney.apply();
});

function initializeApp() {
    // Add active class to current nav item
    highlightActiveNav();
    
    // Initialize search functionality
    initializeSearch();
    
    // Initialize filter handlers
    initializeFilters();

    // Initialize clickable cards
    initializeClickableCards();
}

function highlightActiveNav() {
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.sidebar-nav a');
    
    navLinks.forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });
}

function initializeSearch() {
    const searchInputs = document.querySelectorAll('.search-box input');
    
    searchInputs.forEach(input => {
        let timeout;
        input.addEventListener('input', function() {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                const form = this.closest('form');
                if (form) {
                    form.submit();
                }
            }, 500);
        });
    });
}

function initializeFilters() {
    const filterSelects = document.querySelectorAll('.filters-bar select');
    
    filterSelects.forEach(select => {
        select.addEventListener('change', function() {
            const form = this.closest('form');
            if (form) {
                form.submit();
            }
        });
    });
}

function initializeClickableCards() {
    const clickableCards = document.querySelectorAll('[data-href]');

    clickableCards.forEach(card => {
        const href = card.getAttribute('data-href');
        if (!href) return;

        card.style.cursor = 'pointer';

        card.addEventListener('click', function(e) {
            const target = e.target;

            if (target && target.closest) {
                if (target.closest('a, button, input, select, textarea')) return;
                if (target.closest('.btn, .action-btn')) return;
            }

            window.location.href = href;
        });

        card.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                window.location.href = href;
            }
        });

        if (!card.hasAttribute('tabindex')) {
            card.setAttribute('tabindex', '0');
        }
    });
}

// Format currency in GNF
function formatCurrency(value) {
    const locale = getUserLocale();
    if (value >= 1000000000) {
        return (value / 1000000000).toFixed(1) + gettext(' Md GNF');
    }
    if (value >= 1000000) {
        return (value / 1000000).toFixed(0) + gettext(' M GNF');
    }
    return value.toLocaleString(locale) + gettext(' GNF');
}

// Format date
function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString(getUserLocale(), {
        day: 'numeric',
        month: 'long',
        year: 'numeric'
    });
}

// Get progress bar color based on value
function getProgressColor(value) {
    if (value >= 80) return 'green';
    if (value >= 50) return 'blue';
    if (value >= 25) return 'amber';
    return 'red';
}

// Toggle element visibility
function toggleElement(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.classList.toggle('hidden');
    }
}

// Show notification
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.classList.add('show');
    }, 100);
    
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 3000);
}

// Confirm action
function confirmAction(message, callback) {
    window.csigConfirm({ title: gettext('Confirmation'), message: message, label: gettext('Confirmer') })
        .then(function(ok){ if(ok) callback(); });
}

// API helper functions
async function fetchData(url) {
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching data:', error);
        return null;
    }
}

async function postData(url, data) {
    try {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(data)
        });
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return await response.json();
    } catch (error) {
        console.error('Error posting data:', error);
        return null;
    }
}

// Calendar navigation
function navigateCalendar(year, month) {
    window.location.href = `/calendrier/?year=${year}&month=${month}`;
}

// Select calendar day
function selectCalendarDay(day) {
    const days = document.querySelectorAll('.calendar-day');
    days.forEach(d => d.classList.remove('selected'));
    
    const selectedDay = document.querySelector(`.calendar-day[data-day="${day}"]`);
    if (selectedDay) {
        selectedDay.classList.add('selected');
    }
}

// Toggle request details
function toggleRequestDetails(requestId) {
    const details = document.getElementById(`request-details-${requestId}`);
    if (details) {
        details.classList.toggle('hidden');
    }
}

// Select partner
function selectPartner(partnerId) {
    const cards = document.querySelectorAll('.partner-card');
    cards.forEach(card => card.classList.remove('selected'));
    
    const selectedCard = document.querySelector(`.partner-card[data-id="${partnerId}"]`);
    if (selectedCard) {
        selectedCard.classList.add('selected');
    }
}

// Tab switching
function switchTab(tabName) {
    window.location.href = `?tab=${tabName}`;
}

// Export functionality
function exportToPDF() {
    showNotification(gettext('Export PDF en cours...'), 'info');
    window.location.href = '/rapports/export/pdf/';
}

function exportToExcel() {
    showNotification(gettext('Export Excel en cours...'), 'info');
    // Implement Excel export logic
}

// Initialize searchable select dropdowns
document.addEventListener('DOMContentLoaded', function() {
    initSearchableSelects();
});

function initSearchableSelects() {
    const selects = document.querySelectorAll('select.select-searchable');
    
    selects.forEach(select => {
        // Create container
        const container = document.createElement('div');
        container.className = 'select-search-container';
        
        // Create search input
        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.className = 'search-input';
        searchInput.placeholder = gettext('Rechercher une devise...');
        
        // Get selected option text
        const selectedOption = select.options[select.selectedIndex];
        if (selectedOption) {
            searchInput.value = selectedOption.text;
        }
        
        // Create dropdown
        const dropdown = document.createElement('div');
        dropdown.className = 'dropdown';
        
        // Populate dropdown with options
        Array.from(select.options).forEach(option => {
            const item = document.createElement('div');
            item.className = 'dropdown-item';
            item.textContent = option.text;
            item.dataset.value = option.value;
            
            if (option.selected) {
                item.classList.add('selected');
            }
            
            item.addEventListener('click', function() {
                select.value = this.dataset.value;
                searchInput.value = this.textContent;
                dropdown.classList.remove('show');
                
                // Update selected class
                dropdown.querySelectorAll('.dropdown-item').forEach(i => i.classList.remove('selected'));
                this.classList.add('selected');
                
                // Trigger change event
                select.dispatchEvent(new Event('change'));
            });
            
            dropdown.appendChild(item);
        });
        
        // Hide original select
        select.style.display = 'none';
        
        // Insert container
        select.parentNode.insertBefore(container, select);
        container.appendChild(searchInput);
        container.appendChild(dropdown);
        container.appendChild(select);
        
        // Toggle dropdown on input focus
        searchInput.addEventListener('focus', function() {
            dropdown.classList.add('show');
            this.select();
        });
        
        // Filter options on input
        searchInput.addEventListener('input', function() {
            const filter = this.value.toLowerCase();
            const items = dropdown.querySelectorAll('.dropdown-item');
            let hasResults = false;
            
            items.forEach(item => {
                const text = item.textContent.toLowerCase();
                if (text.includes(filter)) {
                    item.classList.remove('hidden');
                    hasResults = true;
                } else {
                    item.classList.add('hidden');
                }
            });
            
            // Show/hide no results message
            let noResults = dropdown.querySelector('.no-results');
            if (!hasResults) {
                if (!noResults) {
                    noResults = document.createElement('div');
                    noResults.className = 'no-results';
                    noResults.textContent = gettext('Aucun résultat trouvé');
                    dropdown.appendChild(noResults);
                }
                noResults.style.display = 'block';
            } else if (noResults) {
                noResults.style.display = 'none';
            }
        });
        
        // Close dropdown when clicking outside
        document.addEventListener('click', function(e) {
            if (!container.contains(e.target)) {
                dropdown.classList.remove('show');
                // Reset to selected value if input is empty or invalid
                const selectedItem = dropdown.querySelector('.dropdown-item.selected');
                if (selectedItem) {
                    searchInput.value = selectedItem.textContent;
                }
            }
        });
    });
}
