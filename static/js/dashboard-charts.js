/**
 * StockX Pro — Dashboard Charts (Heidi Health Inspired)
 * Uses Chart.js with warm, professional palette
 */

// ===== NAV History Chart (used on index.html) =====
function initPerformanceChart(labels, data) {
    const canvas = document.getElementById('performanceChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    // Warm gradient matching Heidi palette
    const gradient = ctx.createLinearGradient(0, 0, 0, 350);
    gradient.addColorStop(0, 'rgba(251, 245, 130, 0.28)');  // primary gold
    gradient.addColorStop(0.5, 'rgba(251, 245, 130, 0.10)');
    gradient.addColorStop(1, 'rgba(251, 245, 130, 0.02)');

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: '账户净值 (NAV)',
                data: data,
                borderColor: '#755760',           // secondary mauve
                backgroundColor: gradient,
                fill: true,
                tension: 0.35,
                pointRadius: 3,
                pointBackgroundColor: '#755760',
                pointBorderColor: '#FFFFFF',
                pointBorderWidth: 2,
                pointHoverRadius: 7,
                pointHoverBackgroundColor: '#755760',
                pointHoverBorderColor: '#FFFFFF',
                pointHoverBorderWidth: 3,
                borderWidth: 2.5,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#FFFFFF',
                    titleColor: '#28030F',
                    bodyColor: '#28030F',
                    borderColor: '#EDE8E4',
                    borderWidth: 1,
                    cornerRadius: 8,
                    padding: 14,
                    displayColors: false,
                    callbacks: {
                        label: function(ctx) {
                            return '¥ ' + parseFloat(ctx.raw).toLocaleString('zh-CN', {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2
                            });
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: false,
                    grid: { color: 'rgba(0,0,0,0.04)' },
                    ticks: {
                        callback: function(v) {
                            return '¥' + (v / 10000).toFixed(1) + '万';
                        },
                        color: '#6B5E62',
                        font: { size: 11 }
                    }
                },
                x: {
                    grid: { display: false },
                    ticks: {
                        maxTicksLimit: 8,
                        color: '#6B5E62',
                        font: { size: 11 }
                    }
                }
            }
        }
    });
}

// ===== Financial Indicator Chart (used on detail.html) =====
function initFinancialChart(labels, debtData, currentData, quickData, canvasId) {
    const canvas = document.getElementById(canvasId || 'financialChart');
    if (!canvas) return;

    new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: '资产负债率 (%)',
                    data: debtData,
                    borderColor: '#D93A3A',
                    backgroundColor: 'rgba(217,58,58,0.06)',
                    fill: true,
                    tension: 0.3,
                    borderWidth: 2,
                    pointRadius: 2,
                    pointHoverRadius: 5,
                },
                {
                    label: '流动比率',
                    data: currentData,
                    borderColor: '#2FA84F',
                    backgroundColor: 'rgba(47,168,79,0.06)',
                    fill: true,
                    tension: 0.3,
                    borderWidth: 2,
                    pointRadius: 2,
                    pointHoverRadius: 5,
                },
                {
                    label: '速动比率',
                    data: quickData,
                    borderColor: '#755760',
                    backgroundColor: 'rgba(117,87,96,0.06)',
                    fill: true,
                    tension: 0.3,
                    borderWidth: 2,
                    pointRadius: 2,
                    pointHoverRadius: 5,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        usePointStyle: true,
                        padding: 20,
                        color: '#6B5E62',
                        font: { size: 12, family: 'Inter, sans-serif' }
                    }
                },
                tooltip: {
                    backgroundColor: '#FFFFFF',
                    titleColor: '#28030F',
                    bodyColor: '#28030F',
                    borderColor: '#EDE8E4',
                    borderWidth: 1,
                    cornerRadius: 8,
                    padding: 12,
                }
            },
            scales: {
                y: {
                    grid: { color: 'rgba(0,0,0,0.04)' },
                    ticks: { color: '#6B5E62', font: { size: 11 } }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#6B5E62', font: { size: 11 } }
                }
            }
        }
    });
}

// ===== Price History Chart =====
function initPriceChart(labels, closePrices, volumes, canvasId) {
    const canvas = document.getElementById(canvasId || 'priceChart');
    if (!canvas) return;

    new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: '收盘价',
                data: closePrices,
                borderColor: '#755760',
                backgroundColor: 'rgba(117,87,96,0.08)',
                fill: true,
                tension: 0.25,
                borderWidth: 2.5,
                pointRadius: 2,
                pointHoverRadius: 6,
                pointBackgroundColor: '#755760',
                pointBorderColor: '#FFF',
                pointBorderWidth: 2,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#FFFFFF',
                    titleColor: '#28030F',
                    bodyColor: '#28030F',
                    borderColor: '#EDE8E4',
                    borderWidth: 1,
                    cornerRadius: 8,
                    padding: 12,
                    callbacks: {
                        label: ctx => '收盘价: ¥' + parseFloat(ctx.raw).toFixed(2)
                    }
                }
            },
            scales: {
                y: {
                    grid: { color: 'rgba(0,0,0,0.04)' },
                    ticks: { color: '#6B5E62', callback: v => '¥' + v.toFixed(1) }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#6B5E62', maxTicksLimit: 10 }
                }
            }
        }
    });
}