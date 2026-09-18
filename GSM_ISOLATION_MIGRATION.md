# NetSafi — GSM Device Isolation + Zero-Touch Provisioning

## Muhtasari

Mfumo unabadilika kutoka **centralized GSM devices** (lipa namba moja
ikihudumia clients wote) kwenda **isolated GSM devices per account**,
na sasa pia una **zero-touch provisioning** (kama TTCL CPE
activation): kifaa (ESP32 + W5500 + WiFiManager fallback) kinajitangaza
lenyewe kwa cloud kikiwa 'unclaimed', superadmin anakiwekea client
kwa mbali kupitia dashboard, kifaa kinapokea api_key yake kwenye
checkin inayofuata.

## Muundo wa GSMDevice (mpya)

- `status` — `unclaimed` (default; client=None, api_key=None) au
  `active` (kina client na api_key)
- `client` — mmiliki mkuu (FK, **null=True KWA KUDUMU** — hii SIYO
  hatua ya muda, ni sehemu ya muundo wa provisioning)
- `shared_with` — M2M ya hiari; clients wengine wanaoruhusiwa
  kutumia lipa namba hiyo hiyo
- `api_key` — null mpaka kifaa ki-claimed; inazalishwa kiotomatiki
  kwenye `GSMDevice.save()` wakati wowote `client` inapowekwa na
  `api_key` bado haipo (iwe kupitia `claim()` method au Django admin
  ya kawaida kwa vifaa vya zamani/legacy)
- `device_id` — sasa ni "factory_id": kifaa CHENYEWE kinajitambulisha
  nayo (mfano `ESP.getEfuseMac()`), siyo admin anayeiweka kwa mkono

## Mtiririko wa provisioning

1. Kifaa kinawashwa → kinajaribu Ethernet (W5500, default) → button
   ikibonyezwa, inaingia WiFiManager (AP + captive portal) kwa
   kuweka WiFi credentials za mahali kilipo
2. Kifaa kinapiga `POST /devices/checkin/` na `{"factory_id": "..."}`
   — hakuna api_key inayotumika (bado haipo). Ikiwa `factory_id` ni
   mpya, `GSMDevice` mpya inaundwa na `status=unclaimed`
3. Kifaa kinaendelea kupiga `checkin/` mara kwa mara (mfano kila
   dakika) mpaka kipate `{"status": "active", "api_key": "..."}`
4. Superadmin anaingia dashboard yake, anaona orodha ya vifaa
   `unclaimed` (`GET /devices/pending/`), anachagua kimoja, anaweka
   `client`, `name`, `network`, `lipa_number`, `phone_number` (na
   `shared_with` ikihitajika) kupitia `POST /devices/<id>/claim/`
5. Kifaa kinapiga `checkin/` tena, kinapata `api_key` yake, kinaihifadhi
   kwenye NVS (flash) yake — sasa kinatumia hiyo `api_key` (header
   `X-API-Key`) kwenye kila `POST /sms/receive/` (malipo) na
   `GET /sms/outgoing/` (kuchukua SMS za kutuma)

## Matching logic (apps/sms/tasks.py) — haijabadilika

`device.eligible_clients()` = mmiliki + `shared_with` (kifaa cha
kawaida bila sharing = client mmoja tu). Kwa kifaa cha 'unclaimed'
(client=None), hii inarudisha orodha tupu — SMS yoyote itakayofika
kwa bahati mbaya kwa device_id isiyo na client itakataliwa salama.

## Mgongano wa bei (Package.clean()) — haijabadilika

Angalia maelezo ya awali — `unique_amount = price + client.identifier`,
na ukaguzi wa ziada una-scope kwa `eligible_clients` group.

## Faili zilizobadilika (backend)

