import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0003_client_mikrotik_permissions'),
        ('devices', '0003_alter_gsmdevice_device_id_and_more'),
    ]

    operations = [
        # MUHIMU: 'status' ndiyo hali ya zero-touch provisioning —
        # 'unclaimed' (kifaa kimejitangaza lakini hakina client bado)
        # au 'active' (kimeclaimwa, kina api_key). Vifaa 4
        # vilivyopo tayari (Vodacom/Tigo/Airtel/Halo, za mfumo wa
        # zamani wa centralized) vitaanza na 'unclaimed' kwa default
        # hapa — superadmin atahitaji kuvipa client kwa mkono (kupitia
        # Django admin) ili vipate api_key na kuwa 'active'
        # kiotomatiki (angalia GSMDevice.save()).
        migrations.AddField(
            model_name='gsmdevice',
            name='status',
            field=models.CharField(
                max_length=20,
                choices=[('unclaimed', 'Haijawekewa client (inasubiri admin)'), ('active', 'Active')],
                default='unclaimed',
            ),
        ),
        # client ni null=True KWA MAKUSUDI KABISA (hii SIYO hatua ya
        # muda kama ilivyokuwa mpango wa awali) — kifaa cha
        # 'unclaimed' HAKINA mmiliki bado, na hilo ni sehemu ya
        # muundo wa kudumu wa provisioning, siyo hitilafu ya
        # kusubiri kurekebishwa.
        migrations.AddField(
            model_name='gsmdevice',
            name='client',
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='gsm_devices',
                to='clients.client',
                help_text="Mmiliki mkuu wa kifaa hiki. Tupu = bado hakijawekewa client (unclaimed).",
            ),
        ),
        migrations.AddField(
            model_name='gsmdevice',
            name='shared_with',
            field=models.ManyToManyField(
                to='clients.client',
                related_name='shared_gsm_devices',
                blank=True,
                help_text="Clients wengine (kwa hiari) wanaoruhusiwa kutumia lipa namba hii hii.",
            ),
        ),
        # api_key ni null=True KWA MAKUSUDI KABISA (siyo hatua ya
        # muda) — kifaa cha 'unclaimed' halina api_key mpaka
        # kiclaimwe. Angalia GSMDevice.save() kwa jinsi inavyozalishwa
        # kiotomatiki mara client inapowekwa.
        migrations.AddField(
            model_name='gsmdevice',
            name='api_key',
            field=models.CharField(max_length=64, null=True, blank=True, unique=True, editable=False),
        ),
        # Fields hizi hazikuwa na blank=True awali — sasa zinahitaji
        # kuwa hiari kwa sababu kifaa cha 'unclaimed' hakina bado
        # taarifa hizi (zinajazwa wakati wa claim()).
        migrations.AlterField(
            model_name='gsmdevice',
            name='name',
            field=models.CharField(max_length=100, blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='gsmdevice',
            name='lipa_number',
            field=models.CharField(max_length=20, blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='gsmdevice',
            name='phone_number',
            field=models.CharField(max_length=20, blank=True, default=''),
        ),
        # KABLA: network=unique=True kwa mfumo mzima. SASA: client
        # anaweza kuwa na kifaa kimoja kwa kila network (uniqueness
        # inahamishwa chini kwenye constraint ya (client, network)) —
        # na null=True kwa sababu kifaa cha 'unclaimed' halina network
        # bado.
        migrations.AlterField(
            model_name='gsmdevice',
            name='network',
            field=models.CharField(
                choices=[
                    ('vodacom', 'Vodacom M-Pesa'),
                    ('tigo', 'Tigo Pesa'),
                    ('airtel', 'Airtel Money'),
                    ('halo', 'HaloPesa'),
                ],
                max_length=20, blank=True, null=True,
            ),
        ),
        migrations.AlterModelOptions(
            name='gsmdevice',
            options={'ordering': ['client_id', 'network']},
        ),
        migrations.AddConstraint(
            model_name='gsmdevice',
            constraint=models.UniqueConstraint(fields=('client', 'network'), name='unique_network_per_client'),
        ),
    ]
