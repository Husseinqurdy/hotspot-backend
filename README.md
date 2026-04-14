# RouteAfrica Hotspot Voucher System v3

Mfumo kamili wa kusimamia vouchers za MikroTik Tanzania.
Multi-tenant | Kiswahili + English | A7670E GSM | Railway + Neon

---

## Muundo wa Faili

```
hotspot_v3/
├── backend/                    # Django + DRF
│   ├── hotspot/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── celery.py
│   ├── apps/
│   │   ├── accounts/           # User model, Login, Auth
│   │   ├── clients/            # Multi-tenant clients
│   │   ├── routers/            # MikroTik management + API
│   │   ├── packages/           # Internet packages
│   │   ├── payments/           # Malipo records
│   │   ├── vouchers/           # Voucher lifecycle
│   │   ├── sms/                # SMS receive endpoint + tasks
│   │   └── devices/            # GSM A7670 device management
│   ├── manage.py
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/                   # React + TypeScript
│   ├── src/
│   │   ├── i18n/               # Kiswahili + English translations
│   │   ├── contexts/           # Auth + Language contexts
│   │   ├── components/         # Layout, UI components
│   │   ├── pages/
│   │   │   ├── admin/          # Dashboard, Clients, Devices
│   │   │   └── AllPages.tsx    # Admin + Client pages zote
│   │   └── styles/
│   └── package.json
│
└── arduino/
    ├── a7670e_hotspot.ino      # Code ya A7670E
    └── MAELEZO.md              # Maelezo ya kuprogramu
```

---

## Usanidi wa Backend (Railway)

### 1. Anzisha Railway project
```bash
# Install Railway CLI
npm install -g @railway/cli
railway login
railway new
```

### 2. Ongeza Redis na PostgreSQL
```
Railway Dashboard → Add Service → Redis
Railway Dashboard → Add Service → PostgreSQL
```

Au tumia Neon.tech kwa PostgreSQL (bure):
- Nenda https://neon.tech
- Unda database mpya
- Nakili connection string

### 3. Weka environment variables kwenye Railway:
```
SECRET_KEY=<generate random key>
DEBUG=False
ALLOWED_HOSTS=your-app.railway.app
DB_HOST=<neon host>
DB_NAME=<db name>
DB_USER=<db user>
DB_PASSWORD=<db password>
DB_SSLMODE=require
REDIS_URL=<railway redis url>
AT_USERNAME=<africa's talking username>
AT_API_KEY=<africa's talking api key>
AT_SENDER_ID=HOTSPOT
DEVICE_API_KEY=<random secret for A7670>
CORS_ALLOWED_ORIGINS=https://netsafi.umemeswahili.co.tz
```

### 4. Deploy
```bash
cd backend
railway up
railway run python manage.py migrate
railway run python manage.py createsuperuser
```

### 5. Unda Superadmin
```bash
railway run python manage.py shell
```
```python
from apps.accounts.models import User
u = User.objects.create_superuser('admin', 'admin@routeafrica.co.tz', 'password123')
u.role = 'superadmin'
u.save()
```

---

## Usanidi wa Frontend (cPanel)

### 1. Build frontend
```bash
cd frontend
npm install
cp .env.example .env.local
# Weka VITE_API_URL=https://your-app.railway.app/api
npm run build
```

### 2. Upload kwenye cPanel
- Nenda cPanel → File Manager
- Nenda `public_html/netsafi/` au subdomain folder
- Upload yaliyomo kwenye `dist/` folder
- Weka `.htaccess` kwa React routing:

```apache
Options -MultiViews
RewriteEngine On
RewriteCond %{REQUEST_FILENAME} !-f
RewriteRule ^ index.html [QSA,L]
```

---

## Flow ya Mzunguko Kamili

```
1. Mteja anaingia menyu ya Lipa Bili (M-Pesa/Tigo/Airtel/Halo)
2. Anaweka Lipa Namba ya SIM card iliyopo kwenye A7670E
3. Anaweka Reference ya client wake (mfano: X7K2)
4. Analipa kiasi (mfano: TZS 500)
5. SMS ya confirmation inakuja kwenye SIM card ya A7670E
6. A7670E inasoma SMS moja kwa moja (+CMT notification)
7. A7670E inatuma data kwa Django API (HTTPS POST)
8. Django inatambua client kwa prefix X7K2
9. Django inatafuta package ya TZS 500 kwa client huyo
10. Django inaunganika na MikroTik ya client (API port 8728)
11. MikroTik inaunda user/voucher automatically
12. Django inatuma SMS ya voucher kwa mteja kupitia Africa's Talking
13. Mteja anapokea SMS na voucher code
14. Mteja anaunganika WiFi na kuingiza code
15. MikroTik inamruhusu — anapata internet!
```

---

## Vipengele Muhimu

### Lipa Namba Dynamic
Admin anaweza kuongeza/kufuta/kubadilisha lipa namba kupitia:
`/admin/devices` → Add/Edit/Delete GSM Device

Clients wanaona lipa namba zilizo active kwenye dashboard yao automatically.

### Multi-language (Kiswahili + English)
Kubadilisha lugha: Bonyeza 🇹🇿 SW au 🇬🇧 EN kwenye sidebar.
Lugha inabaki kwenye localStorage.

### Multi-tenant
Kila client ana:
- Reference prefix yake unique (auto-generated)
- Routers zake
- Packages zake
- Vouchers zake
- Malipo yake

---

## API Endpoints

| Method | Endpoint | Maelezo |
|--------|----------|---------|
| POST | /api/auth/login/ | Login |
| POST | /api/auth/refresh/ | Refresh token |
| GET | /api/dashboard/superadmin/ | Admin dashibodi |
| GET | /api/dashboard/client/ | Client dashibodi |
| GET/POST | /api/clients/ | Clients CRUD |
| POST | /api/clients/{id}/add-balance/ | Ongeza bakaa |
| GET/POST | /api/routers/ | Routers CRUD |
| POST | /api/routers/{id}/test-connection/ | Test router |
| POST | /api/routers/{id}/sync-packages/ | Sync packages |
| GET/POST | /api/packages/ | Packages CRUD |
| GET | /api/payments/ | Malipo (read only) |
| GET | /api/vouchers/ | Vouchers (read only) |
| GET/POST | /api/devices/ | GSM Devices CRUD |
| GET | /api/devices/public/ | Lipa namba za public |
| POST | /api/sms/receive/ | A7670 endpoint (X-API-Key) |
