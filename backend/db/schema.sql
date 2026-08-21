-- ============================================================================
-- دكّان كنعان — Cloud SQL (PostgreSQL) schema
-- Applied by `npm run migrate` (server/db/migrate.js).
-- Auth + authorization live in the API layer, not the DB (no Supabase/RLS).
-- ============================================================================

create extension if not exists "pgcrypto"; -- for gen_random_uuid()

do $$ begin
  create type user_role as enum ('customer', 'manager');
exception when duplicate_object then null; end $$;

do $$ begin
  create type order_status as enum ('pending', 'paid', 'fulfilled', 'cancelled');
exception when duplicate_object then null; end $$;

do $$ begin
  create type product_category as enum ('pantry', 'pottery');
exception when duplicate_object then null; end $$;

-- extra order statuses added after launch (being prepared / delivered)
alter type order_status add value if not exists 'preparing';
alter type order_status add value if not exists 'delivered';

-- ---------- users -----------------------------------------------------------
create table if not exists users (
  id            uuid primary key default gen_random_uuid(),
  email         text not null unique,
  password_hash text not null,
  full_name     text,
  phone         text,
  role          user_role not null default 'customer',
  created_at    timestamptz not null default now()
);

-- Which generation of sign-ins is still valid. Every token carries the number it
-- was issued under; changing the password raises it, which retires the tokens on
-- every other device at once (see security.py). Existing tokens predate the column
-- and carry no number, so they match the 0 every account starts at — the deploy
-- that adds this signs nobody out.
alter table users add column if not exists token_version integer not null default 0;

-- ---------- addresses (saved customer delivery locations) -------------------
create table if not exists addresses (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references users (id) on delete cascade,
  label      text,          -- e.g. "المنزل" / "العمل"
  city       text not null,
  street     text not null,
  house      text not null,
  notes      text,
  is_default boolean not null default false,
  created_at timestamptz not null default now()
);
create index if not exists addresses_user_id_idx on addresses (user_id);

-- ---------- products --------------------------------------------------------
create table if not exists products (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  description text,
  price       numeric(10, 2) not null check (price >= 0),
  unit        text,
  category    product_category not null,
  tag         text,
  image_url   text,
  stock       integer not null default 0 check (stock >= 0),
  is_active   boolean not null default true,
  created_at  timestamptz not null default now()
);

-- multiple product photos (ordered; images[0] mirrors image_url as the primary).
-- Added via ALTER so existing databases pick it up on re-migrate.
alter table products add column if not exists images jsonb not null default '[]'::jsonb;
-- small compressed preview shown in product lists (full images load on the detail page)
alter table products add column if not exists thumb_url text;
-- optional sub-type within a category (e.g. صحون / أكواب for pottery) — used for storefront filtering
alter table products add column if not exists type text;
create index if not exists products_category_type_idx on products (category, type);
-- manager-controlled display order (lower shows first); ties fall back to created_at
alter table products add column if not exists sort integer not null default 0;
-- last edit time, used as <lastmod> in sitemap.xml
alter table products add column if not exists updated_at timestamptz;
-- English copy, mirroring content_values' ar/en pairs. The existing columns stay
-- the Arabic ones so nothing has to be renamed or backfilled; a blank _en falls
-- back to the Arabic at render time, which is also what makes this safe to roll
-- out gradually (the manager can translate products one at a time).
alter table products add column if not exists name_en        text;
alter table products add column if not exists description_en text;
alter table products add column if not exists unit_en        text;
alter table products add column if not exists tag_en         text;
create index if not exists products_category_sort_idx on products (category, sort);
-- Backfill: any product with a primary image but no gallery gets a one-item gallery.
update products set images = jsonb_build_array(image_url)
  where (images is null or images = '[]'::jsonb) and coalesce(image_url, '') <> '';

