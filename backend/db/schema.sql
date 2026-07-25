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
alter table orders add column if not exists discount_code text;
alter table orders add column if not exists discount_amount numeric(10, 2) not null default 0;

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

-- ---------- discount_codes -------------------------------------------------
create table if not exists discount_codes (
  id               uuid primary key default gen_random_uuid(),
  code             text not null unique,           -- stored uppercased
  percent          integer not null check (percent between 1 and 100),
  first_order_only boolean not null default true,  -- only valid on a customer's first order
  active           boolean not null default true,
  max_uses         integer,                        -- null = unlimited
  used_count       integer not null default 0,
  expires_at       timestamptz,                    -- null = no expiry
  created_at       timestamptz not null default now()
);

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

-- ---------- settings (admin-editable key/value config) ---------------------
create table if not exists settings (
  key        text primary key,
  value      jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

-- delivery fee charged per order (recomputed server-side at checkout)
alter table orders add column if not exists delivery_fee numeric(10, 2) not null default 0;

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
