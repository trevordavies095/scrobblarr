/**
 * htmx Helper Functions and Configuration for Scrobblarr
 * Enhances htmx functionality with custom behaviors and utilities
 */

// Prevent multiple execution with robust global flag
if (typeof window.htmxHelpersInitialized === 'undefined') {
    window.htmxHelpersInitialized = true;

document.addEventListener('DOMContentLoaded', function() {
    initializeHtmxHelpers();
});

/**
 * Initialize htmx helpers and event listeners
 */
function initializeHtmxHelpers() {
    // Configure htmx defaults
    configureHtmxDefaults();

    // Add global htmx event listeners
    addGlobalHtmxEventListeners();

    // Initialize time period selectors
    initializeTimePeriodSelectors();

    // Initialize search functionality
    initializeSearchFunctionality();
}

/**
 * Configure htmx default settings
 */
function configureHtmxDefaults() {
    if (typeof htmx !== 'undefined') {
        // Set default timeout
        htmx.config.timeout = 10000; // 10 seconds

        // Set default error message
        htmx.config.defaultSwapStyle = 'innerHTML';

        // Configure history
        htmx.config.historyEnabled = true;
        htmx.config.refreshOnHistoryMiss = false;
    }
}

/**
 * Add global htmx event listeners
 */
function addGlobalHtmxEventListeners() {
    // Before request - show loading state
    document.addEventListener('htmx:beforeRequest', function(evt) {
        const target = evt.target;

        // Add loading class to target element
        target.classList.add('htmx-request');

        // Show global loading spinner for expensive operations
        if (target.hasAttribute('data-loading-global')) {
            window.ScrobblarrUtils.showLoading();
        }

        // Show local loading indicator
        showLocalLoadingIndicator(target);
    });

    // After request - hide loading state
    document.addEventListener('htmx:afterRequest', function(evt) {
        const target = evt.target;

        // Remove loading class
        target.classList.remove('htmx-request');

        // Hide global loading spinner
        window.ScrobblarrUtils.hideLoading();

        // Hide local loading indicator
        hideLocalLoadingIndicator(target);
    });

    // Request error handling
    document.addEventListener('htmx:responseError', function(evt) {
        const target = evt.target;
        const status = evt.detail.xhr.status;

        let message = 'Failed to load data. Please try again.';

        switch (status) {
            case 404:
                message = 'The requested data was not found.';
                break;
            case 403:
                message = 'You do not have permission to access this data.';
                break;
            case 500:
                message = 'Server error. Please try again later.';
                break;
            case 429:
                message = 'Too many requests. Please wait a moment before trying again.';
                break;
        }

        window.ScrobblarrUtils.showError(message);

        // Log error for debugging
        console.error('htmx request error:', {
            status: status,
            url: evt.detail.pathInfo.requestPath,
            target: target
        });
    });

    // Network error handling
    document.addEventListener('htmx:sendError', function(evt) {
        window.ScrobblarrUtils.showError('Network error. Please check your connection.');
    });

    // Timeout handling
    document.addEventListener('htmx:timeout', function(evt) {
        window.ScrobblarrUtils.showError('Request timed out. Please try again.');
    });

    // After swap - handle new content
    document.addEventListener('htmx:afterSwap', function(evt) {
        const target = evt.target;

        // Initialize new components in swapped content
        initializeNewContent(target);

        // Announce to screen readers
        announceContentUpdate(target);

        // Animate progress bars
        animateProgressBarsInElement(target);

        // Update page title if needed
        updatePageTitleFromTarget(target);
    });

    // History navigation
    document.addEventListener('htmx:historyRestore', function(evt) {
        window.ScrobblarrUtils.announceToScreenReader('Page restored from history');
    });
}

/**
 * Show local loading indicator for specific elements
 */
function showLocalLoadingIndicator(element) {
    // Check if element already has a loading indicator
    if (element.querySelector('.htmx-indicator')) {
        return;
    }

    // Create loading indicator
    const indicator = document.createElement('div');
    indicator.className = 'htmx-indicator';
    indicator.innerHTML = `
        <div class="inline-spinner">
            <div class="spinner spinner-sm"></div>
            <span class="loading-text">Loading...</span>
        </div>
    `;

    // Position indicator
    if (element.tagName === 'TABLE') {
        // For tables, show overlay
        indicator.className += ' htmx-table-indicator';
        element.style.position = 'relative';
    }

    element.appendChild(indicator);
}

/**
 * Hide local loading indicator
 */
function hideLocalLoadingIndicator(element) {
    const indicator = element.querySelector('.htmx-indicator');
    if (indicator) {
        indicator.remove();
    }
}

/**
 * Initialize new content after htmx swap
 */
function initializeNewContent(target) {
    // Initialize any tooltips
    initializeTooltips(target);

    // Initialize charts if Chart.js is loaded
    if (typeof Chart !== 'undefined') {
        initializeCharts(target);
    } else if (target.querySelector('[data-chart]')) {
        console.warn('Chart.js not loaded but chart elements found');
    }

    // Initialize time period selectors in new content
    initializeTimePeriodSelectors(target);

    // Initialize any forms
    initializeForms(target);
}

/**
 * Initialize time period selectors
 */
function initializeTimePeriodSelectors(container = document) {
    const selectors = container.querySelectorAll('.time-period-selector');

    selectors.forEach(selector => {
        const options = selector.querySelectorAll('.time-period-option');

        options.forEach(option => {
            option.addEventListener('click', function(e) {
                e.preventDefault();

                // Update active state
                options.forEach(opt => opt.classList.remove('active'));
                this.classList.add('active');

                // Get target element and period
                const targetSelector = selector.getAttribute('data-target');
                const period = this.getAttribute('data-period');
                const target = document.querySelector(targetSelector);

                if (target && target.hasAttribute('hx-get')) {
                    // Update htmx URL with new period
                    const baseUrl = target.getAttribute('hx-get').split('?')[0];
                    const newUrl = `${baseUrl}?period=${period}`;
                    target.setAttribute('hx-get', newUrl);

                    // Trigger htmx request
                    htmx.trigger(target, 'htmx:trigger');

                    // Update URL parameter
                    window.ScrobblarrUtils.setQueryParam('period', period);
                }
            });
        });
    });
}

/**
 * Initialize search functionality with debouncing
 */
function initializeSearchFunctionality() {
    const searchInputs = document.querySelectorAll('input[data-search-target]');

    searchInputs.forEach(input => {
        const targetSelector = input.getAttribute('data-search-target');
        const target = document.querySelector(targetSelector);

        if (target) {
            const debouncedSearch = window.ScrobblarrUtils.debounce(function(query) {
                performSearch(target, query);
            }, 500);

            input.addEventListener('input', function() {
                const query = this.value.trim();
                debouncedSearch(query);
            });

            // Handle enter key
            input.addEventListener('keydown', function(e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    const query = this.value.trim();
                    performSearch(target, query);
                }
            });
        }
    });
}