```
apps/devices/models.py          — status, client/api_key nullable KWA KUDUMU, claim(), save() auto-key
apps/devices/serializers.py     — status field, api_key masking
apps/devices/views.py           — CheckinView (public), claim/pending actions kwenye GSMDeviceViewSet
apps/devices/admin.py           — status, shared_with display
apps/devices/urls.py            — /devices/checkin/ endpoint mpya
apps/payments/models.py         — unique_amount per-client, Payment.gsm_device
apps/payments/serializers.py    — gsm_device field
apps/payments/admin.py          — gsm_device field
apps/packages/models.py         — conflict check scoped to eligible_clients group
apps/sms/models.py              — OutgoingSMS.client
apps/sms/views.py               — per-device api_key auth, queue scoped to eligible_clients
apps/sms/admin.py               — client column
apps/routers/tasks.py           — queue_sms(..., client=...) threaded through
apps/vouchers/tasks.py          — queue_sms(..., client=...) threaded through
apps/accounts/views.py          — FIXED BUG: ClientDashboardView leaked ALL clients' lipa namba
```

### Migrations

```
apps/devices/migrations/0004_gsmdevice_provisioning.py     — status, client/shared_with/api_key (nullable KWA KUDUMU), network/name/lipa_number/phone_number blank=True
apps/payments/migrations/0004_clientpackageprice_per_client_payment_device.py
apps/payments/migrations/0005_backfill_payment_device.py   (data migration — auto-links old Payments to GSMDevice by device_id string match)
apps/sms/migrations/0004_outgoingsms_client.py
```

Hakuna migrations za 'backfill_api_key' tena — hazihitajiki kwa
sababu `api_key` sasa inazalishwa kiotomatiki wakati wowote `client`
inapowekwa (`GSMDevice.save()`), iwe kwa vifaa vipya (kupitia
`claim()`) au vifaa vya zamani (kupitia Django admin ya kawaida).

## Bug muhimu iliyopatikana na kurekebishwa

`apps/accounts/views.py::ClientDashboardView` ilikuwa ikionyesha
lipa namba za clients WOTE kwenye dashboard ya kila client. Imerekebishwa.

## Hatua za deployment kwenye droplet mpya

1. Restore backup ya database ya sasa
2. Badilisha files za code kwa hizi zilizoko humu
3. Endesha migrations:
   ```
   python manage.py migrate devices 0004
   python manage.py migrate payments 0004
   python manage.py migrate payments 0005   # backfill Payment.gsm_device (otomatiki)
   python manage.py migrate sms 0004
   ```
4. **Vifaa 4 vilivyopo tayari** (Vodacom/Tigo/Airtel/Halo) vitakuwa
   na `status=unclaimed` baada ya migration 0004. Chagua mojawapo ya:
   - **(a)** Ingia Django admin → GSMDevice → weka `client` kwa kila
     kimoja kwa mkono (api_key itazalishwa kiotomatiki, status
     itakuwa active) — hii ndiyo njia ya haraka kwa vifaa vinne tu
   - **(b)** Vi-deactivate (`is_active=False`) na uache vifaa vipya
     vipite kupitia mtiririko kamili wa `checkin/claim/` (bora zaidi
     endapo unabadilisha hardware kabisa)
5. **Firmware ya ESP32** ihitaji kuandikwa upya kuendana na
   provisioning flow mpya: `POST /devices/checkin/` mara ya kwanza
   (na kila baada ya muda mpaka `status=active`), kisha kuhifadhi
   `api_key` iliyorudishwa kwenye NVS, kisha kutumia `X-API-Key`
   header kwenye maombi yote yajayo ya `/sms/receive/` na
   `/sms/outgoing/`.
6. Ongeza rate-limiting kwenye `/devices/checkin/` kabla ya
   uzalishaji (production) — angalia TODO kwenye `CheckinView`.

## Frontend (React) — bado haijafanyiwa kazi

- Ukurasa wa "Vifaa vipya" (superadmin) — orodha ya `unclaimed`
  (`GET /devices/pending/`) + fomu ya claim (`POST /devices/<id>/claim/`)
- UI ya `shared_with` kwenye GSMDevice management iliyopo
- `total_gsm_devices` mpya kwenye SuperAdminDashboard

## Kilichobaki nje ya scope hii

- `apps/routers/job_views.py` bado inatumia `settings.DEVICE_API_KEY`
  ya global — kwa ajili ya router job polling (dhana tofauti kabisa
  na GSM SMS devices), si sehemu ya isolation/provisioning hii.