-- ---------- orders ----------------------------------------------------------
create table if not exists orders (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid references users (id) on delete set null,
  customer_name text not null,
  phone         text not null,
  city          text not null,
  street        text not null,
  house         text not null,
  notes         text,
  status        order_status not null default 'pending',
  total         numeric(10, 2) not null default 0,
  created_at    timestamptz not null default now()
);
create index if not exists orders_user_id_idx on orders (user_id);
create index if not exists orders_created_at_idx on orders (created_at desc);
-- payment fields (added after initial launch; idempotent)
alter table orders add column if not exists payment_method text not null default 'cod';
alter table orders add column if not exists payment_status text not null default 'unpaid';
alter table orders add column if not exists ziina_payment_id text;
-- soft delete: manager can hide an order without erasing it from the database
alter table orders add column if not exists hidden boolean not null default false;
alter table orders add column if not exists discount_code text;
alter table orders add column if not exists discount_amount numeric(10, 2) not null default 0;

-- ---------- order_status_events (when each status was reached) --------------
-- Powers the customer-facing tracking timeline: one row per transition, so the
-- account page can show *when* an order was paid / prepared / delivered.
create table if not exists order_status_events (
  id         uuid primary key default gen_random_uuid(),
  order_id   uuid not null references orders (id) on delete cascade,
  status     order_status not null,
  created_at timestamptz not null default now()
);
create index if not exists order_status_events_order_idx on order_status_events (order_id, created_at);
-- Backfill: orders placed before this table existed get a single event for the
-- status they're currently in, timed at their creation.
insert into order_status_events (order_id, status, created_at)
  select o.id, o.status, o.created_at from orders o
  where not exists (select 1 from order_status_events e where e.order_id = o.id);

-- ---------- wishlists (saved products per customer) ------------------------
create table if not exists wishlists (
  user_id    uuid not null references users (id) on delete cascade,
  product_id uuid not null references products (id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, product_id)
);
create index if not exists wishlists_user_idx on wishlists (user_id, created_at desc);

-- ---------- stock_alerts ("tell me when it's back") -----------------------
-- Cleared once the alert fires, so a customer is notified once per restock.
create table if not exists stock_alerts (
  user_id    uuid not null references users (id) on delete cascade,
  product_id uuid not null references products (id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, product_id)
);
create index if not exists stock_alerts_product_idx on stock_alerts (product_id);

-- ---------- audit_logs (customer action trail, admin-only) ------------------
create table if not exists audit_logs (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid references users (id) on delete set null,
  action     text not null,
  detail     jsonb,
  ip         text,
  created_at timestamptz not null default now()
);
create index if not exists audit_logs_created_idx on audit_logs (created_at desc);
create index if not exists audit_logs_user_idx on audit_logs (user_id);
-- the storefront page the action came from (derived from the request Referer)
alter table audit_logs add column if not exists page text;
-- the API call that recorded it ("POST /api/orders"), which is the action the
-- customer actually took — the page is only where they were standing at the time
alter table audit_logs add column if not exists api text;
-- A visitor label derived from the request (see _visitor in audit.py): a hash of a
-- daily random salt with the address and browser. Counting guests by address alone
-- made a household or an office look like one person. Nothing is stored on the
-- customer's device, and the label cannot be matched across days.
alter table audit_logs add column if not exists visitor text;

-- ---------- signup_verifications (pending signups awaiting email+phone codes)
create table if not exists signup_verifications (
  id            uuid primary key default gen_random_uuid(),
  email         text not null,
  phone         text not null,
  full_name     text,
  password_hash text not null,
  email_code    text not null,
  phone_code    text not null,
  email_ok      boolean not null default false,
  phone_ok      boolean not null default false,
  attempts      integer not null default 0,
  expires_at    timestamptz not null,
  created_at    timestamptz not null default now()
);
create index if not exists signup_verifications_email_idx on signup_verifications (lower(email));

-- ---------- password_resets (a live code for a forgotten password) ----------
-- The code is stored bcrypt-hashed rather than in the clear. A pending signup row
-- above only finishes a signup somebody already started with a password they chose;
-- this one is a key to an account that already exists, so a leaked table must not
-- hand over working codes. At most one live row per address (see routers/auth.py),
-- which is also what keeps this table from growing.
create table if not exists password_resets (
  id         uuid primary key default gen_random_uuid(),
  email      text not null,
  code_hash  text not null,
  attempts   integer not null default 0,
  expires_at timestamptz not null,
  created_at timestamptz not null default now()
);
create index if not exists password_resets_email_idx on password_resets (lower(email));

