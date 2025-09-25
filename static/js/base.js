/**
 * Base JavaScript functionality for Scrobblarr
 * Handles mobile navigation, utility functions, and core UI interactions
 */

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', function() {
    initializeMobileNavigation();
    initializeMessageHandling();
    initializeAccessibilityFeatures();
});

/**
 * Mobile Navigation Toggle
 */
function initializeMobileNavigation() {
    const mobileToggle = document.querySelector('.mobile-menu-toggle');
    const nav = document.querySelector('.nav');

    if (mobileToggle && nav) {
        mobileToggle.addEventListener('click', function(e) {
            e.preventDefault();
            toggleMobileNav();
        });

        // Close mobile nav when clicking outside
        document.addEventListener('click', function(e) {
            if (!nav.contains(e.target) && !mobileToggle.contains(e.target)) {
                closeMobileNav();
            }
        });

        // Close mobile nav on escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && nav.classList.contains('mobile-nav-open')) {
                closeMobileNav();
                mobileToggle.focus();
            }
        });

        // Handle window resize
        window.addEventListener('resize', function() {
            if (window.innerWidth > 768) {
                closeMobileNav();
            }
        });
    }
}

function toggleMobileNav() {
    const mobileToggle = document.querySelector('.mobile-menu-toggle');
    const nav = document.querySelector('.nav');

    if (nav.classList.contains('mobile-nav-open')) {
        closeMobileNav();
    } else {
        openMobileNav();
    }
}

function openMobileNav() {
    const mobileToggle = document.querySelector('.mobile-menu-toggle');
    const nav = document.querySelector('.nav');

    nav.classList.add('mobile-nav-open');
    mobileToggle.setAttribute('aria-expanded', 'true');

    // Focus first nav link
    const firstNavLink = nav.querySelector('.nav-link');
    if (firstNavLink) {
        firstNavLink.focus();
    }
}

function closeMobileNav() {
    const mobileToggle = document.querySelector('.mobile-menu-toggle');
    const nav = document.querySelector('.nav');

    nav.classList.remove('mobile-nav-open');
    mobileToggle.setAttribute('aria-expanded', 'false');
}

/**
 * Message Handling (Success, Error, Info)
 */
function initializeMessageHandling() {
    // Auto-hide messages after delay
    const messages = document.querySelectorAll('.error-messages, .success-messages');
    messages.forEach(messageContainer => {
        if (!messageContainer.classList.contains('hidden')) {
            setTimeout(() => {
                hideMessage(messageContainer);
            }, 5000); // Hide after 5 seconds
        }
    });

    // Add close buttons to messages
    messages.forEach(messageContainer => {
        addCloseButtonToMessages(messageContainer);
    });
}

function addCloseButtonToMessages(container) {
    const messages = container.querySelectorAll('.message');
    messages.forEach(message => {
        if (!message.querySelector('.message-close')) {
            const closeBtn = document.createElement('button');
            closeBtn.className = 'message-close';
            closeBtn.innerHTML = '&times;';
            closeBtn.setAttribute('aria-label', 'Close message');
            closeBtn.addEventListener('click', () => {
                message.remove();
                if (container.children.length === 0) {
                    hideMessage(container);
                }
            });
            message.appendChild(closeBtn);
        }
    });
}

function showMessage(type, text, duration = 5000) {
    const containerId = type === 'error' ? 'error-messages' : 'success-messages';
    let container = document.getElementById(containerId);

    if (!container) {
        return;
    }

    // Create message element
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message';

    const icon = type === 'error' ?
        '<svg class="message-icon" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path></svg>' :
        '<svg class="message-icon" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path></svg>';

    messageDiv.innerHTML = `
        ${icon}
        <span class="message-text">${text}</span>
        <button class="message-close" aria-label="Close message">&times;</button>
    `;

    // Add close functionality
    const closeBtn = messageDiv.querySelector('.message-close');
    closeBtn.addEventListener('click', () => {
        messageDiv.remove();
        if (container.children.length === 0) {
            hideMessage(container);
        }
    });

    // Add to container and show
    container.appendChild(messageDiv);
    showElement(container);

    // Auto-hide after duration
    if (duration > 0) {
        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.remove();
                if (container.children.length === 0) {
                    hideMessage(container);
                }
            }
        }, duration);
    }
}

function showError(message, duration = 5000) {
    showMessage('error', message, duration);
}

function showSuccess(message, duration = 5000) {
    showMessage('success', message, duration);
}

