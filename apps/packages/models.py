import logging
from django.db import models, transaction
from django.core.exceptions import ValidationError
from apps.clients.models import Client

logger = logging.getLogger('hotspot')


class Package(models.Model):
    DURATION_UNIT_CHOICES = [
        ('hours', 'Masaa'),
        ('days', 'Siku'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='packages')
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)

    duration_value = models.IntegerField(default=1)
    duration_unit = models.CharField(max_length=10, choices=DURATION_UNIT_CHOICES, default='hours')
    duration_minutes = models.IntegerField(default=60, editable=False)

    speed_up = models.CharField(max_length=10, default='2')
    speed_down = models.CharField(max_length=10, default='2')
    mikrotik_profile = models.CharField(max_length=50)
    shared_users = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['price']
        unique_together = ['client', 'name']

    def __str__(self):
        return f"{self.name} - TZS {self.price}"

    def _compute_duration_minutes(self):
        if self.duration_unit == 'hours':
            return self.duration_value * 60
        elif self.duration_unit == 'days':
            return self.duration_value * 1440
        return self.duration_value * 60

    def _mikrotik_session_timeout(self):
        """
        Session-timeout kwa MikroTik profile — daima 'unlimited' (00:00:00),
        bila kujali muda wa package. Muda halisi wa matumizi unadhibitiwa
        na on_login_script (angalia _sync_to_mikrotik).
        """
        return '00:00:00'

    def _scheduler_interval(self):
        if self.duration_unit == 'hours':
            return '00:01:00'
        elif self.duration_unit == 'days':
            return '00:05:00'
        return '00:01:00'

    def _mikrotik_limit_uptime(self):
        if self.duration_unit == 'hours':
            return f"{self.duration_value:02d}:00:00"
        elif self.duration_unit == 'days':
            return f"{self.duration_value}d 00:00:00"
        return f"01:00:00"

    def duration_display(self):
        if self.duration_unit == 'hours':
            return f"Saa {self.duration_value}"
        elif self.duration_unit == 'days':
            return f"Siku {self.duration_value}"
        if self.duration_minutes < 60:
            return f"Dakika {self.duration_minutes}"
        elif self.duration_minutes < 1440:
            return f"Saa {self.duration_minutes // 60}"
        return f"Siku {self.duration_minutes // 1440}"

    def _eligible_client_ids_for_conflict_check(self):
        """
        Kundi la client_ids linalotakiwa likaguliwe kwa mgongano wa
        unique_amount pamoja na self.client:

        - Kwa kawaida (hakuna kifaa chochote cha GSM kinachoshirikiwa
          na client huyu) → ni client mwenyewe TU. Uhuru kamili,
          hakuna athari kwa wengine.
        - Endapo client huyu ana kifaa (kama mmiliki AU kama
          mshiriki wa shared_with) kinachoshirikiwa na client
          wengine → kundi linapanuka kujumuisha wote wanaoshiriki
          kifaa hicho hicho (kwa sababu SMS moja kwenye kifaa hicho
          inaweza kulingana na package ya mtu yeyote kwenye kundi).

        Hii inaweka scope YOYOTE ya ukaguzi kuwa ndogo kama
        inavyowezekana — clients wasioshirikiana chochote hawaathiriwi
        kabisa na wengine.
        """
        from apps.devices.models import GSMDevice

        ids = {self.client_id}
        # Vifaa anavyomiliki client huyu na vina sharing
        owned_shared = GSMDevice.objects.filter(client_id=self.client_id).prefetch_related('shared_with')
        for device in owned_shared:
            ids.add(device.client_id)
            ids.update(device.shared_with.values_list('id', flat=True))
        # Vifaa vya wengine ambavyo client huyu ameongezwa kwenye shared_with vyao
        shared_into = GSMDevice.objects.filter(shared_with__id=self.client_id).select_related('client')
        for device in shared_into:
            ids.add(device.client_id)
            ids.update(device.shared_with.values_list('id', flat=True))
        return ids

    def _compute_unique_amount(self):
        """
        Kiasi kitakachotumika kutambulisha package hii kwenye SMS ya
        malipo (angalia apps/sms/tasks.py::process_payment_sms).

        - Client ASIYE na sharing yoyote (self.client.requires_payment_identifier()
          == False): unique_amount = bei KAMILI ya package, bila
          kuongeza chochote — device_id peke yake tayari inatosha
          kumtambulisha, hakuna anayeweza kugongana naye.
        - Client MWENYE sharing (anashirikiana kifaa na wengine):
          unique_amount = price + client.identifier, kama ilivyokuwa
          awali — bado tunahitaji njia ya kutofautisha malipo ndani
          ya hilo kundi dogo linaloshirikiana kifaa.
        """
        if self.client.requires_payment_identifier():
            return int(self.price) + self.client.identifier
        return int(self.price)

    def resync_unique_amount(self):
        """
        Hesabu upya na hifadhi unique_amount ya ClientPackagePrice
        iliyopo tayari — BILA kugusa MikroTik (tofauti na save()) na
        BILA kuunda upya ClientPackagePrice mpya. Tumika pale
        sharing status ya client imebadilika (GSMDevice.shared_with
        imeongezwa/imeondolewa) na packages zake zote zinahitaji
        kuhamia kati ya 'bei flat' na 'bei + identifier' — angalia
        callers kwenye apps/devices/views.py (claim/update actions).
        """
        from apps.payments.models import ClientPackagePrice
        new_unique_amount = self._compute_unique_amount()
        ClientPackagePrice.objects.filter(
            client=self.client, package=self
        ).update(unique_amount=new_unique_amount)

    def clean(self):
        if not self.client_id:
            return
        try:
            from apps.payments.models import ClientPackagePrice
            new_unique_amount = self._compute_unique_amount()

            eligible_ids = self._eligible_client_ids_for_conflict_check()

            # MUHIMU: ukaguzi huu unafanya kazi dhidi ya KUNDI la
            # eligible_ids (self mwenyewe, na endapo anashirikiana
            # kifaa na wengine — wale wengine pia), SIYO tena dhidi ya
            # clients wote wa mfumo mzima (jinsi ilivyokuwa kabla ya
            # isolation), wala siyo client mmoja peke yake pale
            # ambapo kuna sharing halisi.
            conflict = ClientPackagePrice.objects.filter(
                client_id__in=eligible_ids,
                unique_amount=new_unique_amount
            ).exclude(package=self).first()
            if conflict:
                if conflict.client_id == self.client_id:
                    raise ValidationError({
                        'price': (
                            f"Bei hii inasababisha mgongano na package yako "
                            f"nyingine '{conflict.package.name}' (kiasi "
                            f"{new_unique_amount} kinatumika humo tayari). "
                            f"Tafadhali badilisha bei yako."
                        )
                    })
                else:
                    raise ValidationError({
                        'price': (
                            f"Bei hii inasababisha mgongano na package ya "
                            f"'{conflict.client.business_name}' (kiasi "
                            f"{new_unique_amount}) — mnashirikiana kifaa "
                            f"kimoja cha malipo. Tafadhali badilisha bei yako."
                        )
                    })
        except ImportError:
            pass

    def save(self, *args, **kwargs):
        self.duration_minutes = self._compute_duration_minutes()

        is_new = self.pk is None
        price_changed = False

        if not is_new:
            try:
                old = Package.objects.get(pk=self.pk)
                price_changed = old.price != self.price
            except Package.DoesNotExist:
                pass

        self.full_clean()

        with transaction.atomic():
            super().save(*args, **kwargs)

            from apps.payments.models import ClientPackagePrice
            new_unique_amount = self._compute_unique_amount()

            if is_new:
                ClientPackagePrice.objects.create(
                    client=self.client,
                    package=self,
                    unique_amount=new_unique_amount
                )
            elif price_changed:
                ClientPackagePrice.objects.filter(
                    client=self.client,
                    package=self
                ).update(unique_amount=new_unique_amount)

        self._sync_to_mikrotik()

    def delete(self, *args, **kwargs):
        profile_name = self.mikrotik_profile
        client = self.client
        super().delete(*args, **kwargs)
        self._delete_from_mikrotik(profile_name, client)

    def _sync_to_mikrotik(self):
        """
        Unda au sasisha kwenye MikroTik routers zote za client:
          1. Hotspot user profile (speed + session-timeout + shared-users + on-login script)
          2. Scheduler moja ya package — backup mechanism inayofuta vouchers
             zilizofika limit-uptime
        """
        results = []
        try:
            from apps.routers.models import MikroTikRouter
            from apps.routers.mikrotik import get_mikrotik_connection

            routers = MikroTikRouter.objects.filter(client=self.client, is_online=True)
            if not routers.exists():
                logger.warning(f"Hakuna router online ya {self.client.business_name}")
                return results

            rate_limit      = f"{self.speed_up}M/{self.speed_down}M"
            session_timeout = self._mikrotik_session_timeout()
            limit_uptime    = self._mikrotik_limit_uptime()
            interval        = self._scheduler_interval()
            sched_name      = f"expire-{self.mikrotik_profile}"

            on_login_script = (
                f":local voucher $user;\r\n"
                f":if ([:len [/system scheduler find name=$voucher]]=0) do={{\r\n"
                f"  /system scheduler add \\\r\n"
                f"    name=$voucher \\\r\n"
                f"    comment=$voucher \\\r\n"
                f"    interval=\"{limit_uptime}\" \\\r\n"
                f"    on-event=\"/ip hotspot active remove [find user=$voucher]\\r\\n"
                f"/ip hotspot user remove [find name=$voucher]\\r\\n"
                f"/system scheduler remove [find name=$voucher]\"\r\n"
                f"}}"
            )

            on_event = (
                f":foreach u in=[/ip/hotspot/user find profile={self.mikrotik_profile}] do={{"
                f":local uname [/ip/hotspot/user get $u name];"
                f":local uptime [/ip/hotspot/user get $u uptime];"
                f":if ($uptime >= \"{limit_uptime}\") do={{"
                f"/ip/hotspot/active remove [find user=$uname];"
                f"/ip/hotspot/user remove $u;"
                f":log info (\"Voucher expired: \" . $uname);"
                f"}}"
                f"}}"
            )

            for router in routers:
                try:
                    api = get_mikrotik_connection(router)
                    if not api:
                        logger.warning(f"Haiwezekani kuunganika {router.name}")
                        results.append({'router': router.name, 'status': 'unreachable'})
                        continue

                    existing_profile = api.command(
                        '/ip/hotspot/user/profile/print',
                        queries={'name': self.mikrotik_profile}
                    )

                    profile_was_new = not existing_profile

                    if existing_profile:
                        api.command('/ip/hotspot/user/profile/set', {
                            '.id': existing_profile[0]['.id'],
                            'rate-limit': rate_limit,
                            'session-timeout': session_timeout,
                            'shared-users': str(self.shared_users),
                            'on-login': on_login_script,
                        })
                        logger.info(f"✅ Profile '{self.mikrotik_profile}' updated kwenye {router.name}")
                    else:
                        api.command('/ip/hotspot/user/profile/add', {
                            'name': self.mikrotik_profile,
                            'rate-limit': rate_limit,
                            'session-timeout': session_timeout,
                            'shared-users': str(self.shared_users),
                            'on-login': on_login_script,
                        })
                        logger.info(f"✅ Profile '{self.mikrotik_profile}' created kwenye {router.name}")

                    existing_sched = api.command(
                        '/system/scheduler/print',
                        queries={'name': sched_name}
                    )

                    if existing_sched:
                        api.command('/system/scheduler/set', {
                            '.id': existing_sched[0]['.id'],
                            'interval': interval,
                            'on-event': on_event,
                            'comment': f'Auto-expire vouchers za {self.mikrotik_profile} | {self.name}',
                        })
                        logger.info(f"✅ Scheduler '{sched_name}' updated kwenye {router.name}")
                    else:
                        api.command('/system/scheduler/add', {
                            'name': sched_name,
                            'start-date': 'jan/01/1970',
                            'start-time': '00:00:00',
                            'interval': interval,
                            'on-event': on_event,
                            'policy': 'read,write,policy,test',
                            'comment': f'Auto-expire vouchers za {self.mikrotik_profile} | {self.name}',
                            'disabled': 'false',
                        })
                        logger.info(f"✅ Scheduler '{sched_name}' created kwenye {router.name}")

                    api.disconnect()
                    results.append({'router': router.name, 'status': 'created' if profile_was_new else 'updated'})

                except Exception as e:
                    logger.error(f"MikroTik sync failed kwa {router.name}: {e}")
                    results.append({'router': router.name, 'status': 'failed', 'error': str(e)})

        except Exception as e:
            logger.error(f"_sync_to_mikrotik error: {e}")

        return results

    def _delete_from_mikrotik(self, profile_name, client):
        """Futa profile + scheduler kwenye MikroTik routers zote za client."""
        try:
            from apps.routers.models import MikroTikRouter
            from apps.routers.mikrotik import get_mikrotik_connection

            routers = MikroTikRouter.objects.filter(client=client, is_online=True)
            if not routers.exists():
                return

            sched_name = f"expire-{profile_name}"

            for router in routers:
                try:
                    api = get_mikrotik_connection(router)
                    if not api:
                        continue

                    existing = api.command(
                        '/ip/hotspot/user/profile/print',
                        queries={'name': profile_name}
                    )
                    if existing:
                        api._talk(['/ip/hotspot/user/profile/remove', f'=.id={existing[0][".id"]}'])
                        logger.info(f"✅ Profile '{profile_name}' deleted kutoka {router.name}")

                    existing_sched = api.command(
                        '/system/scheduler/print',
                        queries={'name': sched_name}
                    )
                    if existing_sched:
                        api.command('/system/scheduler/remove', {'.id': existing_sched[0]['.id']})
                        logger.info(f"✅ Scheduler '{sched_name}' deleted kutoka {router.name}")

                    api.disconnect()

                except Exception as e:
                    logger.error(f"MikroTik delete failed kwa {router.name}: {e}")

        except Exception as e:
            logger.error(f"_delete_from_mikrotik error: {e}")
