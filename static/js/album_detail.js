/**
 * Album Detail Page JavaScript
 * Provides interactive functionality for the album detail page including chart rendering and HTMX integration
 */

// Global chart instance to manage chart lifecycle
let albumChartInstance = null;

/**
 * Initialize chart data from the global script tag
 */
function initializeChartData() {
    const chartDataScript = document.getElementById('chart-data-global');
    if (chartDataScript) {
        try {
            window.chartDataGlobal = JSON.parse(chartDataScript.textContent);
        } catch (e) {
            console.error('Error parsing album chart data:', e);
            window.chartDataGlobal = { success: false, error: 'Failed to parse chart data' };
        }
    }
}

/**
 * Create and render the album chart
 */
function createAlbumChart() {
    const canvas = document.getElementById('albumChart');
    if (!canvas || !window.chartDataGlobal || !window.chartDataGlobal.success) {
        return;
    }

    // Destroy existing chart if it exists
    if (albumChartInstance) {
        albumChartInstance.destroy();
        albumChartInstance = null;
    }

    const ctx = canvas.getContext('2d');
    const chartData = window.chartDataGlobal;

    albumChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: chartData.labels,
            datasets: [{
                label: 'Scrobbles',
                data: chartData.values,
                backgroundColor: 'rgba(187, 134, 252, 0.6)',
                borderColor: 'rgba(187, 134, 252, 1)',
                borderWidth: 1,
                borderRadius: 4,
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
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: 'rgba(30, 30, 30, 0.95)',
                    titleColor: '#e0e0e0',
                    bodyColor: '#e0e0e0',
                    borderColor: '#333',
                    borderWidth: 1,
                    cornerRadius: 8,
                    callbacks: {
                        title: function(context) {
                            return context[0].label;
                        },
                        label: function(context) {
                            const value = context.parsed.y;
                            return `${value} scrobble${value !== 1 ? 's' : ''}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)',
                        borderColor: '#333'
                    },
                    ticks: {
                        color: '#999',
                        maxTicksLimit: 12
                    }
                },
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)',
                        borderColor: '#333'
                    },
                    ticks: {
                        color: '#999',
                        stepSize: 1
                    }
                }
            }
        }
    });
}

/**
 * Handle HTMX events for dynamic content updates
 */
function setupHTMXEventHandlers() {
    // Handle after content settlement to reinitialize charts
    document.addEventListener('htmx:afterSettle', function(event) {
        // Reinitialize chart data after HTMX updates
        initializeChartData();

        // If the album chart canvas was updated, recreate the chart
        if (event.detail.target.querySelector('#albumChart')) {
            setTimeout(createAlbumChart, 100);
        }
    });

    // Add loading states for better UX
    document.addEventListener('htmx:beforeRequest', function(event) {
        const target = event.detail.target;
        if (target.id === 'album-dynamic-content' || target.id === 'album-content') {
            target.style.opacity = '0.6';
            target.style.pointerEvents = 'none';
        }
    });

    document.addEventListener('htmx:afterRequest', function(event) {
        const target = event.detail.target;
        if (target.id === 'album-dynamic-content' || target.id === 'album-content') {
            target.style.opacity = '1';
            target.style.pointerEvents = 'auto';
        }
    });
}

/**
 * Initialize the album detail page
 */
function initializeAlbumDetail() {
    // Initialize chart data
    initializeChartData();

    // Create chart if chart tab is active
    if (document.querySelector('.tab-link[data-tab="charts"].active') ||
        document.querySelector('.tab-link.active[href*="tab=charts"]')) {
        createAlbumChart();
    }

    // Setup HTMX event handlers
    setupHTMXEventHandlers();

    // Add smooth transitions for tab switches
    const tabLinks = document.querySelectorAll('.tab-link');
    tabLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            // Add transition class for smooth content switching
            const content = document.getElementById('album-content');
            if (content) {
                content.style.transition = 'opacity 0.2s ease';
            }
        });
    });
}

/**
 * Cleanup function for page unload
 */
function cleanupAlbumDetail() {
    if (albumChartInstance) {
        albumChartInstance.destroy();
        albumChartInstance = null;
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeAlbumDetail);
} else {
    initializeAlbumDetail();
}

// Cleanup on page unload
window.addEventListener('beforeunload', cleanupAlbumDetail);

// Export for potential external use
window.albumDetail = {
    initialize: initializeAlbumDetail,
    createChart: createAlbumChart,
    cleanup: cleanupAlbumDetail
};