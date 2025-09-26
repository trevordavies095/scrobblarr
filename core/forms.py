"""
Forms for Scrobblarr core functionality including settings management.
"""
from django import forms
from django.core.exceptions import ValidationError


class LastFmSettingsForm(forms.Form):
    """
    Form for Last.fm configuration settings.

    Note: API key and secret are read-only from environment variables.
    This form only allows updating username and sync frequency.
    """

    lastfm_username = forms.CharField(
        max_length=255,
        required=True,
        label="Last.fm Username",
        help_text="Your Last.fm username for syncing scrobbles",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your Last.fm username'
        })
    )

    sync_frequency = forms.ChoiceField(
        choices=[
            ('manual', 'Manual - Sync only when requested'),
            ('hourly', 'Hourly - Sync every hour'),
            ('daily', 'Daily - Sync once per day'),
        ],
        required=True,
        label="Sync Frequency",
        help_text="How often to automatically sync new scrobbles from Last.fm",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    def clean_lastfm_username(self):
        """Validate Last.fm username format."""
        username = self.cleaned_data.get('lastfm_username', '').strip()

        if not username:
            raise ValidationError("Last.fm username is required")

        if len(username) < 2:
            raise ValidationError("Last.fm username must be at least 2 characters")

        if len(username) > 15:
            raise ValidationError("Last.fm username must be 15 characters or less")

        allowed_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-')
        if not all(c in allowed_chars for c in username):
            raise ValidationError("Last.fm username can only contain letters, numbers, hyphens, and underscores")

        return username