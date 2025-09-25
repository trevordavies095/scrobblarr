"""
Django template filters for dashboard enhancements.
"""
from django import template
from django.utils.safestring import mark_safe
import locale

register = template.Library()


@register.filter
def format_number(value):
    """
    Format a number with thousand separators.

    Examples:
        1500 -> "1,500"
        1500000 -> "1,500,000"
        None -> "--"
    """
    if value is None or value == "":
        return "--"

    try:
        # Convert to integer if it's a float with no decimal part
        if isinstance(value, float) and value.is_integer():
            value = int(value)

        # Use locale-aware formatting if available, fallback to manual formatting
        try:
            return f"{value:,}"
        except (ValueError, TypeError):
            return str(value)
    except (ValueError, TypeError):
        return "--"


@register.filter
def format_percentage(value, total=None, decimal_places=1):
    """
    Format a percentage value.

    Examples:
        format_percentage(25, 100) -> "25.0%"
        format_percentage(0.75) -> "75.0%"
    """
    if value is None or value == "":
        return "--"

    try:
        if total is not None and total > 0:
            percentage = (float(value) / float(total)) * 100
        else:
            # Assume value is already a percentage (0-1) or (0-100)
            percentage = float(value)
            if percentage <= 1:
                percentage *= 100

        return f"{percentage:.{decimal_places}f}%"
    except (ValueError, TypeError, ZeroDivisionError):
        return "--"


@register.filter
def format_duration(seconds):
    """
    Format duration in seconds as MM:SS or HH:MM:SS.

    Examples:
        format_duration(90) -> "1:30"
        format_duration(3661) -> "1:01:01"
    """
    if seconds is None or seconds == "":
        return "--"

    try:
        seconds = int(seconds)
        if seconds < 3600:  # Less than 1 hour
            minutes, secs = divmod(seconds, 60)
            return f"{minutes}:{secs:02d}"
        else:  # 1 hour or more
            hours, remainder = divmod(seconds, 3600)
            minutes, secs = divmod(remainder, 60)
            return f"{hours}:{minutes:02d}:{secs:02d}"
    except (ValueError, TypeError):
        return "--"


@register.filter
def format_change_indicator(current, previous):
    """
    Create a change indicator showing direction and percentage change.

    Returns a dict with 'direction', 'percentage', and 'text' keys.
    """
    if current is None or previous is None or previous == 0:
        return None

    try:
        current = float(current)
        previous = float(previous)

        if current == previous:
            return {
                'direction': 'neutral',
                'percentage': 0.0,
                'text': 'No change'
            }

        change_percentage = ((current - previous) / previous) * 100
        direction = 'up' if change_percentage > 0 else 'down'

        return {
            'direction': direction,
            'percentage': abs(change_percentage),
            'text': f"{'↑' if direction == 'up' else '↓'} {abs(change_percentage):.1f}%"
        }
    except (ValueError, TypeError, ZeroDivisionError):
        return None


@register.filter
def humanize_count(value):
    """
    Convert large numbers to human-readable format.

    Examples:
        1500 -> "1.5K"
        1500000 -> "1.5M"
        150 -> "150"
    """
    if value is None or value == "":
        return "--"

    try:
        value = float(value)

        if value >= 1_000_000:
            return f"{value / 1_000_000:.1f}M"
        elif value >= 1_000:
            return f"{value / 1_000:.1f}K"
        else:
            return str(int(value))
    except (ValueError, TypeError):
        return "--"


@register.filter
def safe_divide(dividend, divisor, default="--"):
    """
    Safely divide two numbers, returning default for invalid operations.
    """
    try:
        if divisor is None or divisor == 0:
            return default
        return float(dividend) / float(divisor)
    except (ValueError, TypeError, ZeroDivisionError):
        return default


@register.inclusion_tag('components/stat_card.html')
def stat_card(title, value, subtitle=None, change=None, icon=None, link=None):
    """
    Render a statistic card component.

    Usage:
        {% stat_card "Total Scrobbles" stats.total_scrobbles subtitle="All time" %}
    """
    return {
        'title': title,
        'value': value,
        'subtitle': subtitle,
        'change': change,
        'icon': icon,
        'link': link
    }


@register.simple_tag
def progress_bar(current, maximum, label=None, show_percentage=True):
    """
    Generate a progress bar HTML.

    Usage:
        {% progress_bar current_value max_value "Progress Label" %}
    """
    if maximum == 0 or current is None or maximum is None:
        percentage = 0
    else:
        percentage = min((current / maximum) * 100, 100)

    progress_html = f'''
    <div class="progress-container">
        {f'<div class="progress-label">{label}</div>' if label else ''}
        <div class="progress-bar">
            <div class="progress-fill" style="width: {percentage:.1f}%"></div>
        </div>
        {f'<div class="progress-text">{percentage:.1f}%</div>' if show_percentage else ''}
    </div>
    '''

    return mark_safe(progress_html)