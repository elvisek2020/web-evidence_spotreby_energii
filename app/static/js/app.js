// Hlavní JavaScript aplikace

function escapeHtml(str) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(String(str)));
    return div.innerHTML;
}

// Toast notifikace
function showToast(message, type = 'info', duration = 5000) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    
    const toast = document.createElement('div');
    const toastId = 'toast-' + Date.now();
    const safeType = ['success', 'error', 'warning', 'info'].includes(type) ? type : 'info';
    
    const colors = {
        success: 'bg-green-50 border-green-200 text-green-800',
        error: 'bg-red-50 border-red-200 text-red-800',
        warning: 'bg-yellow-50 border-yellow-200 text-yellow-800',
        info: 'bg-blue-50 border-blue-200 text-blue-800'
    };
    
    const icons = {
        success: `<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>`,
        error: `<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>`,
        warning: `<path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>`,
        info: `<path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"/>`
    };

    const alertDiv = document.createElement('div');
    alertDiv.className = `max-w-sm w-full ${colors[safeType]} border rounded-lg p-4 shadow-lg`;
    alertDiv.setAttribute('role', 'alert');

    const msgEl = document.createElement('p');
    msgEl.className = 'text-sm font-medium';
    msgEl.textContent = message;

    alertDiv.innerHTML = `
        <div class="flex">
            <div class="flex-shrink-0">
                <svg class="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">${icons[safeType]}</svg>
            </div>
            <div class="ml-3"></div>
            <div class="ml-auto pl-3">
                <div class="-mx-1.5 -my-1.5">
                    <button data-close-toast class="inline-flex rounded-md p-1.5 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-blue-50 focus:ring-blue-600">
                        <span class="sr-only">Zavřít</span>
                        <svg class="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/>
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    `;
    alertDiv.querySelector('.ml-3').appendChild(msgEl);
    
    toast.id = toastId;
    toast.appendChild(alertDiv);
    container.appendChild(toast);

    let autoCloseTimer = setTimeout(() => closeToast(toastId), duration);
    
    toast.addEventListener('mouseenter', () => clearTimeout(autoCloseTimer));
    toast.addEventListener('mouseleave', () => {
        autoCloseTimer = setTimeout(() => closeToast(toastId), duration);
    });
}

document.addEventListener('click', function(e) {
    const btn = e.target.closest('[data-close-toast]');
    if (btn) {
        const toast = btn.closest('[id^="toast-"]');
        if (toast) toast.remove();
    }
});

function closeToast(toastId) {
    const toast = document.getElementById(toastId);
    if (toast) {
        toast.remove();
    }
}

// Utility funkce
function formatDate(date) {
    return new Date(date).toLocaleDateString('cs-CZ');
}

function formatNumber(number, decimals = 2) {
    return parseFloat(number).toFixed(decimals);
}

// Loading states
function setLoading(element, loading = true) {
    if (loading) {
        element.classList.add('loading');
        element.disabled = true;
    } else {
        element.classList.remove('loading');
        element.disabled = false;
    }
}

// Form validation
function validateForm(form) {
    const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');
    let isValid = true;
    
    inputs.forEach(input => {
        if (!input.value.trim()) {
            input.classList.add('input-error');
            isValid = false;
        } else {
            input.classList.remove('input-error');
        }
    });
    
    return isValid;
}

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Ctrl+S pro uložení formuláře
    if (e.ctrlKey && e.key === 's') {
        e.preventDefault();
        const form = document.querySelector('form');
        if (form) {
            form.dispatchEvent(new Event('submit'));
        }
    }
    
    // Esc pro zavření modálů
    if (e.key === 'Escape') {
        const modals = document.querySelectorAll('.modal');
        modals.forEach(modal => {
            if (modal.style.display !== 'none') {
                modal.style.display = 'none';
            }
        });
    }
});

// Respektování prefers-reduced-motion
if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    // Zrušení všech animací
    const style = document.createElement('style');
    style.textContent = `
        *, *::before, *::after {
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
        }
    `;
    document.head.appendChild(style);
}

// Inicializace aplikace
document.addEventListener('DOMContentLoaded', function() {
    // Nastavení focus na první interaktivní element
    const firstInteractive = document.querySelector('input, button, select, textarea, [tabindex]:not([tabindex="-1"])');
    if (firstInteractive) {
        firstInteractive.focus();
    }
    
    // Inicializace všech formulářů
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!validateForm(this)) {
                e.preventDefault();
                showToast('Prosím vyplňte všechna povinná pole', 'error');
            }
        });
    });
    
    // Inicializace tooltipů a popoverů
    const tooltips = document.querySelectorAll('[data-tooltip]');
    tooltips.forEach(tooltip => {
        tooltip.addEventListener('mouseenter', function() {
            // Implementace tooltipu
        });
    });
});

// Export pro použití v jiných souborech
window.App = {
    showToast,
    closeToast,
    formatDate,
    formatNumber,
    setLoading,
    validateForm,
    escapeHtml
};