-- ---------- carts (server-side basket so it follows a customer across devices)
create table if not exists carts (
  user_id    uuid primary key references users (id) on delete cascade,
  items      jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

-- ---------- error_reports (customer-side errors, for the admin to follow up) -
create table if not exists error_reports (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid references users (id) on delete set null,
  name       text,   -- contact snapshot so the admin can reach the customer
  email      text,
  phone      text,
  message    text not null,
  detail     text,
  page       text,
  user_agent text,
  created_at timestamptz not null default now()
);
create index if not exists error_reports_created_idx on error_reports (created_at desc);

-- ---------- push_subscriptions (Web Push endpoints per user/device) ---------
create table if not exists push_subscriptions (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references users (id) on delete cascade,
  endpoint   text not null unique,
  p256dh     text not null,
  auth       text not null,
  created_at timestamptz not null default now()
);
create index if not exists push_subscriptions_user_idx on push_subscriptions (user_id);

-- ---------- notifications (per-user in-app feed / bell) ---------------------
create table if not exists notifications (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references users (id) on delete cascade,
  type       text not null,                 -- 'new_order' | 'order_status' | 'message' | 'reply' | 'new_review' | 'review_status'
  title      text not null,
  body       text,
  order_id   uuid references orders (id) on delete set null,
  read       boolean not null default false,
  created_at timestamptz not null default now()
);
create index if not exists notifications_user_idx on notifications (user_id, created_at desc);

-- ---------- messages (two-way customer <-> shop support threads) ------------
-- A thread is all messages sharing user_id (the customer). sender says who wrote it.
create table if not exists messages (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null references users (id) on delete cascade,
  order_id         uuid references orders (id) on delete set null,   -- optional order context
  sender           text not null,           -- 'customer' | 'manager'
  body             text not null,
  read_by_customer boolean not null default false,
  read_by_manager  boolean not null default false,
  created_at       timestamptz not null default now()
);
create index if not exists messages_user_idx on messages (user_id, created_at);

-- ---------- discount_codes -------------------------------------------------
create table if not exists discount_codes (
  id               uuid primary key default gen_random_uuid(),
  code             text not null unique,           -- stored uppercased
  percent          integer check (percent between 1 and 100),
  first_order_only boolean not null default true,  -- only valid on a customer's first order
  active           boolean not null default true,
  max_uses         integer,                        -- null = unlimited
  used_count       integer not null default 0,
  expires_at       timestamptz,                    -- null = no expiry
  created_at       timestamptz not null default now()
);

-- A code takes either a percentage off or a fixed number of dirhams off. The amount
-- is the second kind; `percent` above lost its NOT NULL so a code can carry one or
-- the other. Existing codes are all percentages, so they satisfy this untouched.
alter table discount_codes add column if not exists amount numeric(10, 2);
alter table discount_codes alter column percent drop not null;
do $$ begin
  alter table discount_codes add constraint discount_codes_amount_positive
    check (amount is null or amount > 0);
exception when duplicate_object then null; end $$;
-- Exactly one of the two, never both and never neither: a code with no discount in
-- it, or with two, has no single meaning at the checkout.
do $$ begin
  alter table discount_codes add constraint discount_codes_one_kind
    check ((percent is null) <> (amount is null));
exception when duplicate_object then null; end $$;

-- ---------- order_items -----------------------------------------------------
create table if not exists order_items (
  id         uuid primary key default gen_random_uuid(),
  order_id   uuid not null references orders (id) on delete cascade,
  product_id uuid references products (id) on delete set null,
  name       text not null,           -- snapshot at purchase time
  price      numeric(10, 2) not null, -- snapshot
  qty        integer not null check (qty > 0)
);
create index if not exists order_items_order_id_idx on order_items (order_id);

-- Tracking token: lets whoever placed an order open its status page without an
-- account (/track/<id>?t=<token>) and lets a guest returning from Ziina confirm
-- their own payment. Unguessable, and scoped to that one order.
alter table orders add column if not exists track_token text;

-- Short, human-readable order number (shown as DK-XXXXXXX). Printed on the
-- confirmation e-mail and used with the customer's phone/e-mail by the guest order
-- lookup, so someone without an account can find their order from the number alone
-- plus something only they know. Unique, and drawn from an alphabet with no 0/O/1/I
-- so it survives being read out over the phone.
alter table orders add column if not exists ref text;
create unique index if not exists orders_ref_key on orders (ref) where ref is not null;
create unique index if not exists orders_track_token_key on orders (track_token) where track_token is not null;

-- Guest checkout creates an account with an EMPTY password_hash: it can't be
-- logged into (bcrypt rejects it), it exists so the order, the in-app chat and the
-- notifications have a user to hang off. Registering with that e-mail later claims
-- the row and sets a real password — see routers/auth.py.

-- ---------- settings (admin-editable key/value config) ---------------------
create table if not exists settings (
  key        text primary key,
  value      jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

-- delivery fee charged per order (recomputed server-side at checkout)
alter table orders add column if not exists delivery_fee numeric(10, 2) not null default 0;

-- admin-managed delivery zones: a city matching a zone's keywords pays its fee;
-- cities matching no zone pay settings.delivery.default_fee
create table if not exists delivery_zones (
  id         uuid primary key default gen_random_uuid(),
  label      text not null,
  keywords   text not null default '',   -- comma-separated city keywords to match
  fee        numeric(10, 2) not null default 0,
  sort       integer not null default 0,
  created_at timestamptz not null default now()
);

-- ---------- performance indexes --------------------------------------------
-- Added for the storefront sorts/filters and the manager dashboard. Each one
-- backs a query that would otherwise be a full table scan.
create index if not exists order_items_product_id_idx on order_items (product_id);
create index if not exists orders_status_idx on orders (status);
create index if not exists products_price_idx on products (price) where is_active;
create index if not exists users_created_at_idx on users (created_at desc);

-- ---------- content_values (editable "why us" cards, admin-managed) ---------
create table if not exists content_values (
  id         uuid primary key default gen_random_uuid(),
  sort       integer not null default 0,
  image_url  text,
  link       text,
  title_ar   text not null default '',
  title_en   text not null default '',
  desc_ar    text not null default '',
  desc_en    text not null default '',
  more_ar    text not null default '',
  more_en    text not null default '',
  updated_at timestamptz not null default now()
);

-- ---------- reviews (general shop reviews, written by customers) -------------
-- One review per customer (they edit it by submitting again). Nothing is public
-- until a manager approves it, so the storefront section can't be spammed.
create table if not exists reviews (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references users (id) on delete cascade,
  rating     smallint not null check (rating between 1 and 5),
  body       text not null default '',
  city       text,                                    -- shown under the name; optional
  status     text not null default 'pending' check (status in ('pending', 'approved', 'rejected')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
-- A customer may write as many as they like — each row stands on its own and is
-- edited through PUT /api/reviews/<id>. (There used to be a unique index here
-- enforcing one per account; dropped, and dropped on existing databases too.)
drop index if exists reviews_user_key;
create index if not exists reviews_user_idx on reviews (user_id, created_at desc);
-- the storefront's read: approved only, newest first
create index if not exists reviews_approved_idx on reviews (created_at desc) where status = 'approved';
-- the manager's moderation queue
create index if not exists reviews_status_idx on reviews (status, created_at desc);
-- optional photo the customer attached. Stored as files like product images (see
-- media.py); the card loads the thumbnail, the full one opens on click.
alter table reviews add column if not exists image_url text;
alter table reviews add column if not exists thumb_url text;

-- Writing a review needs an account, so every row has a user_id. Guest reviews were
-- briefly allowed and left two artefacts behind on databases from that window; undo
-- them, but only where no such row exists, so this can never fail a deploy.
do $$
begin
  if not exists (select 1 from reviews where user_id is null) then
    alter table reviews drop column if exists author_name;
    alter table reviews alter column user_id set not null;
  end if;
end $$;
