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

// Global error handler
window.addEventListener('error', function(e) {
    console.error('JavaScript error:', e.error);
    showError('An unexpected error occurred. Please try again.');
});

// Global unhandled promise rejection handler
window.addEventListener('unhandledrejection', function(e) {
    console.error('Unhandled promise rejection:', e.reason);
    showError('An unexpected error occurred. Please try again.');
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