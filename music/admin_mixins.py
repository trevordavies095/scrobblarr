"""
Reusable admin mixins for common functionality across different models.
"""
from django.contrib import admin
from django.db.models import Count, Max
from django.urls import reverse
from django.utils.html import format_html
from django.utils import timezone

from .admin_actions import (
    export_to_csv, validate_selected_records, clear_invalid_mbids,
    bulk_update_urls, generate_data_quality_report
)


class EnhancedAdminMixin:
    """Base mixin with common enhancements for all admin interfaces."""

    save_on_top = True
    list_per_page = 50
    show_full_result_count = False  # Performance optimization for large datasets

    def get_readonly_fields(self, request, obj=None):
        """Always make timestamp fields readonly."""
        readonly = list(super().get_readonly_fields(request, obj) or [])
        if 'created_at' not in readonly:
            readonly.append('created_at')
        if 'updated_at' not in readonly:
            readonly.append('updated_at')
        return readonly

    def get_list_display(self, request):
        """Ensure consistent list display across all admin interfaces."""
        return super().get_list_display(request)


class CountDisplayMixin:
    """Mixin providing reusable count display methods."""

    def get_count_display_html(self, obj, count, related_model_name, filter_param, field_name='id'):
        """Generate HTML for clickable count displays."""
        if count > 0:
            url = reverse(f'admin:music_{related_model_name}_changelist')
            filter_url = f'{url}?{filter_param}={getattr(obj, field_name)}'
            return format_html('<a href="{}">{:,}</a>', filter_url, count)
        return '0'

    def get_play_count_display(self, obj, play_count):
        """Format play count with appropriate styling."""
        if play_count == 0:
            return format_html('<span style="color: #888;">0</span>')
        elif play_count < 10:
            return format_html('<span style="color: #28a745;">{:,}</span>', play_count)
        elif play_count < 50:
            return format_html('<span style="color: #ffc107; font-weight: bold;">{:,}</span>', play_count)
        else:
            return format_html('<span style="color: #dc3545; font-weight: bold;">{:,}</span>', play_count)


class BulkActionMixin:
    """Mixin providing common bulk actions."""

    def get_actions(self, request):
        """Add common bulk actions to all admin interfaces."""
        actions = super().get_actions(request)
        actions['export_to_csv'] = (export_to_csv, 'export_to_csv', export_to_csv.short_description)
        actions['validate_selected_records'] = (
            validate_selected_records,
            'validate_selected_records',
            validate_selected_records.short_description
        )
        actions['generate_data_quality_report'] = (
            generate_data_quality_report,
            'generate_data_quality_report',
            generate_data_quality_report.short_description
        )

        # Add MBID-related actions if the model has MBID field
        if hasattr(self.model, 'mbid'):
            actions['clear_invalid_mbids'] = (
                clear_invalid_mbids,
                'clear_invalid_mbids',
                clear_invalid_mbids.short_description
            )
            actions['bulk_update_urls'] = (
                bulk_update_urls,
                'bulk_update_urls',
                bulk_update_urls.short_description
            )

        return actions


class MBIDStatusMixin:
    """Mixin for displaying MBID status with visual indicators."""

    def mbid_status_display(self, obj):
        """Display MBID status with color coding."""
        if not hasattr(obj, 'mbid'):
            return '-'

        if obj.mbid:
            # Check if MBID is valid UUID format
            import re
            uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            if re.match(uuid_pattern, obj.mbid):
                return format_html(
                    '<span style="color: #28a745; font-weight: bold;" title="{}">✓ Valid</span>',
                    obj.mbid
                )
            else:
                return format_html(
                    '<span style="color: #dc3545; font-weight: bold;" title="Invalid MBID: {}">✗ Invalid</span>',
                    obj.mbid
                )
        else:
            return format_html('<span style="color: #6c757d;">Missing</span>')

    mbid_status_display.short_description = 'MBID Status'
    mbid_status_display.admin_order_field = 'mbid'


class RecentActivityMixin:
    """Mixin for displaying recent activity information."""

    def recent_activity_display(self, obj):
        """Display when the record was last active (different per model)."""
        # This will be overridden in specific admin classes
        if hasattr(obj, 'updated_at'):
            return obj.updated_at.strftime('%Y-%m-%d')
        return '-'

    recent_activity_display.short_description = 'Recent Activity'
    recent_activity_display.admin_order_field = 'updated_at'


