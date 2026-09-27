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

// Toast, který přežije přesměrování nebo znovunačtení stránky
function flashToast(message, type = 'success') {
    try {
        sessionStorage.setItem('flashToast', JSON.stringify({ message, type }));
    } catch (e) {
        // Úložiště nemusí být dostupné (soukromé okno), hláška se pak jen nezobrazí
    }
}

function showFlashToast() {
    let flash = null;
    try {
        flash = JSON.parse(sessionStorage.getItem('flashToast') || 'null');
        sessionStorage.removeItem('flashToast');
    } catch (e) {
        return;
    }
    if (flash && flash.message) showToast(flash.message, flash.type);
}

document.addEventListener('DOMContentLoaded', showFlashToast);

// Text chyby z odpovědi API; detail bývá řetězec, u chyb validace pole objektů
function formatApiError(body, fallback = 'Neznámá chyba') {
    const detail = body && body.detail;
    if (typeof detail === 'string' && detail) return detail;
    if (Array.isArray(detail)) {
        const zpravy = detail
            .map(chyba => String((chyba && chyba.msg) || '').replace(/^Value error, /, ''))
            .filter(Boolean);
        if (zpravy.length) return zpravy.join('; ');
    }
    return fallback;
}

// Volání API s JSON tělem; při chybě vyhodí Error s hláškou pro uživatele
async function apiFetch(url, { json, ...options } = {}) {
    const init = { ...options, headers: { ...(options.headers || {}) } };
    if (json !== undefined) {
        init.body = JSON.stringify(json);
        init.headers['Content-Type'] = 'application/json';
    }

    let response;
    try {
        response = await fetch(url, init);
    } catch (e) {
        throw new Error('Server je nedostupný, zkuste to prosím znovu');
    }

    const body = await response.json().catch(() => null);
    if (!response.ok) {
        throw new Error(formatApiError(body, `Chyba serveru (${response.status})`));
    }
    return body;
}

// Modální potvrzovací dialog, nahrazuje nativní confirm()
// Vrací true (potvrzení), false (zrušení) nebo 'alt' (volitelné prostřední tlačítko)
function showConfirm(options = {}) {
    const config = typeof options === 'string' ? { message: options } : options;
    const {
        title = 'Potvrzení',
        message = '',
        confirmText = 'Potvrdit',
        cancelText = 'Zrušit',
        altText = null,
        variant = 'primary'
    } = config;

    return new Promise(resolve => {
        const titleId = 'modal-title-' + Date.now();
        const previouslyFocused = document.activeElement;

        const confirmColors = variant === 'danger'
            ? 'bg-red-600 hover:bg-red-700 focus-visible:ring-red-300'
            : 'bg-blue-600 hover:bg-blue-700 focus-visible:ring-blue-300';
        const secondaryClass = 'inline-flex items-center px-4 py-2 text-sm font-medium bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-200 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gray-300 transition-colors';

        const overlay = document.createElement('div');
        overlay.className = 'modal fixed inset-0 flex items-center justify-center p-4 bg-gray-900/50';
        overlay.setAttribute('role', 'dialog');
        overlay.setAttribute('aria-modal', 'true');
        overlay.setAttribute('aria-labelledby', titleId);
        overlay.innerHTML = `
            <div class="w-full max-w-xl bg-white dark:bg-gray-800 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 p-6">
                <h2 id="${titleId}" class="text-lg font-semibold text-gray-900 dark:text-white mb-2"></h2>
                <p class="text-sm text-gray-600 dark:text-gray-400 mb-6 whitespace-pre-line"></p>
                <div class="flex flex-wrap justify-end gap-3">
                    <button type="button" data-modal-cancel class="${secondaryClass}"></button>
                    ${altText ? `<button type="button" data-modal-alt class="${secondaryClass}"></button>` : ''}
                    <button type="button" data-modal-confirm class="inline-flex items-center px-4 py-2 text-sm font-medium text-white rounded-lg ${confirmColors} focus-visible:outline-none focus-visible:ring-2 transition-colors"></button>
                </div>
            </div>
        `;

        const cancelBtn = overlay.querySelector('[data-modal-cancel]');
        const altBtn = overlay.querySelector('[data-modal-alt]');
        const confirmBtn = overlay.querySelector('[data-modal-confirm]');
        const buttons = [...overlay.querySelectorAll('button')];
        overlay.querySelector('h2').textContent = title;
        overlay.querySelector('p').textContent = message;
        cancelBtn.textContent = cancelText;
        if (altBtn) altBtn.textContent = altText;
        confirmBtn.textContent = confirmText;

        function close(result) {
            document.removeEventListener('keydown', onKeydown, true);
            overlay.remove();
            document.body.classList.remove('overflow-hidden');
            if (previouslyFocused && document.contains(previouslyFocused)) {
                previouslyFocused.focus();
            }
            resolve(result);
        }

        function onKeydown(e) {
            if (e.key === 'Escape') {
                e.preventDefault();
                close(false);
                return;
            }
            // Udržení focusu uvnitř dialogu
            if (e.key === 'Tab') {
                e.preventDefault();
                const index = buttons.indexOf(document.activeElement);
                const posun = e.shiftKey ? -1 : 1;
                buttons[(index + posun + buttons.length) % buttons.length].focus();
            }
        }

        cancelBtn.addEventListener('click', () => close(false));
        if (altBtn) altBtn.addEventListener('click', () => close('alt'));
        confirmBtn.addEventListener('click', () => close(true));
        overlay.addEventListener('click', e => {
            if (e.target === overlay) close(false);
        });
        document.addEventListener('keydown', onKeydown, true);

        document.body.classList.add('overflow-hidden');
        document.body.appendChild(overlay);
        confirmBtn.focus();
    });
}

