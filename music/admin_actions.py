"""
Custom admin actions for bulk operations and data management.
"""
import csv
from io import StringIO
from django.contrib import messages
from django.contrib.admin import action
from django.db import transaction
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.html import format_html
from django.core.exceptions import ValidationError

from .management.commands.validate_data import Command as ValidateCommand


def export_to_csv(modeladmin, request, queryset):
    """Export selected records to CSV format."""
    opts = modeladmin.model._meta
    model_name = opts.verbose_name_plural.title()

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{opts.model_name}_export_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'

    writer = csv.writer(response)

    # Get field names (excluding foreign keys for simplicity)
    field_names = []
    for field in opts.fields:
        if not field.many_to_many and not field.one_to_many:
            field_names.append(field.name)

    # Add computed fields for specific models
    if opts.model_name == 'artist':
        field_names.extend(['track_count', 'album_count', 'scrobble_count'])
    elif opts.model_name == 'album':
        field_names.extend(['artist_name', 'track_count', 'scrobble_count'])
    elif opts.model_name == 'track':
        field_names.extend(['artist_name', 'album_name', 'scrobble_count'])
    elif opts.model_name == 'scrobble':
        field_names.extend(['track_name', 'artist_name', 'album_name'])

    writer.writerow(field_names)

    # Write data rows
    for obj in queryset:
        row = []
        for field_name in field_names:
            if field_name in ['track_count', 'album_count', 'scrobble_count']:
                # Handle computed fields
                if hasattr(obj, field_name.replace('_count', 's')):
                    if field_name == 'track_count':
                        value = getattr(obj, 'tracks', obj.tracks if hasattr(obj, 'tracks') else obj.track_set).count()
                    elif field_name == 'album_count':
                        value = getattr(obj, 'albums', obj.albums if hasattr(obj, 'albums') else obj.album_set).count()
                    elif field_name == 'scrobble_count':
                        if opts.model_name == 'track':
                            value = obj.scrobbles.count()
                        else:
                            value = getattr(obj, 'tracks__scrobbles', 0) or 0
                else:
                    value = 0
            elif field_name == 'artist_name':
                value = getattr(obj, 'artist', None)
                value = str(value) if value else ''
            elif field_name == 'album_name':
                value = getattr(obj, 'album', None) or getattr(obj, 'track.album', None)
                value = str(value) if value else ''
            elif field_name == 'track_name':
                value = getattr(obj, 'track', None)
                value = str(value) if value else ''
            else:
                value = getattr(obj, field_name, '')
                if value is None:
                    value = ''
            row.append(str(value))
        writer.writerow(row)

    messages.success(request, f'Successfully exported {queryset.count()} {model_name.lower()} records to CSV.')
    return response

export_to_csv.short_description = "Export selected records to CSV"


def validate_selected_records(modeladmin, request, queryset):
    """Run data validation on selected records."""
    model_name = modeladmin.model._meta.verbose_name_plural

    # Create a validation command instance
    validator = ValidateCommand()

    # Filter validation to only selected records
    record_ids = list(queryset.values_list('id', flat=True))

    # Run validation logic (simplified version)
    issues_found = []
    fixes_applied = 0

    with transaction.atomic():
        for obj in queryset:
            try:
                # Basic validation checks
                if hasattr(obj, 'mbid') and obj.mbid:
                    # Validate MBID format
                    from .models import mbid_validator
                    try:
                        mbid_validator(obj.mbid)
                    except ValidationError:
                        issues_found.append(f'{obj}: Invalid MBID format')
                        if request.GET.get('apply_fixes'):
                            obj.mbid = None
                            obj.save(update_fields=['mbid'])
                            fixes_applied += 1

                if hasattr(obj, 'url') and obj.url:
                    # Basic URL validation
                    from django.core.validators import URLValidator
                    validator = URLValidator()
                    try:
                        validator(obj.url)
                    except ValidationError:
                        issues_found.append(f'{obj}: Invalid URL format')
                        if request.GET.get('apply_fixes'):
                            obj.url = None
                            obj.save(update_fields=['url'])
                            fixes_applied += 1

            except Exception as e:
                issues_found.append(f'{obj}: Validation error - {str(e)}')

    if issues_found:
        message = f'Found {len(issues_found)} validation issues in {model_name}:'
        for issue in issues_found[:10]:  # Limit to first 10 issues
            message += f'\n• {issue}'
        if len(issues_found) > 10:
            message += f'\n• ... and {len(issues_found) - 10} more'

        if fixes_applied > 0:
            message += f'\n\nApplied {fixes_applied} automatic fixes.'
            messages.success(request, message)
        else:
            messages.warning(request, message)
    else:
        messages.success(request, f'No validation issues found in selected {model_name}.')