function hideMessage(container) {
    container.classList.add('hidden');
    container.innerHTML = '';
}

function showElement(element) {
    element.classList.remove('hidden');
}

/**
 * Loading Spinner Management
 */
function showLoading() {
    const spinner = document.getElementById('loading-spinner');
    if (spinner) {
        spinner.classList.remove('hidden');
        spinner.setAttribute('aria-hidden', 'false');
    }
}

function hideLoading() {
    const spinner = document.getElementById('loading-spinner');
    if (spinner) {
        spinner.classList.add('hidden');
        spinner.setAttribute('aria-hidden', 'true');
    }
}

/**
 * Accessibility Features
 */
function initializeAccessibilityFeatures() {
    // Keyboard navigation for custom elements
    document.addEventListener('keydown', function(e) {
        // Handle Enter key on buttons and links
        if (e.key === 'Enter' || e.key === ' ') {
            const target = e.target;
            if (target.classList.contains('btn') ||
                target.classList.contains('nav-link') ||
                target.classList.contains('time-period-option')) {
                e.preventDefault();
                target.click();
            }
        }
    });

    // Announce page changes to screen readers
    const pageTitle = document.title;
    announceToScreenReader(`Navigated to ${pageTitle}`);
}

function announceToScreenReader(message) {
    const announcement = document.createElement('div');
    announcement.setAttribute('aria-live', 'polite');
    announcement.setAttribute('aria-atomic', 'true');
    announcement.className = 'sr-only';
    announcement.textContent = message;

    document.body.appendChild(announcement);

    setTimeout(() => {
        document.body.removeChild(announcement);
    }, 1000);
}

/**
 * Number Formatting Utilities
 */
function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toLocaleString();
}

function formatDuration(seconds) {
    if (!seconds) return '--:--';

    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;

    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
}

/**
 * Time Formatting Utilities
 */
function formatRelativeTime(timestamp) {
    const now = new Date();
    const date = new Date(timestamp);
    const diffInSeconds = Math.floor((now - date) / 1000);

    const intervals = [
        { label: 'year', seconds: 31536000 },
        { label: 'month', seconds: 2592000 },
        { label: 'week', seconds: 604800 },
        { label: 'day', seconds: 86400 },
        { label: 'hour', seconds: 3600 },
        { label: 'minute', seconds: 60 }
    ];

    for (const interval of intervals) {
        const count = Math.floor(diffInSeconds / interval.seconds);
        if (count >= 1) {
            return count === 1 ?
                `1 ${interval.label} ago` :
                `${count} ${interval.label}s ago`;
        }
    }

    return 'just now';
}

/**
 * URL Utilities
 */
function updateURLWithoutReload(url) {
    if (history.pushState) {
        history.pushState(null, null, url);
    }
}

function getQueryParam(param) {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(param);
}

function setQueryParam(param, value) {
    const url = new URL(window.location);
    url.searchParams.set(param, value);
    updateURLWithoutReload(url.toString());
}

/**
 * Local Storage Utilities
 */
function setLocalStorage(key, value) {
    try {
        localStorage.setItem(`scrobblarr_${key}`, JSON.stringify(value));
        return true;
    } catch (e) {
        console.warn('Failed to save to localStorage:', e);
        return false;
    }
}

function getLocalStorage(key, defaultValue = null) {
    try {
        const item = localStorage.getItem(`scrobblarr_${key}`);
        return item ? JSON.parse(item) : defaultValue;
    } catch (e) {
        console.warn('Failed to read from localStorage:', e);
        return defaultValue;
    }
}

function removeLocalStorage(key) {
    try {
        localStorage.removeItem(`scrobblarr_${key}`);
        return true;
    } catch (e) {
        console.warn('Failed to remove from localStorage:', e);
        return false;
    }
}

/**
 * Debounce Utility
 */
function debounce(func, delay) {
    let timeoutId;
    return function (...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func.apply(this, args), delay);
    };
}

/**
 * Progress Bar Animation
 */
function animateProgressBar(element, targetPercentage, duration = 1000) {
    if (!element) return;

    const startTime = performance.now();
    const startPercentage = 0;

    function updateProgress(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);

        // Easing function (ease-out)
        const easedProgress = 1 - Math.pow(1 - progress, 3);
        const currentPercentage = startPercentage + (targetPercentage - startPercentage) * easedProgress;

        element.style.width = `${currentPercentage}%`;

        if (progress < 1) {
            requestAnimationFrame(updateProgress);
        }
    }

    requestAnimationFrame(updateProgress);
}

