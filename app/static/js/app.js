// MCC App JavaScript

// --- Keyboard Shortcuts ---
document.addEventListener('keydown', function(e) {
    var target = e.target;
    var isInput = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT';

    // Ctrl+Space - AI Chat toggle (works everywhere)
    if (e.ctrlKey && e.code === 'Space') {
        e.preventDefault();
        toggleChatPanel();
        return;
    }

    // '/' - Focus global search (only when not in an input)
    if (e.key === '/' && !isInput && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        var searchInput = document.getElementById('global-search-input');
        if (searchInput) {
            document.getElementById('search-overlay').classList.remove('hidden');
            searchInput.focus();
        }
        return;
    }

    // Escape - Close track modal, search overlay, or chat panel
    if (e.key === 'Escape') {
        var trackModal = document.getElementById('track-modal-backdrop');
        if (trackModal && !trackModal.classList.contains('hidden')) {
            trackModal.classList.add('hidden');
            return;
        }
        var overlay = document.getElementById('search-overlay');
        if (overlay && !overlay.classList.contains('hidden')) {
            overlay.classList.add('hidden');
            return;
        }
        var chat = document.getElementById('ai-chat-panel');
        if (chat && !chat.classList.contains('hidden')) {
            chat.classList.add('hidden');
            return;
        }
    }

    // Shortcuts that only work outside inputs
    if (isInput) return;

    // Ctrl+T or just 'T' - Navigate to tasks
    if (e.key === 't' && !e.ctrlKey && !e.metaKey) {
        window.location.href = '/tasks/';
        return;
    }

    // 'D' - Daily ops
    if (e.key === 'd') {
        window.location.href = '/daily/';
        return;
    }

    // 'G' then 'H' - Go home (dashboard) — just 'H' for simplicity
    if (e.key === 'h') {
        window.location.href = '/';
        return;
    }

    // 'C' - Content pipeline
    if (e.key === 'c') {
        window.location.href = '/pipelines/content';
        return;
    }

    // 'R' - Roadmap
    if (e.key === 'r') {
        window.location.href = '/roadmap/';
        return;
    }

    // '?' - Show keyboard shortcuts help
    if (e.key === '?') {
        var help = document.getElementById('shortcuts-help');
        if (help) help.classList.toggle('hidden');
        return;
    }
});

// --- Chat Panel ---
function toggleChatPanel() {
    var panel = document.getElementById('ai-chat-panel');
    if (panel) {
        panel.classList.toggle('hidden');
    }
}

// --- Search ---
function closeSearch() {
    document.getElementById('search-overlay').classList.add('hidden');
}

// --- Init ---
document.addEventListener('DOMContentLoaded', function() {
    // AI Chat toggle button
    var toggleBtn = document.getElementById('ai-chat-toggle');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', toggleChatPanel);
    }

    // Search overlay: close on click outside
    var overlay = document.getElementById('search-overlay');
    if (overlay) {
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) closeSearch();
        });
    }
});

// --- HTMX Config ---
document.body.addEventListener('htmx:configRequest', function(e) {
    e.detail.headers['X-MCC-Page'] = window.location.pathname;
});

// HTMX loading indicator: add spinner class during request
document.body.addEventListener('htmx:beforeRequest', function(e) {
    var indicator = e.target.querySelector('.mcc-loading');
    if (indicator) indicator.classList.remove('hidden');
});

document.body.addEventListener('htmx:afterRequest', function(e) {
    var indicator = e.target.querySelector('.mcc-loading');
    if (indicator) indicator.classList.add('hidden');
});

// HTMX error handling
document.body.addEventListener('htmx:responseError', function(e) {
    var target = e.detail.target;
    if (target) {
        target.innerHTML = '<div class="text-center py-4 text-sm text-mcc-critical">Something went wrong. Please try again.</div>';
    }
});

document.body.addEventListener('htmx:sendError', function(e) {
    var target = e.detail.target;
    if (target) {
        target.innerHTML = '<div class="text-center py-4 text-sm text-mcc-critical">Connection error. Check that the server is running.</div>';
    }
});
