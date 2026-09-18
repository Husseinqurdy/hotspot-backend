import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0003_client_mikrotik_permissions'),
        ('sms', '0003_delete_smslog_alter_outgoingsms_priority'),
    ]

    operations = [
        # null=True kwa MAKUSUDI: ujumbe wa zamani (kabla ya isolation)
        # haukuwa na client, na hauhitaji ku-backfill — ni historia
        # tu. Ujumbe MPYA wote unaotokana na queue_sms() sasa
        # utaupitisha client moja kwa moja (angalia apps/sms/tasks.py).
        migrations.AddField(
            model_name='outgoingsms',
            name='client',
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='outgoing_sms',
                to='clients.client',
            ),
        ),
    ]
