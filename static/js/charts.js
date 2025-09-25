/**
 * Scrobblarr Charts JavaScript
 * Chart.js integration for interactive scrobbles visualization
 * Story 25: Charts & Visualization Page
 */

class ScrobblarrCharts {
    constructor() {
        this.chart = null;
        this.config = {
            responsive: true,
            maintainAspectRatio: false,
            backgroundColor: '#1e1e1e',
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: '#2a2a2a',
                    titleColor: '#e0e0e0',
                    bodyColor: '#e0e0e0',
                    borderColor: '#bb86fc',
                    borderWidth: 1,
                    titleFont: {
                        size: 14,
                        weight: '600'
                    },
                    bodyFont: {
                        size: 13
                    },
                    callbacks: {
                        title: (context) => context[0].label,
                        label: (context) => {
                            const value = context.parsed.y;
                            const label = value === 1 ? 'scrobble' : 'scrobbles';
                            return `${value.toLocaleString()} ${label}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: '#333',
                        borderColor: '#555'
                    },
                    ticks: {
                        color: '#999',
                        font: {
                            size: 11
                        },
                        maxRotation: 45,
                        minRotation: 0
                    },
                    title: {
                        display: true,
                        text: 'Time Period',
                        color: '#bb86fc',
                        font: {
                            size: 13,
                            weight: '600'
                        }
                    }
                },
                y: {
                    beginAtZero: true,
                    grid: {
                        color: '#333',
                        borderColor: '#555'
                    },
                    ticks: {
                        color: '#999',
                        font: {
                            size: 11
                        },
                        callback: (value) => value.toLocaleString()
                    },
                    title: {
                        display: true,
                        text: 'Scrobbles',
                        color: '#bb86fc',
                        font: {
                            size: 13,
                            weight: '600'
                        }
                    }
                }
            },
            interaction: {
                intersect: false,
                mode: 'index'
            },
            elements: {
                bar: {
                    borderRadius: 2
                }
            }
        };

        this.init();
    }

    /**
     * Initialize chart system
     */
    init() {
        this.setupEventListeners();

        // Initialize chart if we're on the charts page and Chart.js is available
        if (document.getElementById('scrobbleChart')) {
            this.waitForChartJs(() => {
                this.createChart();
            });
        }
    }

    /**
     * Wait for Chart.js to be available before initializing charts
     */
    waitForChartJs(callback, attempts = 0, maxAttempts = 50) {
        if (typeof Chart !== 'undefined') {
            callback();
        } else if (attempts < maxAttempts) {
            // Chart.js not yet loaded, wait 100ms and try again
            setTimeout(() => {
                this.waitForChartJs(callback, attempts + 1, maxAttempts);
            }, 100);
        } else {
            console.error('Chart.js failed to load after', maxAttempts, 'attempts');
            this.showNotification('Chart.js library failed to load. Charts cannot be displayed.', 'error');
        }
    }

    /**
     * Setup event listeners for chart interactions
     */
    setupEventListeners() {
        // Re-initialize chart after htmx updates
        document.addEventListener('htmx:afterSwap', (evt) => {
            if (evt.detail.target.id === 'chart-container') {
                setTimeout(() => {
                    this.waitForChartJs(() => {
                        this.createChart();
                    });
                }, 100);
            }
        });

        // Download button functionality
        document.addEventListener('click', (e) => {
            if (e.target.id === 'download-chart' || e.target.closest('#download-chart')) {
                e.preventDefault();
                this.downloadChart();
            }
        });

        // Handle chart resize for responsive design
        window.addEventListener('resize', this.debounce(() => {
            if (this.chart) {
                this.chart.resize();
            }
        }, 250));
    }

    /**
     * Get chart data from the page
     */
    getChartData() {
        // Try global chart data first (main page)
        let dataElement = document.getElementById('chart-data-global');

        // Fallback to partial chart data (htmx updates)
        if (!dataElement) {
            dataElement = document.getElementById('chart-data');
        }

        if (!dataElement) {
            console.warn('Chart data element not found');
            return null;
        }

        try {
            return JSON.parse(dataElement.textContent);
        } catch (error) {
            console.error('Failed to parse chart data:', error);
            return null;
        }
    }

    /**
     * Create or update the chart
     */
    createChart() {
        const ctx = document.getElementById('scrobbleChart');
        if (!ctx) {
            console.warn('Chart canvas not found');
            return;
        }

        const chartData = this.getChartData();
        if (!chartData || !chartData.success || !chartData.values || chartData.values.length === 0) {
            console.warn('Invalid chart data:', chartData);
            return;
        }

        // Destroy existing chart if it exists
        if (this.chart) {
            this.chart.destroy();
        }

        // Create gradient background
        const gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 400);
        gradient.addColorStop(0, 'rgba(187, 134, 252, 0.8)');
        gradient.addColorStop(1, 'rgba(187, 134, 252, 0.2)');

        // Chart configuration
        const config = {
            type: 'bar',
            data: {
                labels: chartData.labels,
                datasets: [{
                    label: 'Scrobbles',
                    data: chartData.values,
                    backgroundColor: gradient,
                    borderColor: 'rgba(187, 134, 252, 1)',
                    borderWidth: 1,
                    hoverBackgroundColor: 'rgba(187, 134, 252, 0.9)',
                    hoverBorderColor: 'rgba(187, 134, 252, 1)',
                    hoverBorderWidth: 2
                }]
            },
            options: this.config
        };

        // Create the chart
        try {
            this.chart = new Chart(ctx, config);
            console.log('Chart created successfully with', chartData.values.length, 'data points');
        } catch (error) {
            console.error('Failed to create chart:', error);
        }
    }

    /**
     * Download chart as PNG
     */
    downloadChart() {
        if (!this.chart) {
            console.warn('No chart available for download');
            return;
        }

        try {
            const link = document.createElement('a');
            link.download = `scrobblarr-chart-${Date.now()}.png`;
            link.href = this.chart.toBase64Image('image/png', 1.0);
            link.click();

            console.log('Chart downloaded successfully');
        } catch (error) {
            console.error('Failed to download chart:', error);

            // Show user-friendly error message
            this.showNotification('Failed to download chart. Please try again.', 'error');
        }
    }

    /**
     * Show a notification to the user
     */
    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;

        // Style the notification
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 8px;
            color: white;
            font-weight: 500;
            z-index: 1000;
            opacity: 0;
            transition: opacity 0.3s ease;
            ${type === 'error' ? 'background-color: #f44336;' : 'background-color: #4caf50;'}
        `;

        // Add to page
        document.body.appendChild(notification);

        // Animate in
        setTimeout(() => notification.style.opacity = '1', 100);

        // Remove after delay
        setTimeout(() => {
            notification.style.opacity = '0';
            setTimeout(() => document.body.removeChild(notification), 300);
        }, 3000);
    }

    /**
     * Utility function for debouncing
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    /**
     * Get chart statistics
     */
    getChartStats() {
        if (!this.chart || !this.chart.data.datasets[0]) {
            return null;
        }

        const data = this.chart.data.datasets[0].data;
        const total = data.reduce((sum, value) => sum + value, 0);
        const max = Math.max(...data);
        const min = Math.min(...data);
        const avg = total / data.length;

        return {
            total,
            max,
            min,
            avg,
            count: data.length
        };
    }

    /**
     * Update chart data dynamically
     */
    updateChart(newData) {
        if (!this.chart) {
            console.warn('No chart to update');
            return;
        }

        if (!newData || !newData.labels || !newData.values) {
            console.warn('Invalid data for chart update');
            return;
        }

        try {
            this.chart.data.labels = newData.labels;
            this.chart.data.datasets[0].data = newData.values;
            this.chart.update('active');

            console.log('Chart updated with', newData.values.length, 'data points');
        } catch (error) {
            console.error('Failed to update chart:', error);
        }
    }

    /**
     * Destroy the chart
     */
    destroy() {
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
    }
}

// Initialize charts when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.scrobblarrCharts = new ScrobblarrCharts();
});