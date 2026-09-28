/*
 * grafy.js — grafy na stránce Grafy (Chart.js)
 * -----------------------------------------------------------------------------
 * Data vkládá server do <script type="application/json" id="graf-data">.
 * Každý <canvas data-graf="…"> kreslí jednu skupinu měřičů se společnou jednotkou
 * (jedna osa na graf). Barvy se čtou z tokenů app.css (--color-series-<slot>,
 * text, mřížka, povrch), takže grafy sledují světlý i tmavý motiv.
 */

(function () {
    'use strict';

    var zdroj = null;
    var grafy = [];
    // Index měsíce/záznamu pod myší – zvýrazní se ve všech grafech najednou
    var aktivni = null;
    var cislo = new Intl.NumberFormat('cs-CZ', { maximumFractionDigits: 1 });

    function token(nazev) {
        return getComputedStyle(document.documentElement).getPropertyValue(nazev).trim();
    }

    // Tokeny barev jsou ve tvaru #rrggbb
    function sPruhlednosti(barva, alfa) {
        var n = parseInt(barva.slice(1), 16);
        return 'rgba(' + ((n >> 16) & 255) + ', ' + ((n >> 8) & 255) + ', ' + (n & 255) + ', ' + alfa + ')';
    }

    function rada(meric) {
        return zdroj.data.rady[meric.key];
    }

    function datovaRada(meric, mesice, povrch) {
        var hodnoty = rada(meric);
        var barva = token('--color-series-' + meric.slot);
        var odhad = function (index) { return hodnoty.odhad[index]; };
        return {
            label: hodnoty.label,
            klic: meric.key,
            data: hodnoty.hodnoty,
            // Při najetí myší zůstane plný jen sloupec pod kurzorem, ostatní se ztlumí
            backgroundColor: mesice
                ? function (c) { return aktivni !== null && c.dataIndex !== aktivni ? sPruhlednosti(barva, 0.35) : barva; }
                : barva,
            hoverBackgroundColor: barva,
            borderColor: barva,
            borderWidth: mesice ? 0 : 2,
            borderRadius: mesice ? 4 : 0,
            borderSkipped: 'start',
            maxBarThickness: 24,
            // Body čáry: plné s prstencem barvy povrchu, uložený odhad dutý
            pointRadius: mesice ? 0 : 4,
            pointHoverRadius: 6,
            pointBackgroundColor: function (c) { return odhad(c.dataIndex) ? povrch : barva; },
            pointBorderColor: function (c) { return odhad(c.dataIndex) ? barva : povrch; },
            pointBorderWidth: 2,
            segment: {
                borderDash: function (s) {
                    return odhad(s.p0DataIndex) || odhad(s.p1DataIndex) ? [6, 4] : undefined;
                }
            },
            spanGaps: false,
            tension: 0
        };
    }

    // Zvýraznění stejného indexu ve všech grafech: ztlumení ostatních sloupců a tooltip
    function zvyraznit(index) {
        if (index === aktivni) return;
        aktivni = index;
        grafy.forEach(function (graf) {
            var prvky = [];
            if (index !== null) {
                graf.data.datasets.forEach(function (rada, i) {
                    if (rada.data[index] !== null && rada.data[index] !== undefined) {
                        prvky.push({ datasetIndex: i, index: index });
                    }
                });
            }
            graf.setActiveElements(prvky);
            graf.tooltip.setActiveElements(prvky, { x: 0, y: 0 });
            graf.update('none');
        });
    }

    function vykreslit() {
        grafy.forEach(function (graf) { graf.destroy(); });
        grafy = [];
        aktivni = null;

        var mesice = zdroj.rezim === 'mesice';
        var text = token('--color-text-light');
        var mrizka = token('--color-border');
        var povrch = token('--color-surface');

        document.querySelectorAll('canvas[data-graf]').forEach(function (canvas) {
            var merice = zdroj.merice.filter(function (meric) { return meric.graf === canvas.dataset.graf; });
            var datasets = merice.map(function (meric) { return datovaRada(meric, mesice, povrch); });

            grafy.push(new Chart(canvas.getContext('2d'), {
                type: mesice ? 'bar' : 'line',
                data: { labels: zdroj.data.popisky, datasets: datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: { duration: 250 },
                    interaction: { mode: 'index', intersect: false },
                    onHover: function (udalost, prvky) {
                        zvyraznit(prvky.length ? prvky[0].index : null);
                    },
                    plugins: {
                        // Jedna řada legendu nepotřebuje, název nese nadpis karty
                        // Značka řady má barvu řady: u sloupců zaoblený čtverec, u čar krátká čára
                        // (bodový styl čáry by vzal prstenec prvního bodu v barvě povrchu)
                        legend: {
                            display: datasets.length > 1,
                            position: 'top',
                            align: 'start',
                            labels: mesice
                                ? { color: token('--color-text-2'), usePointStyle: true, pointStyle: 'rectRounded', padding: 16 }
                                : { color: token('--color-text-2'), boxWidth: 18, boxHeight: 2, padding: 16 }
                        },
                        tooltip: {
                            backgroundColor: token('--color-text'),
                            titleColor: token('--color-bg'),
                            bodyColor: token('--color-bg'),
                            footerColor: token('--color-bg'),
                            footerFont: { weight: 'normal' },
                            boxWidth: 12,
                            boxHeight: 3,
                            padding: 10,
                            cornerRadius: 8,
                            callbacks: {
                                labelColor: function (polozka) {
                                    var barva = polozka.dataset.borderColor;
                                    return { borderColor: barva, backgroundColor: barva, borderWidth: 0 };
                                },
                                title: function (polozky) {
                                    return polozky.length ? zdroj.data.popisky_dlouhe[polozky[0].dataIndex] : '';
                                },
                                label: function (polozka) {
                                    var hodnoty = zdroj.data.rady[polozka.dataset.klic];
                                    var odhad = hodnoty.odhad[polozka.dataIndex] ? ' (odhad)' : '';
                                    return cislo.format(polozka.parsed.y) + ' ' + hodnoty.jednotka + '  ' + hodnoty.label + odhad;
                                },
                                // Měřiče bez hodnoty v daném bodě i s důvodem (výměna měřiče, bez údajů)
                                footer: function (polozky) {
                                    if (!polozky.length) return '';
                                    var index = polozky[0].dataIndex;
                                    return merice
                                        .filter(function (meric) { return rada(meric).hodnoty[index] === null; })
                                        .map(function (meric) {
                                            return rada(meric).label + ': ' + (rada(meric).poznamka[index] || 'bez údajů');
                                        });
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            ticks: { color: text, maxRotation: 0, autoSkipPadding: 16 },
                            grid: { display: false },
                            border: { color: mrizka }
                        },
                        y: {
                            ticks: { color: text, callback: function (hodnota) { return cislo.format(hodnota); } },
                            grid: { color: mrizka },
                            border: { display: false }
                        }
                    }
                }
            }));
        });
    }

    function bezKnihovny() {
        document.querySelectorAll('.graf').forEach(function (obal) {
            var zprava = document.createElement('p');
            zprava.className = 'text-muted text-sm';
            zprava.textContent = 'Graf se nepodařilo načíst (knihovna Chart.js není dostupná). Hodnoty najdete v tabulce níže.';
            obal.replaceChildren(zprava);
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        var data = document.getElementById('graf-data');
        if (!data) return;
        if (typeof Chart === 'undefined') {
            bezKnihovny();
            return;
        }
        zdroj = JSON.parse(data.textContent);
        vykreslit();

        // Po odjetí myši z grafu zvýraznění zrušit (canvasy se při překreslení nemění)
        document.querySelectorAll('canvas[data-graf]').forEach(function (canvas) {
            canvas.addEventListener('mouseleave', function () { zvyraznit(null); });
        });

        // Překreslit při přepnutí motivu v zápatí i při změně motivu systému
        new MutationObserver(vykreslit).observe(document.documentElement, {
            attributes: true,
            attributeFilter: ['data-theme']
        });
        var tmavy = window.matchMedia('(prefers-color-scheme: dark)');
        if (tmavy.addEventListener) tmavy.addEventListener('change', vykreslit);
    });
})();