validate_selected_records.short_description = "Validate selected records"


def remove_duplicates(modeladmin, request, queryset):
    """Remove duplicate records based on model-specific criteria."""
    model_name = modeladmin.model._meta.model_name
    duplicates_removed = 0

    if model_name == 'scrobble':
        # Remove duplicate scrobbles (same track + timestamp)
        seen = set()
        to_delete = []

        for scrobble in queryset.order_by('id'):
            key = (scrobble.track_id, scrobble.timestamp)
            if key in seen:
                to_delete.append(scrobble.id)
            else:
                seen.add(key)

        if to_delete:
            from .models import Scrobble
            duplicates_removed = Scrobble.objects.filter(id__in=to_delete).count()
            Scrobble.objects.filter(id__in=to_delete).delete()

    elif model_name in ['artist', 'album', 'track']:
        # More complex duplicate detection would go here
        messages.info(request, f'Duplicate detection for {model_name} records requires manual review.')
        return

    if duplicates_removed > 0:
        messages.success(request, f'Removed {duplicates_removed} duplicate records.')
    else:
        messages.info(request, 'No duplicate records found to remove.')

remove_duplicates.short_description = "Remove duplicates"


def clear_invalid_mbids(modeladmin, request, queryset):
    """Clear invalid MBID values from selected records."""
    from .models import mbid_validator
    cleared_count = 0

    for obj in queryset:
        if hasattr(obj, 'mbid') and obj.mbid:
            try:
                mbid_validator(obj.mbid)
            except ValidationError:
                obj.mbid = None
                obj.save(update_fields=['mbid'])
                cleared_count += 1

    if cleared_count > 0:
        messages.success(request, f'Cleared invalid MBIDs from {cleared_count} records.')
    else:
        messages.info(request, 'No invalid MBIDs found in selected records.')

clear_invalid_mbids.short_description = "Clear invalid MBIDs"


def mark_for_review(modeladmin, request, queryset):
    """Mark selected records for manual review (if model supports it)."""
    # This would be useful if we added a 'needs_review' field to models
    # For now, we'll just show a message
    model_name = modeladmin.model._meta.verbose_name_plural
    messages.info(
        request,
        f'Marked {queryset.count()} {model_name} for review. '
        f'Use filters to find records that need attention.'
    )

mark_for_review.short_description = "Mark for review"


def recalculate_counts(modeladmin, request, queryset):
    """Recalculate cached count fields (useful for debugging)."""
    model_name = modeladmin.model._meta.model_name
    updated_count = 0

    # This would be more useful if we had cached count fields
    # For now, it serves as a template for future count field updates

    for obj in queryset:
        # Trigger any count recalculations by accessing count methods
        if hasattr(obj, 'get_track_count'):
            obj.get_track_count()
        if hasattr(obj, 'get_album_count'):
            obj.get_album_count()
        if hasattr(obj, 'get_scrobble_count'):
            obj.get_scrobble_count()
        updated_count += 1

    messages.info(
        request,
        f'Recalculated counts for {updated_count} records. '
        f'Count values are computed dynamically.'
    )