/**
 * Perform search with htmx
 */
function performSearch(target, query) {
    const baseUrl = target.getAttribute('hx-get').split('?')[0];
    const currentParams = new URLSearchParams(window.location.search);

    if (query) {
        currentParams.set('q', query);
    } else {
        currentParams.delete('q');
    }

    const newUrl = currentParams.toString() ?
        `${baseUrl}?${currentParams.toString()}` :
        baseUrl;

    target.setAttribute('hx-get', newUrl);
    htmx.trigger(target, 'htmx:trigger');

    // Update browser URL
    window.ScrobblarrUtils.updateURLWithoutReload(newUrl);
}

/**
 * Initialize tooltips (simple implementation)
 */
function initializeTooltips(container = document) {
    const tooltipElements = container.querySelectorAll('[data-tooltip]');

    tooltipElements.forEach(element => {
        element.addEventListener('mouseenter', showTooltip);
        element.addEventListener('mouseleave', hideTooltip);
        element.addEventListener('focus', showTooltip);
        element.addEventListener('blur', hideTooltip);
    });
}

function showTooltip(e) {
    const text = e.target.getAttribute('data-tooltip');
    if (!text) return;

    const tooltip = document.createElement('div');
    tooltip.className = 'tooltip';
    tooltip.textContent = text;
    tooltip.id = 'active-tooltip';

    document.body.appendChild(tooltip);

    // Position tooltip
    const rect = e.target.getBoundingClientRect();
    tooltip.style.left = rect.left + (rect.width / 2) - (tooltip.offsetWidth / 2) + 'px';
    tooltip.style.top = rect.top - tooltip.offsetHeight - 8 + 'px';
}

function hideTooltip() {
    const tooltip = document.getElementById('active-tooltip');
    if (tooltip) {
        tooltip.remove();
    }
}

/**
 * Initialize charts in new content
 */
function initializeCharts(container = document) {
    const chartElements = container.querySelectorAll('[data-chart]');

    chartElements.forEach(element => {
        const chartType = element.getAttribute('data-chart');
        const dataUrl = element.getAttribute('data-chart-url');

        if (dataUrl) {
            fetchChartData(dataUrl).then(data => {
                createChart(element, chartType, data);
            }).catch(error => {
                console.error('Failed to load chart data:', error);
                element.innerHTML = '<p class="error-text">Failed to load chart data</p>';
            });
        }
    });
}

/**
 * Fetch chart data
 */
async function fetchChartData(url) {
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    return await response.json();
}

/**
 * Create chart using Chart.js
 */
function createChart(element, type, data) {
    const canvas = document.createElement('canvas');
    element.appendChild(canvas);

    const ctx = canvas.getContext('2d');

    const config = {
        type: type,
        data: data,
        options: getChartOptions(type)
    };

    new Chart(ctx, config);
}

