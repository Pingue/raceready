// Theme management — dark / light / system
window.RRTheme = (function () {
    var STORAGE_KEY = 'rr-theme';
    var systemQuery = window.matchMedia('(prefers-color-scheme: dark)');

    function getSaved() {
        return localStorage.getItem(STORAGE_KEY) || 'system';
    }

    function applyTheme(theme) {
        var dark = theme === 'dark' || (theme === 'system' && systemQuery.matches);
        document.documentElement.classList.toggle('dark-mode', dark);
    }

    function updateUI(theme) {
        var labels = { system: 'Auto', light: 'Light', dark: 'Dark' };
        var el = document.getElementById('theme-label');
        if (el) el.textContent = labels[theme] || 'Auto';

        document.querySelectorAll('.theme-option').forEach(function (opt) {
            opt.classList.remove('active');
        });
        var active = document.getElementById('theme-opt-' + theme);
        if (active) active.classList.add('active');
    }

    function setTheme(theme) {
        localStorage.setItem(STORAGE_KEY, theme);
        applyTheme(theme);
        updateUI(theme);
        // Let index.js update background color if checkAllGreen is defined
        if (typeof checkAllGreen === 'function') checkAllGreen();
    }

    // Apply immediately to avoid flash
    applyTheme(getSaved());

    // React to OS-level preference changes
    systemQuery.addEventListener('change', function () {
        if (getSaved() === 'system') {
            applyTheme('system');
            if (typeof checkAllGreen === 'function') checkAllGreen();
        }
    });

    document.addEventListener('DOMContentLoaded', function () {
        updateUI(getSaved());
        document.querySelectorAll('.theme-option').forEach(function (opt) {
            opt.addEventListener('click', function (e) {
                e.preventDefault();
                setTheme(this.getAttribute('data-theme'));
            });
        });
    });

    return { setTheme: setTheme, getSaved: getSaved };
})();
