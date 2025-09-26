# Generated migration to fix missing sync_count column

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('music', '0002_performance_indexes'),
    ]

    operations = [
        # Add the missing sync_count field to SyncStatus model
        migrations.AddField(
            model_name='syncstatus',
            name='sync_count',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Number of successful syncs performed'
            ),
        ),

        # Add the constraint for sync_count as defined in the model
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS sync_count_non_negative ON sync_status (sync_count) WHERE sync_count >= 0;",
            reverse_sql="DROP INDEX IF EXISTS sync_count_non_negative;"
        ),
    ]