/**
 * Theme Detection
 */
function getPreferredColorScheme() {
    if (window.matchMedia) {
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    return 'dark'; // Default to dark theme
}

/**
 * Export utilities for use in other scripts
 */
window.ScrobblarrUtils = {
    showError,
    showSuccess,
    hideMessage,
    showLoading,
    hideLoading,
    formatNumber,
    formatDuration,
    formatRelativeTime,
    updateURLWithoutReload,
    getQueryParam,
    setQueryParam,
    setLocalStorage,
    getLocalStorage,
    removeLocalStorage,
    debounce,
    animateProgressBar,
    announceToScreenReader,
    getPreferredColorScheme
};

// Global error handler - now defined after ScrobblarrUtils
window.addEventListener('error', function(e) {
    console.error('JavaScript error:', e.error);
    // Check if showError is available before calling it
    if (typeof showError === 'function') {
        showError('An unexpected error occurred. Please try again.');
    } else if (window.ScrobblarrUtils && typeof window.ScrobblarrUtils.showError === 'function') {
        window.ScrobblarrUtils.showError('An unexpected error occurred. Please try again.');
    } else {
        // Fallback to console if showError is not available
        console.warn('Error display function not available, logging error only');
    }
});

// Global unhandled promise rejection handler - now defined after ScrobblarrUtils
window.addEventListener('unhandledrejection', function(e) {
    console.error('Unhandled promise rejection:', e.reason);
    // Check if showError is available before calling it
    if (typeof showError === 'function') {
        showError('An unexpected error occurred. Please try again.');
    } else if (window.ScrobblarrUtils && typeof window.ScrobblarrUtils.showError === 'function') {
        window.ScrobblarrUtils.showError('An unexpected error occurred. Please try again.');
    } else {
        // Fallback to console if showError is not available
        console.warn('Error display function not available, logging error only');
    }
});

/**
 * Recent Tracks Page Functionality
 */
function initializeRecentTracksPage() {
    const recentTracksForm = document.querySelector('.recent-tracks-filters');
    if (!recentTracksForm) return;

    // Debounced search functionality
    const searchInput = document.getElementById('search');
    if (searchInput) {
        const debouncedSearch = debounce(() => {
            htmx.trigger(recentTracksForm, 'submit');
        }, 300);

        searchInput.addEventListener('input', debouncedSearch);
    }

    // Date range validation
    const dateFromInput = document.getElementById('date_from');
    const dateToInput = document.getElementById('date_to');

    if (dateFromInput && dateToInput) {
        dateFromInput.addEventListener('change', function() {
            if (dateToInput.value && this.value > dateToInput.value) {
                showError('Start date cannot be after end date.');
                this.value = '';
            }
        });

        dateToInput.addEventListener('change', function() {
            if (dateFromInput.value && this.value < dateFromInput.value) {
                showError('End date cannot be before start date.');
                this.value = '';
            }
        });
    }

    // Save filter preferences to localStorage
    const filterInputs = recentTracksForm.querySelectorAll('input, select');
    filterInputs.forEach(input => {
        // Load saved preferences
        const savedValue = getLocalStorage(`recent_tracks_${input.name}`);
        if (savedValue && !input.value) {
            input.value = savedValue;
        }

        // Save preferences on change
        input.addEventListener('change', function() {
            if (this.value) {
                setLocalStorage(`recent_tracks_${this.name}`, this.value);
            } else {
                removeLocalStorage(`recent_tracks_${this.name}`);
            }
        });
    });

    // Clear filters functionality
    window.clearRecentTracksFilters = function() {
        // Clear form inputs
        searchInput.value = '';
        if (dateFromInput) dateFromInput.value = '';
        if (dateToInput) dateToInput.value = '';

        const perPageSelect = document.getElementById('per_page');
        if (perPageSelect) perPageSelect.value = '50';

        // Clear localStorage
        ['search', 'date_from', 'date_to', 'per_page'].forEach(key => {
            removeLocalStorage(`recent_tracks_${key}`);
        });

        // Trigger form submission
        htmx.trigger(recentTracksForm, 'submit');
    };

    // Export functionality
    window.exportRecentTracks = function() {
        const formData = new FormData(recentTracksForm);
        formData.set('export', 'csv');

        const params = new URLSearchParams(formData);
        const url = window.location.pathname + '?' + params.toString();

        // Create temporary link and click it
        const link = document.createElement('a');
        link.href = url;
        link.download = '';
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        showSuccess('Export started. Your download should begin shortly.');
    };
}

/**
 * Advanced Pagination Functionality
 */
function initializePagination() {
    // Handle keyboard navigation for pagination
    document.addEventListener('keydown', function(e) {
        if (e.target.classList.contains('pagination-btn')) {
            if (e.key === 'ArrowLeft') {
                const prevBtn = document.querySelector('.pagination-btn-prev');
                if (prevBtn && !prevBtn.disabled) {
                    prevBtn.focus();
                }
            } else if (e.key === 'ArrowRight') {
                const nextBtn = document.querySelector('.pagination-btn-next');
                if (nextBtn && !nextBtn.disabled) {
                    nextBtn.focus();
                }
            }
        }
    });

    // Track current page for analytics
    const currentPage = getQueryParam('page') || '1';
    setLocalStorage('recent_tracks_last_page', currentPage);
}

/**
 * Enhanced Search Functionality
 */
function initializeAdvancedSearch() {
    const searchInput = document.getElementById('search');
    if (!searchInput) return;

    // Search suggestions (future enhancement)
    let searchHistory = getLocalStorage('search_history', []);

    searchInput.addEventListener('focus', function() {
        // Could show recent searches dropdown here
        console.log('Search history:', searchHistory);
    });

    // Track search queries
    searchInput.addEventListener('input', function() {
        if (this.value.length >= 3 && !searchHistory.includes(this.value)) {
            searchHistory.unshift(this.value);
            searchHistory = searchHistory.slice(0, 10); // Keep last 10 searches
            setLocalStorage('search_history', searchHistory);
        }
    });

    // Search shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + F to focus search
        if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
            const currentPage = window.location.pathname;
            if (currentPage === '/recent/') {
                e.preventDefault();
                searchInput.focus();
                searchInput.select();
            }
        }

        // Escape to clear search
        if (e.key === 'Escape' && document.activeElement === searchInput) {
            searchInput.value = '';
            searchInput.blur();
            // Trigger search update
            const form = searchInput.closest('form');
            if (form) {
                htmx.trigger(form, 'submit');
            }
        }
    });
}

