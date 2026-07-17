/* ============================================================
   Pharmacy Management — Web UI JavaScript
   Vanilla JS for interactivity, AJAX, theme toggle
   ============================================================ */

(function() {
    'use strict';

    // ── Theme Toggle ──────────────────────────────────────
    const html = document.documentElement;
    const themeBtn = document.getElementById('themeToggle');

    function getTheme() {
        return html.getAttribute('data-theme') || 'dark';
    }

    function setTheme(theme) {
        html.setAttribute('data-theme', theme);
        localStorage.setItem('pharmacy-theme', theme);
        fetch('/api/settings/theme', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({theme: theme})
        }).catch(() => {});
    }

    const saved = localStorage.getItem('pharmacy-theme');
    if (saved) {
        html.setAttribute('data-theme', saved);
    }

    if (themeBtn) {
        themeBtn.addEventListener('click', function() {
            setTheme(getTheme() === 'dark' ? 'light' : 'dark');
        });
    }

    // ── Search-as-you-type ────────────────────────────────
    document.querySelectorAll('[data-search-url]').forEach(function(el) {
        const url = el.getAttribute('data-search-url');
        const target = document.querySelector(el.getAttribute('data-search-target'));
        let timer;
        el.addEventListener('input', function() {
            clearTimeout(timer);
            timer = setTimeout(function() {
                const params = new URLSearchParams(window.location.search);
                params.set('q', el.value);
                window.location.search = params.toString();
            }, 300);
        });
    });

    // ── Modal helpers ─────────────────────────────────────
    window.openModal = function(id) {
        const m = document.getElementById(id);
        if (m) m.classList.add('active');
    };

    window.closeModal = function(id) {
        const m = document.getElementById(id);
        if (m) m.classList.remove('active');
    };

    window.closeAllModals = function() {
        document.querySelectorAll('.modal-overlay').forEach(function(m) {
            m.classList.remove('active');
        });
    };

    document.querySelectorAll('.modal-overlay').forEach(function(overlay) {
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) {
                overlay.classList.remove('active');
            }
        });
    });

    // ── Flash auto-dismiss ────────────────────────────────
    document.querySelectorAll('.flash').forEach(function(el) {
        setTimeout(function() {
            el.style.transition = 'opacity 0.3s';
            el.style.opacity = '0';
            setTimeout(function() { el.remove(); }, 300);
        }, 4000);
    });

    // ── AJAX helper ───────────────────────────────────────
    window.api = {
        post: function(url, data) {
            return fetch(url, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            }).then(function(r) { return r.json(); });
        },
        put: function(url, data) {
            return fetch(url, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            }).then(function(r) { return r.json(); });
        },
        del: function(url) {
            return fetch(url, {
                method: 'DELETE',
            }).then(function(r) { return r.json(); });
        },
        get: function(url) {
            return fetch(url).then(function(r) { return r.json(); });
        }
    };

    // ── Confirm dialog ────────────────────────────────────
    window.confirmAction = function(msg, onConfirm) {
        if (confirm(msg)) {
            onConfirm();
        }
    };

})();
