# دكّان كنعان — متجر إلكتروني (Online store)

متجرٌ إلكترونيٌّ كاملٌ للمونة الفلسطينيّة والفخّار الخليليّ: تصفّح المنتجات، سلّة،
حسابات للعملاء، عناوين توصيل محفوظة، طلبات (الدفع عند الاستلام)، ولوحة إدارة
للمدير لإدارة المنتجات والطلبات ومتابعة العملاء.

## البنية (Architecture)

```
Browser (Vue 3 SPA)  ──/api──►  Node/Express API  ──►  PostgreSQL
        nginx                    JWT auth + logic        (Cloud SQL / container)
```

- **Frontend** — Vue 3 + Vite, Pinia (المتاجر/الحالة), Vue Router. مبنيٌّ بنمط MVVM:
  - *View*: `src/views/*` + `src/components/*`
  - *ViewModel*: `src/stores/*` (auth, cart, catalog, orders, addresses)
  - *Model access*: `src/services/api.js`
- **Backend** — Express API في `server/` مع مصادقة JWT (bcrypt) وصلاحيات
  (عميل / مدير) في الوسائط (middleware).
- **Database** — PostgreSQL. المخطّط في `server/db/schema.sql`.

## التشغيل عبر Docker (الأسهل)

يتطلّب Docker Desktop.

```bash
cp .env.example .env        # عدّل كلمات المرور + بيانات المدير الأوّل
docker compose up --build
# افتح http://localhost:8080
```

يشغّل هذا ثلاث حاويات: `db` (Postgres) + `api` + `web` (nginx يقدّم الواجهة
ويمرّر `/api`). تُطبَّق قاعدة البيانات وتُزرَع المنتجات تلقائيًّا، ويُنشأ حساب
المدير من `SEED_MANAGER_EMAIL/PASSWORD`.

## التطوير محليًّا (بدون Docker)

```bash
# 1) قاعدة بيانات Postgres تعمل محليًّا، ثم:
cd server
cp .env.example .env         # DB_*, JWT_SECRET
npm install
npm run migrate              # المخطّط + المنتجات (+ مدير اختياري)
npm run dev                  # API على :8080

# 2) الواجهة في صدفة أخرى:
cd ..
npm install
npm run dev                  # http://localhost:5173  (يمرّر /api إلى :8080)
```

لجعل حسابك مديرًا يدويًّا:
```sql
update users set role = 'manager' where email = 'you@example.com';
```

## المسارات (Routes)

| المسار | الوصول | الوصف |
|---|---|---|
| `/` | عام | المتجر + السلّة + إتمام الطلب |
| `/login`, `/register` | زائر | الدخول / إنشاء حساب |
| `/account` | عميل | العناوين + سجلّ الطلبات |
| `/manager` | مدير | الطلبات + المنتجات (إضافة/حذف/تعبئة) + العملاء |

## النشر على GCP

- **API** → Cloud Run (حاوية `server/`). اضبط `INSTANCE_CONNECTION_NAME` + `DB_*`
  للاتّصال بـ Cloud SQL عبر مقبس Unix (مدعومٌ في `server/lib/db.js`).
- **Web** → Cloud Run (حاوية `Dockerfile.web`) أو أيّ استضافة ثابتة، مع تمرير
  `/api` إلى خدمة الـ API.
- **DB** → Cloud SQL for PostgreSQL. طبّق المخطّط بـ `npm run migrate`.

راجع [server/README.md](server/README.md) لتفاصيل إعداد Cloud SQL.