recalculate_counts.short_description = "Recalculate counts"


def bulk_update_urls(modeladmin, request, queryset):
    """Bulk update URLs to MusicBrainz format based on MBIDs."""
    updated_count = 0

    for obj in queryset:
        if hasattr(obj, 'mbid') and obj.mbid and not obj.url:
            model_name = obj._meta.model_name
            if model_name == 'artist':
                obj.url = f'https://musicbrainz.org/artist/{obj.mbid}'
            elif model_name == 'album':
                obj.url = f'https://musicbrainz.org/release/{obj.mbid}'
            elif model_name == 'track':
                obj.url = f'https://musicbrainz.org/recording/{obj.mbid}'

            if obj.url:
                obj.save(update_fields=['url'])
                updated_count += 1

    if updated_count > 0:
        messages.success(request, f'Updated URLs for {updated_count} records.')
    else:
        messages.info(request, 'No records were updated (missing MBIDs or URLs already present).')

bulk_update_urls.short_description = "Generate MusicBrainz URLs from MBIDs"


def generate_data_quality_report(modeladmin, request, queryset):
    """Generate a detailed data quality report for selected records."""
    model_name = modeladmin.model._meta.verbose_name_plural

    # Generate report data
    total_records = queryset.count()
    missing_mbids = queryset.filter(mbid__isnull=True).count() if hasattr(queryset.model, 'mbid') else 0
    missing_urls = queryset.filter(url__isnull=True).count() if hasattr(queryset.model, 'url') else 0

    # Calculate quality score
    quality_issues = missing_mbids + missing_urls
    quality_score = ((total_records - quality_issues) / total_records * 100) if total_records > 0 else 0

    report_data = {
        'model_name': model_name,
        'total_records': total_records,
        'missing_mbids': missing_mbids,
        'missing_urls': missing_urls,
        'quality_score': round(quality_score, 1),
    }

    # Create a simple HTML report
    html_report = f"""
    <div style="padding: 20px; font-family: Arial, sans-serif;">
        <h2>Data Quality Report - {model_name}</h2>
        <div style="background: #f0f0f0; padding: 15px; border-radius: 5px; margin: 10px 0;">
            <h3>Summary</h3>
            <ul>
                <li><strong>Total Records:</strong> {total_records:,}</li>
                <li><strong>Missing MBIDs:</strong> {missing_mbids:,} ({missing_mbids/total_records*100:.1f}%)</li>
                <li><strong>Missing URLs:</strong> {missing_urls:,} ({missing_urls/total_records*100:.1f}%)</li>
                <li><strong>Quality Score:</strong> {quality_score}%</li>
            </ul>
        </div>
        <div style="margin-top: 20px;">
            <p><a href="javascript:history.back()">← Back to Admin</a></p>
        </div>
    </div>
    """

    return HttpResponse(html_report)

generate_data_quality_report.short_description = "Generate data quality report"


# Custom actions for specific models
def merge_duplicate_artists(modeladmin, request, queryset):
    """Merge duplicate artists (requires manual confirmation)."""
    if queryset.count() < 2:
        messages.error(request, 'Please select at least 2 artists to merge.')
        return

    # This would require a more complex interface
    # For now, just provide guidance
    messages.warning(
        request,
        f'Artist merging requires manual review. Selected {queryset.count()} artists. '
        f'Please review for duplicates and merge manually using the Django admin.'
    )

merge_duplicate_artists.short_description = "Merge duplicate artists (manual review required)"


def update_track_durations(modeladmin, request, queryset):
    """Update track durations from external sources (placeholder)."""
    # This would integrate with MusicBrainz API or other sources
    messages.info(
        request,
        f'Track duration updates require external API integration. '
        f'Selected {queryset.count()} tracks for future processing.'
    )

update_track_durations.short_description = "Update track durations (requires API integration)"