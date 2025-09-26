/**
 * Scrobblarr Artist Detail JavaScript
 * Chart.js integration and interactive functionality for artist detail pages
 * Story 26: Artist Detail Page
 */

// Prevent multiple execution
if (!window.ScrobblarrArtistDetail) {

class ScrobblarrArtistDetail {
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
     * Initialize artist detail system
     */
    init() {
        this.setupEventListeners();

        // Initialize chart if we're on the charts tab
        if (document.getElementById('artistChart')) {
            // Use the same robust creation method for initial load
            setTimeout(() => {
                this.attemptChartCreation();
            }, 100); // Small delay to ensure DOM is fully ready
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
     * Setup event listeners for artist detail interactions
     */
    setupEventListeners() {
        // Enhanced chart cleanup before HTMX content swap
        document.addEventListener('htmx:beforeSwap', (evt) => {
            if (evt.detail.target.id === 'artist-dynamic-content') {
                console.log('HTMX beforeSwap - preparing for content update');

                // Aggressive chart cleanup
                if (this.chart) {
                    console.log('Destroying existing chart instance');
                    try {
                        this.chart.destroy();
                    } catch (error) {
                        console.warn('Error destroying chart:', error);
                    }
                    this.chart = null;
                }

                // Clear any Chart.js global references for this canvas
                const canvas = document.getElementById('artistChart');
                if (canvas) {
                    // Force clear any Chart.js context bindings
                    if (typeof Chart !== 'undefined' && Chart.getChart) {
                        const existingChart = Chart.getChart(canvas);
                        if (existingChart) {
                            console.log('Clearing Chart.js global reference');
                            existingChart.destroy();
                        }
                    }
                }

                console.log('Chart cleanup completed');
            }
        });

        // Enhanced chart recreation after HTMX content swap
        document.addEventListener('htmx:afterSwap', (evt) => {
            if (evt.detail.target.id === 'artist-dynamic-content') {
                console.log('HTMX afterSwap - content updated');

                // Use longer timeout for more reliable chart creation
                setTimeout(() => {
                    this.attemptChartCreation();
                }, 300);
            }
        });

        // Tab switching functionality
        document.addEventListener('click', (e) => {
            const tabLink = e.target.closest('.tab-link');
            if (tabLink && !tabLink.classList.contains('active')) {
                // Update active tab visually (htmx will handle the content)
                document.querySelectorAll('.tab-link').forEach(tab => {
                    tab.classList.remove('active');
                });
                tabLink.classList.add('active');
            }
        });

        // Time period switching functionality
        document.addEventListener('click', (e) => {
            const periodLink = e.target.closest('.time-period-option');
            if (periodLink && !periodLink.classList.contains('active')) {
                // Update active period visually (htmx will handle the content)
                document.querySelectorAll('.time-period-option').forEach(period => {
                    period.classList.remove('active');
                });
                periodLink.classList.add('active');
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
        // Try artist-specific chart data first
        let dataElement = document.getElementById('artist-chart-data');

        // Fallback to global chart data
        if (!dataElement) {
            dataElement = document.getElementById('chart-data-global');
        }

        if (!dataElement) {
            console.warn('Artist chart data element not found');
            return null;
        }

        try {
            return JSON.parse(dataElement.textContent);
        } catch (error) {
            console.error('Failed to parse artist chart data:', error);
            return null;
        }
    }

    /**
     * Create or update the artist chart
     */
    createChart() {
        const ctx = document.getElementById('artistChart');
        if (!ctx) {
            console.warn('Artist chart canvas not found');
            return;
        }

        // Ensure canvas is properly initialized
        const canvas = ctx.getContext('2d');
        if (!canvas) {
            console.error('Failed to get 2D context for chart canvas');
            return;
        }

        const chartData = this.getChartData();
        if (!chartData) {
            console.warn('No chart data found');
            return;
        }

        if (!chartData.success) {
            console.log('Chart data not successful, showing empty state:', chartData.error || 'No data available');
            return;
        }

        if (!chartData.values || chartData.values.length === 0) {
            console.log('Chart has no data points, showing empty state');
            return;
        }

        // Destroy existing chart if it exists
        if (this.chart) {
            console.log('Destroying existing chart before creating new one');
            this.chart.destroy();
            this.chart = null;
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
                    label: 'Artist Scrobbles',
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
            console.log('Artist chart created successfully with', chartData.values.length, 'data points');
        } catch (error) {
            console.error('Failed to create artist chart:', error);
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
            console.warn('No artist chart to update');
            return;
        }

        if (!newData || !newData.labels || !newData.values) {
            console.warn('Invalid data for artist chart update');
            return;
        }

        try {
            this.chart.data.labels = newData.labels;
            this.chart.data.datasets[0].data = newData.values;
            this.chart.update('active');

            console.log('Artist chart updated with', newData.values.length, 'data points');
        } catch (error) {
            console.error('Failed to update artist chart:', error);
        }
    }

    /**
     * Attempt chart creation with retry logic and validation
     */
    attemptChartCreation(retryCount = 0, maxRetries = 2) {
        console.log(`Chart creation attempt ${retryCount + 1}/${maxRetries + 1}`);

        // Check if we're on the charts tab
        const chartCanvas = document.getElementById('artistChart');
        if (!chartCanvas) {
            console.log('No chart canvas found - not on charts tab');
            return;
        }

        // Validate canvas is ready for Chart.js
        try {
            const context = chartCanvas.getContext('2d');
            if (!context) {
                console.error('Canvas 2D context not available');
                if (retryCount < maxRetries) {
                    console.log(`Retrying chart creation in 200ms (attempt ${retryCount + 1})`);
                    setTimeout(() => {
                        this.attemptChartCreation(retryCount + 1, maxRetries);
                    }, 200);
                }
                return;
            }
        } catch (error) {
            console.error('Error getting canvas context:', error);
            return;
        }

        // Ensure Chart.js is available
        this.waitForChartJs(() => {
            console.log('Chart.js available, creating chart');
            try {
                this.createChart();
                if (this.chart) {
                    console.log('Chart created successfully');
                } else {
                    console.warn('Chart creation returned but no chart instance created');
                    // Retry if creation failed but we haven't exhausted retries
                    if (retryCount < maxRetries) {
                        console.log(`Retrying chart creation in 300ms (attempt ${retryCount + 1})`);
                        setTimeout(() => {
                            this.attemptChartCreation(retryCount + 1, maxRetries);
                        }, 300);
                    }
                }
            } catch (error) {
                console.error('Error during chart creation:', error);
                if (retryCount < maxRetries) {
                    console.log(`Retrying after error in 300ms (attempt ${retryCount + 1})`);
                    setTimeout(() => {
                        this.attemptChartCreation(retryCount + 1, maxRetries);
                    }, 300);
                }
            }
        });
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

// Initialize artist detail when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.scrobblarrArtistDetail = new ScrobblarrArtistDetail();
});

} // End execution guard