class PerformanceOptimizedMixin:
    """Mixin for performance optimizations."""

    def get_queryset(self, request):
        """Optimize queryset with appropriate select_related and prefetch_related."""
        queryset = super().get_queryset(request)

        # Add basic optimizations that apply to most models
        if hasattr(self, 'list_select_related') and self.list_select_related:
            queryset = queryset.select_related(*self.list_select_related)

        return queryset

    def get_search_results(self, request, queryset, search_term):
        """Optimize search performance."""
        # Use the default search but with performance considerations
        queryset, may_have_duplicates = super().get_search_results(
            request, queryset, search_term
        )

        # Remove duplicates if necessary and if queryset is not too large
        if may_have_duplicates and queryset.count() < 10000:
            queryset = queryset.distinct()

        return queryset, may_have_duplicates


class FilterMixin:
    """Mixin for common filtering capabilities."""

    def get_list_filter(self, request):
        """Add common filters to all admin interfaces."""
        filters = list(super().get_list_filter(request) or [])

        # Add created_at filter to all models
        if 'created_at' not in filters:
            from .admin_filters import CreatedDateFilter
            filters.append(CreatedDateFilter)

        # Add MBID filter if model has MBID field
        if hasattr(self.model, 'mbid'):
            from .admin_filters import MissingMBIDFilter
            if MissingMBIDFilter not in filters:
                filters.append(MissingMBIDFilter)

        return filters


class DataQualityMixin:
    """Mixin for data quality indicators."""

    def data_quality_score(self, obj):
        """Calculate and display a simple data quality score."""
        score = 100
        checks = 0

        # Check for missing MBID
        if hasattr(obj, 'mbid'):
            checks += 1
            if not obj.mbid:
                score -= 30

        # Check for missing URL
        if hasattr(obj, 'url'):
            checks += 1
            if not obj.url:
                score -= 20

        # Check for generic/placeholder names
        if hasattr(obj, 'name') and obj.name:
            checks += 1
            if obj.name.lower() in ['unknown', 'untitled', 'various', 'n/a']:
                score -= 25

        # Normalize score
        if checks == 0:
            return format_html('<span style="color: #6c757d;">-</span>')

        # Color code the score
        if score >= 90:
            color = '#28a745'  # Green
        elif score >= 70:
            color = '#ffc107'  # Yellow
        else:
            color = '#dc3545'  # Red

        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color, max(0, score)
        )

    data_quality_score.short_description = 'Quality'
    data_quality_score.admin_order_field = 'name'  # Fallback ordering


class LinkableMixin:
    """Mixin for creating links between related objects."""

    def create_admin_link(self, obj, field_name, display_text=None):
        """Create a link to another admin page."""
        if not obj:
            return '-'

        try:
            app_label = obj._meta.app_label
            model_name = obj._meta.model_name
            url = reverse(f'admin:{app_label}_{model_name}_change', args=[obj.pk])
            text = display_text or str(obj)
            return format_html('<a href="{}">{}</a>', url, text)
        except:
            return str(obj) if obj else '-'

    def create_changelist_link(self, model_name, filter_param, filter_value, count, text=None):
        """Create a link to a filtered changelist."""
        if count == 0:
            return '0'

        url = reverse(f'admin:music_{model_name}_changelist')
        filter_url = f'{url}?{filter_param}={filter_value}'
        display_text = text or f'{count:,}'
        return format_html('<a href="{}">{}</a>', filter_url, display_text)


class TimestampMixin:
    """Mixin for consistent timestamp display."""

    def format_timestamp(self, timestamp, include_time=True):
        """Format timestamps consistently across admin interfaces."""
        if not timestamp:
            return '-'

        if include_time:
            return timestamp.strftime('%Y-%m-%d %H:%M')
        else:
            return timestamp.strftime('%Y-%m-%d')

    def get_time_ago(self, timestamp):
        """Get human-readable time ago string."""
        if not timestamp:
            return '-'

        now = timezone.now()
        diff = now - timestamp

        if diff.days > 365:
            years = diff.days // 365
            return f'{years} year{"s" if years != 1 else ""} ago'
        elif diff.days > 30:
            months = diff.days // 30
            return f'{months} month{"s" if months != 1 else ""} ago'
        elif diff.days > 0:
            return f'{diff.days} day{"s" if diff.days != 1 else ""} ago'
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f'{hours} hour{"s" if hours != 1 else ""} ago'
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f'{minutes} minute{"s" if minutes != 1 else ""} ago'
        else:
            return 'Just now'


class SearchOptimizedMixin:
    """Mixin for optimized search functionality."""

    def get_search_fields(self):
        """Get optimized search fields."""
        fields = list(super().get_search_fields() or [])

        # Add common search optimizations
        # Prefer exact matches over partial matches for performance
        optimized_fields = []
        for field in fields:
            if not field.startswith('=') and not field.startswith('@'):
                # Use '=' prefix for exact match on indexed fields
                if field in ['name', 'mbid']:
                    optimized_fields.append(f'={field}')
                else:
                    optimized_fields.append(field)
            else:
                optimized_fields.append(field)

        return optimized_fields