/**
 * Table Enhancement Functions
 */
function initializeTableEnhancements() {
    // Add hover effects and click handlers for future detail pages
    const trackRows = document.querySelectorAll('.recent-tracks-table tbody tr');

    trackRows.forEach(row => {
        // Add keyboard navigation
        row.setAttribute('tabindex', '0');
        row.setAttribute('role', 'button');

        row.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                // Future: Navigate to track details
                console.log('Track selected:', this);
            }
        });

        // Double-click for future detail view
        row.addEventListener('dblclick', function() {
            // Future: Navigate to track details
            console.log('Track double-clicked:', this);
        });
    });
}

/**
 * Performance Monitoring
 */
function initializePerformanceMonitoring() {
    // Track page load time
    window.addEventListener('load', function() {
        const perfData = performance.getEntriesByType('navigation')[0];
        if (perfData) {
            console.log('Page load time:', perfData.loadEventEnd - perfData.loadEventStart, 'ms');
        }
    });

    // Track htmx request performance
    document.addEventListener('htmx:afterRequest', function(e) {
        const requestTime = e.detail.requestConfig.timeout;
        console.log('htmx request completed in:', Date.now() - e.detail.requestConfig.startTime, 'ms');
    });
}

// Initialize recent tracks functionality when on the recent tracks page
document.addEventListener('DOMContentLoaded', function() {
    if (window.location.pathname === '/recent/') {
        initializeRecentTracksPage();
        initializePagination();
        initializeAdvancedSearch();
        initializeTableEnhancements();
        initializePerformanceMonitoring();
    }
});

// Reinitialize after htmx updates
document.addEventListener('htmx:afterSwap', function(e) {
    if (e.target.id === 'recent-tracks-content') {
        initializeTableEnhancements();

        // Announce results to screen readers
        const resultsInfo = document.querySelector('.results-text');
        if (resultsInfo) {
            announceToScreenReader(resultsInfo.textContent);
        }
    }
});

// Prevent accidental form submissions
document.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && e.target.tagName === 'INPUT' && e.target.type !== 'submit') {
        const form = e.target.closest('form');
        if (form) {
            const submitButton = form.querySelector('button[type="submit"], input[type="submit"]');
            if (submitButton) {
                e.preventDefault();
                submitButton.click();
            }
        }
    }
});