// Zablokuje tlačítko během požadavku, vrací funkci pro obnovení původního stavu
function zamknoutTlacitko(button, text) {
    const puvodni = button.innerHTML;
    button.disabled = true;
    button.innerHTML = `<span class="animate-spin rounded-full h-4 w-4 border-b-2 border-current mr-2"></span>${escapeHtml(text)}`;
    return () => {
        button.disabled = false;
        button.innerHTML = puvodni;
    };
}

// Uložení odečtu z formuláře evidence nebo editace
// Před uložením se ověří návaznost na okolní ruční odečty; pokles stavu nabídne uložit jako výměnu měřiče
async function ulozitOdecet(form, { url, method, recordId = null, zprava }) {
    if (form.dataset.ukladam) return;
    form.dataset.ukladam = '1';
    const odemknoutTlacitko = zamknoutTlacitko(form.querySelector('button[type="submit"]'), 'Ukládám...');
    const odemknout = () => {
        odemknoutTlacitko();
        delete form.dataset.ukladam;
    };

    try {
        const data = { datum: form.elements.datum.value };
        form.querySelectorAll('[data-meter]').forEach(input => {
            data[input.dataset.meter] = input.value === '' ? null : Number(input.value);
        });
        form.querySelectorAll('[data-vymena]').forEach(checkbox => {
            data[`vymena_${checkbox.dataset.vymena}`] = checkbox.checked;
        });
        if (form.elements.source) data.source = form.elements.source.checked;

        const kontrola = await apiFetch('/api/spotreba/kontrola', { method: 'POST', json: { ...data, id: recordId } });
        if (kontrola.varovani.length) {
            const pokles = kontrola.varovani.filter(v => v.typ === 'nizsi_nez_predchozi');
            const volba = await showConfirm({
                title: 'Zkontrolujte odečet',
                message: kontrola.varovani.map(v => `• ${v.zprava}`).join('\n')
                    + (pokles.length ? '\n\nPokud byl měřič vyměněn, uložte odečet jako výměnu – rozdíl se pak nezapočítá jako spotřeba.' : ''),
                cancelText: 'Zpět k úpravě',
                altText: pokles.length ? 'Uložit přesto' : null,
                confirmText: pokles.length ? 'Uložit jako výměnu měřiče' : 'Uložit přesto'
            });
            if (volba === false) {
                odemknout();
                return;
            }
            if (volba === true) {
                pokles.forEach(v => { data[`vymena_${v.meric}`] = true; });
            }
        }

        const vysledek = await apiFetch(url, { method, json: data });
        flashToast(vysledek.prepocteno_odhadu
            ? `${zprava}. Přepočítané odhady: ${vysledek.prepocteno_odhadu}.`
            : zprava);
        window.location.href = '/';
    } catch (error) {
        showToast(error.message, 'error');
        odemknout();
    }
}

// Ctrl+S / Cmd+S odešle formulář stejně jako tlačítko, včetně kontroly povinných polí
document.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        const form = document.querySelector('form[data-save-shortcut]');
        if (!form) return;
        e.preventDefault();
        form.requestSubmit();
    }
});
