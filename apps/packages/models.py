import logging
from django.db import models, transaction
from django.core.exceptions import ValidationError
from apps.clients.models import Client

logger = logging.getLogger('hotspot')


class Package(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='packages')
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    duration_minutes = models.IntegerField()
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

    def duration_display(self):
        if self.duration_minutes < 60:
            return f"Dakika {self.duration_minutes}"
        elif self.duration_minutes < 1440:
            return f"Saa {self.duration_minutes // 60}"
        return f"Siku {self.duration_minutes // 1440}"

    def clean(self):
        if not self.client_id:
            return
        try:
            from apps.payments.models import ClientPackagePrice
            new_unique_amount = int(self.price) + self.client.identifier
            conflict = ClientPackagePrice.objects.filter(
                unique_amount=new_unique_amount
            ).exclude(package=self).first()
            if conflict:
                raise ValidationError({
                    'price': (
                        f"Bei hii inasababisha mgongano! Kiasi {new_unique_amount} "
                        f"tayari kinatumika na '{conflict.client.business_name}' "
                        f"kwenye package '{conflict.package.name}'. "
                        f"Tafadhali badilisha bei yako."
                    )
                })
        except ImportError:
            pass

    def save(self, *args, **kwargs):
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
            new_unique_amount = int(self.price) + self.client.identifier

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
        """✅ Futa package na profile yake kwenye MikroTik."""
        profile_name = self.mikrotik_profile
        client = self.client
        super().delete(*args, **kwargs)
        self._delete_from_mikrotik(profile_name, client)

    def _sync_to_mikrotik(self):
        """Unda au sasisha profile kwenye MikroTik routers zote za client."""
        try:
            from apps.routers.models import MikroTikRouter
            from apps.routers.mikrotik import get_mikrotik_connection

            routers = MikroTikRouter.objects.filter(
                client=self.client,
                is_online=True
            )

            if not routers.exists():
                logger.warning(f"Hakuna router online ya {self.client.business_name}")
                return

            rate_limit = f"{self.speed_up}M/{self.speed_down}M"
            session_timeout = f"{self.duration_minutes}m"

            for router in routers:
                try:
                    api = get_mikrotik_connection(router)
                    if not api:
                        logger.warning(f"Haiwezekani kuunganika {router.name}")
                        continue

                    existing = api.command(
                        '/ip/hotspot/user/profile/print',
                        queries={'name': self.mikrotik_profile}
                    )

                    if existing:
                        api.command(
                            '/ip/hotspot/user/profile/set',
                            {
                                '=.id': existing[0]['.id'],
                                '=rate-limit': rate_limit,
                                '=session-timeout': session_timeout,
                                '=shared-users': str(self.shared_users),
                            }
                        )
                        logger.info(f"✅ Profile '{self.mikrotik_profile}' updated kwenye {router.name}")
                    else:
                        api.add_hotspot_profile(
                            name=self.mikrotik_profile,
                            rate_limit=rate_limit,
                            session_timeout=session_timeout,
                            shared_users=self.shared_users
                        )
                        logger.info(f"✅ Profile '{self.mikrotik_profile}' created kwenye {router.name}")

                    api.disconnect()

                except Exception as e:
                    logger.error(f"MikroTik sync failed kwa {router.name}: {e}")

        except Exception as e:
            logger.error(f"_sync_to_mikrotik error: {e}")

    def _delete_from_mikrotik(self, profile_name, client):
        """✅ Futa profile kwenye MikroTik routers zote za client."""
        try:
            from apps.routers.models import MikroTikRouter
            from apps.routers.mikrotik import get_mikrotik_connection

            routers = MikroTikRouter.objects.filter(
                client=client,
                is_online=True
            )

            if not routers.exists():
                logger.warning(f"Hakuna router online ya {client.business_name}")
                return

            for router in routers:
                try:
                    api = get_mikrotik_connection(router)
                    if not api:
                        logger.warning(f"Haiwezekani kuunganika {router.name}")
                        continue

                    # Tafuta profile
                    existing = api.command(
                        '/ip/hotspot/user/profile/print',
                        queries={'name': profile_name}
                    )

                    if existing:
                        profile_id = existing[0].get('.id')
                        if profile_id:
                            # ✅ Tumia _talk moja kwa moja
                            api._talk([
                                '/ip/hotspot/user/profile/remove',
                                f'=.id={profile_id}'
                            ])
                            logger.info(f"✅ Profile '{profile_name}' deleted kutoka {router.name}")
                        else:
                            logger.warning(f"Profile '{profile_name}' haina .id")
                    else:
                        logger.info(f"Profile '{profile_name}' haikupatikana kwenye {router.name}")

                    api.disconnect()

                except Exception as e:
                    logger.error(f"MikroTik delete failed kwa {router.name}: {e}")

        except Exception as e:
            logger.error(f"_delete_from_mikrotik error: {e}")