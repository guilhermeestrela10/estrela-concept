-- Estrela Concept: catalog, variants, inventory and WhatsApp orders.
create table public.categories (
  id text primary key check (id ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
  name text not null unique check (length(btrim(name)) between 1 and 60),
  active boolean not null default true,
  created_at timestamptz not null default now()
);

create table public.products (
  id text primary key check (id ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
  category_id text not null references public.categories(id) on delete restrict,
  name text not null check (length(btrim(name)) between 1 and 100),
  tagline text not null check (length(btrim(tagline)) between 1 and 160),
  description text not null check (length(btrim(description)) between 1 and 1200),
  price numeric(10,2) not null check (price > 0 and price <= 1000000),
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.product_images (
  id bigint generated always as identity primary key,
  product_id text not null references public.products(id) on delete cascade,
  url text not null check (length(url) <= 2048),
  alt text not null default '',
  position integer not null default 0 check (position >= 0),
  unique (product_id, position)
);

create table public.product_variants (
  id bigint generated always as identity primary key,
  product_id text not null references public.products(id) on delete restrict,
  size text not null check (length(btrim(size)) between 1 and 30),
  color text not null check (length(btrim(color)) between 1 and 40),
  sku text unique,
  price_override numeric(10,2) check (price_override is null or price_override > 0),
  stock integer not null default 0 check (stock between 0 and 1000000),
  active boolean not null default true,
  unique (product_id, size, color)
);

create table public.orders (
  id uuid primary key default gen_random_uuid(),
  customer_name text not null check (length(btrim(customer_name)) between 1 and 100),
  customer_phone text not null check (customer_phone ~ '^[0-9]{12,13}$'),
  status text not null default 'novo' check (status in ('novo','em_andamento','concluido','cancelado')),
  subtotal numeric(12,2) not null check (subtotal >= 0),
  shipping numeric(12,2) not null default 0 check (shipping >= 0),
  discount numeric(12,2) not null default 0 check (discount >= 0),
  total numeric(12,2) not null check (total >= 0),
  created_at timestamptz not null default now()
);

create table public.order_items (
  id bigint generated always as identity primary key,
  order_id uuid not null references public.orders(id) on delete cascade,
  product_id text not null,
  variant_id bigint references public.product_variants(id) on delete set null,
  product_name text not null,
  size text not null,
  color text not null,
  quantity integer not null check (quantity between 1 and 10),
  unit_price numeric(10,2) not null check (unit_price >= 0),
  line_total numeric(12,2) not null check (line_total >= 0)
);

create index products_active_category_idx on public.products(category_id, name) where active;
create index variants_active_product_idx on public.product_variants(product_id, size, color) where active;
create index orders_created_at_idx on public.orders(created_at desc);
create index orders_status_created_idx on public.orders(status, created_at desc);
create index order_items_order_idx on public.order_items(order_id);
create index order_items_variant_idx on public.order_items(variant_id);

alter table public.categories enable row level security;
alter table public.products enable row level security;
alter table public.product_images enable row level security;
alter table public.product_variants enable row level security;
alter table public.orders enable row level security;
alter table public.order_items enable row level security;

grant select on public.categories, public.products, public.product_images, public.product_variants to anon, authenticated;
grant all on public.categories, public.products, public.product_images, public.product_variants, public.orders, public.order_items to service_role;
grant usage, select on all sequences in schema public to service_role;

create policy "active categories are public" on public.categories
  for select to anon, authenticated using (active);
create policy "active products are public" on public.products
  for select to anon, authenticated using (active);
create policy "images of active products are public" on public.product_images
  for select to anon, authenticated using (
    exists (select 1 from public.products p where p.id = product_id and p.active)
  );
create policy "available variants of active products are public" on public.product_variants
  for select to anon, authenticated using (
    active and stock > 0 and exists (
      select 1 from public.products p where p.id = product_id and p.active
    )
  );

create function public.checkout_create_order(
  p_customer_name text,
  p_customer_phone text,
  p_items jsonb
) returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public, pg_temp
as $$
declare
  customer_name text := btrim(coalesce(p_customer_name, ''));
  customer_phone text := regexp_replace(coalesce(p_customer_phone, ''), '[^0-9]', '', 'g');
  requested record;
  chosen record;
  order_id uuid := gen_random_uuid();
  total numeric(12,2) := 0;
  result_items jsonb := '[]'::jsonb;
  item_total numeric(12,2);
begin
  if length(customer_name) not between 1 and 100 then
    raise exception 'Informe seu nome (até 100 caracteres).';
  end if;
  if length(customer_phone) in (10, 11) then
    customer_phone := '55' || customer_phone;
  end if;
  if customer_phone !~ '^[0-9]{12,13}$' then
    raise exception 'Informe um WhatsApp válido com DDD.';
  end if;
  if jsonb_typeof(p_items) is distinct from 'array' or jsonb_array_length(p_items) not between 1 and 50 then
    raise exception 'Adicione entre 1 e 50 itens ao carrinho.';
  end if;
  if exists (
    select 1 from jsonb_array_elements(p_items) item
    where jsonb_typeof(item) <> 'object'
      or jsonb_typeof(item->'productId') is distinct from 'string'
      or jsonb_typeof(item->'size') is distinct from 'string'
      or jsonb_typeof(item->'color') is distinct from 'string'
      or jsonb_typeof(item->'quantity') is distinct from 'number'
      or coalesce(item->>'quantity', '') !~ '^[1-9][0-9]*$'
      or length(item->>'quantity') > 2
      or (item->>'quantity')::integer not between 1 and 10
  ) then
    raise exception 'Um item do pedido está inválido.';
  end if;

  for requested in
    select item->>'productId' as product_id, item->>'size' as size, item->>'color' as color,
      sum((item->>'quantity')::integer)::integer as quantity
    from jsonb_array_elements(p_items) item
    group by item->>'productId', item->>'size', item->>'color'
    order by item->>'productId', item->>'size', item->>'color'
  loop
    if requested.quantity > 10 then
      raise exception 'A quantidade máxima por opção é 10.';
    end if;
    select p.id, p.name, coalesce(v.price_override, p.price) as price,
      v.id as variant_id, v.stock
    into chosen
    from public.products p
    join public.product_variants v on v.product_id = p.id
    where p.id = requested.product_id and p.active
      and v.size = requested.size and v.color = requested.color and v.active
    for update of v;
    if not found then
      raise exception 'Um dos produtos ou tamanhos não está disponível.';
    end if;
    if requested.quantity > chosen.stock then
      raise exception 'Estoque insuficiente para % (%).', chosen.name, requested.size;
    end if;
    update public.product_variants
      set stock = stock - requested.quantity
      where id = chosen.variant_id and stock >= requested.quantity;
    if not found then
      raise exception 'Estoque insuficiente para % (%).', chosen.name, requested.size;
    end if;
    item_total := round(chosen.price * requested.quantity, 2);
    total := total + item_total;
    result_items := result_items || jsonb_build_array(jsonb_build_object(
      'name', chosen.name, 'size', requested.size, 'color', requested.color,
      'quantity', requested.quantity, 'unitPrice', chosen.price, 'lineTotal', item_total
    ));
  end loop;

  insert into public.orders(id, customer_name, customer_phone, subtotal, total)
    values (order_id, customer_name, customer_phone, total, total);
  insert into public.order_items(order_id, product_id, variant_id, product_name, size, color,
    quantity, unit_price, line_total)
  select order_id, requested_items.product_id, chosen_items.variant_id, chosen_items.name,
    requested_items.size, requested_items.color, requested_items.quantity, chosen_items.price,
    round(chosen_items.price * requested_items.quantity, 2)
  from (
    select item->>'productId' as product_id, item->>'size' as size, item->>'color' as color,
      sum((item->>'quantity')::integer)::integer as quantity
    from jsonb_array_elements(p_items) item
    group by item->>'productId', item->>'size', item->>'color'
  ) requested_items
  join lateral (
    select p.name, coalesce(v.price_override, p.price) as price, v.id as variant_id
    from public.products p join public.product_variants v on v.product_id=p.id
    where p.id=requested_items.product_id and v.size=requested_items.size and v.color=requested_items.color
  ) chosen_items on true;

  return jsonb_build_object(
    'id', order_id, 'status', 'novo', 'items', result_items, 'total', total,
    'customer', jsonb_build_object('name', customer_name, 'phone', customer_phone)
  );
end;
$$;

create function public.admin_save_product(p_product jsonb) returns void
language plpgsql
security invoker
    set search_path = pg_catalog, public, pg_temp
as $$
declare
  product_id text := btrim(coalesce(p_product->>'id', ''));
  category_id text;
  product_name text := btrim(coalesce(p_product->>'name', ''));
  image_url text := btrim(coalesce(p_product->>'image', ''));
  variation jsonb;
  seen integer;
begin
  if product_id !~ '^[a-z0-9]+(?:-[a-z0-9]+)*$' or length(product_id) > 70
    or length(product_name) not between 1 and 100
    or length(btrim(coalesce(p_product->>'tagline', ''))) not between 1 and 160
    or length(btrim(coalesce(p_product->>'description', ''))) not between 1 and 1200
    or image_url !~ '^https://'
    or coalesce((p_product->>'price')::numeric, 0) <= 0
    or coalesce((p_product->>'price')::numeric, 0) > 1000000
    or jsonb_typeof(p_product->'variants') is distinct from 'array'
    or jsonb_array_length(p_product->'variants') not between 1 and 200 then
    raise exception 'Dados do produto inválidos.';
  end if;
  select id into category_id from public.categories
    where name = btrim(p_product->>'category') and active;
  if category_id is null then
    raise exception 'Selecione uma categoria ativa.';
  end if;
  if exists (
    select 1 from jsonb_array_elements(p_product->'variants') v
    where length(btrim(coalesce(v->>'size', ''))) not between 1 and 30
      or length(btrim(coalesce(v->>'color', ''))) not between 1 and 40
      or jsonb_typeof(v->'stock') <> 'number'
      or coalesce(v->>'stock', '') !~ '^[0-9]+$'
      or (v->>'stock')::numeric > 1000000
  ) then
    raise exception 'Variações ou estoque inválidos.';
  end if;
  select count(*) into seen from (
    select v->>'size', v->>'color' from jsonb_array_elements(p_product->'variants') v
    group by v->>'size', v->>'color' having count(*) > 1
  ) duplicates;
  if seen > 0 then raise exception 'Não repita a mesma combinação de tamanho e cor.'; end if;

  insert into public.products(id, category_id, name, tagline, description, price, active)
    values (product_id, category_id, product_name, btrim(p_product->>'tagline'),
      btrim(p_product->>'description'), (p_product->>'price')::numeric, coalesce((p_product->>'active')::boolean, true))
    on conflict (id) do update set category_id=excluded.category_id, name=excluded.name,
      tagline=excluded.tagline, description=excluded.description, price=excluded.price,
      active=excluded.active, updated_at=now();
  delete from public.product_images where product_images.product_id = product_id;
  insert into public.product_images(product_id, url, alt, position)
    values (product_id, image_url, product_name, 0);
  update public.product_variants set active=false where product_variants.product_id=product_id;
  for variation in select value from jsonb_array_elements(p_product->'variants')
  loop
    insert into public.product_variants(product_id, size, color, stock, active)
      values (product_id, btrim(variation->>'size'), btrim(variation->>'color'),
        (variation->>'stock')::integer, coalesce((variation->>'active')::boolean, true))
      on conflict (product_id, size, color) do update set
        stock=excluded.stock, active=excluded.active;
  end loop;
end;
$$;

create function public.admin_update_order_status(p_order_id uuid, p_status text) returns void
language plpgsql
security invoker
set search_path = pg_catalog, public, pg_temp
as $$
declare
  current_status text;
begin
  if p_status not in ('novo','em_andamento','concluido','cancelado') then
    raise exception 'Status de pedido inválido.';
  end if;
  select status into current_status from public.orders where id=p_order_id for update;
  if not found then raise exception 'Pedido não encontrado.'; end if;
  if current_status in ('cancelado','concluido') and p_status <> current_status then
    raise exception 'Pedidos cancelados ou concluídos não podem ser reabertos.';
  end if;
  if p_status='cancelado' and current_status <> 'cancelado' then
    update public.product_variants v
      set stock=v.stock + i.quantity
      from public.order_items i
      where i.order_id=p_order_id and i.variant_id=v.id;
  end if;
  update public.orders set status=p_status where id=p_order_id;
end;
$$;

revoke all on function public.checkout_create_order(text,text,jsonb) from public, authenticated;
grant execute on function public.checkout_create_order(text,text,jsonb) to anon, service_role;
revoke all on function public.admin_save_product(jsonb) from public, anon, authenticated;
grant execute on function public.admin_save_product(jsonb) to service_role;
revoke all on function public.admin_update_order_status(uuid,text) from public, anon, authenticated;
grant execute on function public.admin_update_order_status(uuid,text) to service_role;

insert into public.categories(id,name) values
  ('leggings','Leggings'),('tops','Tops'),('conjuntos','Conjuntos'),('shorts','Shorts'),('camisetas','Camisetas')
on conflict (id) do nothing;

insert into public.products(id,category_id,name,tagline,description,price,active) values
  ('legging-lua','leggings','Legging Lua','Conforto para acompanhar seu ritmo.','Legging de cintura alta com toque macio e elasticidade para treinar ou compor o look do dia.',139.90,true),
  ('top-aurora','tops','Top Aurora','Sustentação leve, presença marcante.','Top esportivo de modelagem confortável para combinar com suas peças favoritas.',89.90,true),
  ('conjunto-brisa','conjuntos','Conjunto Brisa','Seu estilo, seu brilho.','Conjunto coordenado para criar um visual de treino prático e cheio de personalidade.',219.90,true),
  ('short-movimento','shorts','Short Movimento','Liberdade para ir mais longe.','Short de treino versátil com caimento pensado para acompanhar seus movimentos.',99.90,true),
  ('camiseta-essencial','camisetas','Camiseta Essencial','Básica no nome, favorita no uso.','Camiseta confortável para aquecer, treinar e seguir o dia com leveza.',79.90,true)
on conflict (id) do nothing;

insert into public.product_images(product_id,url,alt,position) values
  ('legging-lua','https://images.unsplash.com/photo-1538805060514-97d9cc17730c?auto=format&fit=crop&w=1000&q=85','Legging Lua',0),
  ('top-aurora','https://images.unsplash.com/photo-1538805060514-97d9cc17730c?auto=format&fit=crop&w=1000&q=85','Top Aurora',0),
  ('conjunto-brisa','https://images.unsplash.com/photo-1517836357463-d25dfeac3438?auto=format&fit=crop&w=1000&q=85','Conjunto Brisa',0),
  ('short-movimento','https://images.unsplash.com/photo-1518611012118-696072aa579a?auto=format&fit=crop&w=1000&q=85','Short Movimento',0),
  ('camiseta-essencial','https://images.unsplash.com/photo-1525507119028-ed4c629a60a3?auto=format&fit=crop&w=1000&q=85','Camiseta Essencial',0)
on conflict (product_id,position) do nothing;

insert into public.product_variants(product_id,size,color,stock,active) values
  ('legging-lua','P','Preto',4,true),('legging-lua','M','Preto',5,true),('legging-lua','G','Preto',2,true),('legging-lua','M','Rosa',3,true),
  ('top-aurora','P','Azul-marinho',3,true),('top-aurora','M','Azul-marinho',4,true),('top-aurora','G','Azul-marinho',2,true),('top-aurora','M','Rosa',0,true),
  ('conjunto-brisa','P','Vinho',2,true),('conjunto-brisa','M','Vinho',3,true),('conjunto-brisa','G','Vinho',2,true),
  ('short-movimento','P','Preto',3,true),('short-movimento','M','Preto',5,true),('short-movimento','G','Preto',3,true),
  ('camiseta-essencial','P','Branco',4,true),('camiseta-essencial','M','Branco',4,true),('camiseta-essencial','G','Branco',3,true)
on conflict (product_id,size,color) do nothing;