/**
 * Get Chart.js options based on chart type
 */
function getChartOptions(type) {
    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                labels: {
                    color: '#e0e0e0'
                }
            }
        },
        scales: {
            y: {
                ticks: {
                    color: '#999'
                },
                grid: {
                    color: '#333'
                }
            },
            x: {
                ticks: {
                    color: '#999'
                },
                grid: {
                    color: '#333'
                }
            }
        }
    };

    switch (type) {
        case 'bar':
            return {
                ...commonOptions,
                plugins: {
                    ...commonOptions.plugins,
                    tooltip: {
                        backgroundColor: '#1e1e1e',
                        titleColor: '#e0e0e0',
                        bodyColor: '#e0e0e0',
                        borderColor: '#bb86fc',
                        borderWidth: 1
                    }
                }
            };
        default:
            return commonOptions;
    }
}

/**
 * Initialize forms in new content
 */
function initializeForms(container = document) {
    const forms = container.querySelectorAll('form[hx-post], form[hx-put], form[hx-patch]');

    forms.forEach(form => {
        form.addEventListener('submit', function() {
            const submitButton = form.querySelector('button[type="submit"]');
            if (submitButton) {
                submitButton.disabled = true;
                submitButton.innerHTML = '<div class="spinner spinner-sm"></div> Processing...';

                // Re-enable after response
                setTimeout(() => {
                    submitButton.disabled = false;
                    submitButton.innerHTML = submitButton.getAttribute('data-original-text') || 'Submit';
                }, 2000);
            }
        });
    });
}

/**
 * Announce content updates to screen readers
 */
function announceContentUpdate(target) {
    const announcement = target.getAttribute('data-announce');
    if (announcement) {
        window.ScrobblarrUtils.announceToScreenReader(announcement);
    } else if (target.hasAttribute('data-auto-announce')) {
        window.ScrobblarrUtils.announceToScreenReader('Content updated');
    }
}

/**
 * Animate progress bars in new content
 */
function animateProgressBarsInElement(container) {
    const progressBars = container.querySelectorAll('.progress-fill[data-percentage]');

    progressBars.forEach(bar => {
        const percentage = parseFloat(bar.getAttribute('data-percentage'));
        if (!isNaN(percentage)) {
            // Delay animation slightly for better UX
            setTimeout(() => {
                window.ScrobblarrUtils.animateProgressBar(bar, percentage);
            }, 100);
        }
    });
}

/**
 * Update page title from target element
 */
function updatePageTitleFromTarget(target) {
    const newTitle = target.getAttribute('data-page-title');
    if (newTitle) {
        document.title = newTitle;
    }
}

/**
 * Utility function to trigger htmx requests programmatically
 */
function triggerHtmxRequest(element, event = 'htmx:trigger') {
    if (typeof htmx !== 'undefined') {
        htmx.trigger(element, event);
    }
}

/**
 * Utility function to refresh all htmx elements with specific attribute
 */
function refreshHtmxElements(attribute) {
    const elements = document.querySelectorAll(`[${attribute}]`);
    elements.forEach(element => {
        triggerHtmxRequest(element);
    });
}

/**
 * Export htmx utilities
 */
window.ScrobblarrHtmx = {
    triggerRequest: triggerHtmxRequest,
    refreshElements: refreshHtmxElements,
    showLocalLoadingIndicator,
    hideLocalLoadingIndicator
};

// Add CSS for htmx indicators (prevent multiple execution)
if (!document.getElementById('htmx-styles')) {
const htmxStyles = document.createElement('style');
htmxStyles.id = 'htmx-styles';
htmxStyles.textContent = `
    .htmx-indicator {
        display: none;
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: rgba(30, 30, 30, 0.9);
        padding: 1rem;
        border-radius: 8px;
        z-index: 1000;
    }

    .htmx-request .htmx-indicator {
        display: flex !important;
        align-items: center;
        gap: 0.5rem;
    }

    .htmx-table-indicator {
        top: 2rem;
        background: rgba(18, 18, 18, 0.95);
        border: 1px solid #333;
    }

    .inline-spinner {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        color: #bb86fc;
    }

    .spinner-sm {
        width: 20px;
        height: 20px;
        border-width: 2px;
    }

    .tooltip {
        position: absolute;
        background: #1e1e1e;
        color: #e0e0e0;
        padding: 0.5rem 0.75rem;
        border-radius: 6px;
        font-size: 0.875rem;
        border: 1px solid #333;
        z-index: 10000;
        max-width: 200px;
        word-wrap: break-word;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }

    .error-text {
        color: #ff6b6b;
        font-style: italic;
        text-align: center;
        padding: 2rem;
    }
`;

document.head.appendChild(htmxStyles);
}

} // End htmx helpers execution guard