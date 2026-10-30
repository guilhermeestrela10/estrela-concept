import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const apiUrl = Deno.env.get("SUPABASE_URL")!;
const secretKeys = JSON.parse(Deno.env.get("SUPABASE_SECRET_KEYS") ?? "{}");
const serviceKey = secretKeys.default ?? Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
const headers = { "Content-Type": "application/json", "Cache-Control": "no-store" };

async function db(path: string, method = "GET", body?: unknown, prefer?: string) {
  if (!serviceKey) throw new Error("Supabase service key is unavailable.");
  const response = await fetch(`${apiUrl}/rest/v1/${path}`, {
    method,
    headers: { apikey: serviceKey, "Content-Type": "application/json", ...(prefer ? { Prefer: prefer } : {}) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) throw new Error(data?.message ?? "Supabase request failed.");
  return data;
}

async function authorized(request: Request) {
  const tokenHash = request.headers.get("x-estrela-token-sha256") ?? "";
  if (!/^[a-f0-9]{64}$/.test(tokenHash)) return false;
  return await db("rpc/edge_verify_token", "POST", { p_token_hash: tokenHash }) === true;
}

async function products(includeInactive = false) {
  const query = new URLSearchParams({
    select: "id,name,tagline,description,price,active,category:categories(name),images:product_images(url,alt,position),variants:product_variants(size,color,stock,active)",
    order: "name",
  });
  if (!includeInactive) query.set("active", "eq.true");
  const rows = await db(`products?${query}`);
  return rows.map((row: any) => {
    const image = row.images.sort((a: any, b: any) => a.position - b.position)[0] ?? {};
    return { id: row.id, name: row.name, category: row.category.name, tagline: row.tagline,
      description: row.description, price: Number(row.price), image: image.url ?? "", active: row.active,
      variants: row.variants };
  });
}

async function categories(includeInactive = true) {
  const query = new URLSearchParams({ select: "id,name,active", order: "name" });
  if (!includeInactive) query.set("active", "eq.true");
  return await db(`categories?${query}`);
}

async function orders() {
  const query = new URLSearchParams({
    select: "id,customer_name,customer_phone,status,total,created_at,items:order_items(product_name,size,color,quantity,unit_price,line_total)",
    order: "created_at.desc",
  });
  const rows = await db(`orders?${query}`);
  return rows.map((row: any) => ({ id: row.id, customerName: row.customer_name,
    customerPhone: row.customer_phone, status: row.status, total: Number(row.total), createdAt: row.created_at,
    items: row.items.map((item: any) => ({ name: item.product_name, size: item.size, color: item.color,
      quantity: item.quantity, unitPrice: Number(item.unit_price), lineTotal: Number(item.line_total) })) }));
}

async function handle(action: string, payload: any) {
  if (action === "products") return { products: await products(false) };
  if (action === "admin_products") return { products: await products(true) };
  if (action === "categories") return { categories: (await categories(false)).filter((item: any) => item.active) };
  if (action === "admin_categories") return { categories: await categories(true) };
  if (action === "orders") return { orders: await orders() };
  if (action === "summary") {
    const [allProducts, allOrders] = await Promise.all([products(false), orders()]);
    const byStatus: Record<string, { count: number; total: number }> = Object.fromEntries(
      ["novo", "em_andamento", "concluido", "cancelado"].map((status) => [status, { count: 0, total: 0 }]),
    );
    for (const order of allOrders) {
      byStatus[order.status].count++;
      byStatus[order.status].total += order.total;
    }
    return { products: allProducts.length, lowStockVariants: allProducts.reduce((count: number, product: any) =>
      count + product.variants.filter((variant: any) => variant.active && variant.stock <= 3).length, 0),
      orders: allOrders.length, sales: allOrders.filter((order: any) => order.status === "concluido")
        .reduce((sum: number, order: any) => sum + order.total, 0), byStatus };
  }
  if (action === "checkout") return await db("rpc/checkout_create_order", "POST", {
    p_customer_name: payload.customer?.name, p_customer_phone: payload.customer?.phone, p_items: payload.items,
  });
  if (action === "save_product") {
    await db("rpc/admin_save_product", "POST", { p_product: payload.product });
    return { product: (await products(true)).find((item: any) => item.id === payload.product.id) };
  }
  if (action === "save_category") {
    const result = await db("categories?select=id,name,active", "POST", payload.category, "return=representation");
    return { category: result[0] };
  }
  if (action === "set_product_active") {
    const query = new URLSearchParams({ id: `eq.${payload.id}`, select: "id" });
    const result = await db(`products?${query}`, "PATCH", { active: payload.active }, "return=representation");
    if (!result.length) throw new Error("Produto não encontrado.");
    return { ok: true };
  }
  if (action === "update_order_status") {
    await db("rpc/admin_update_order_status", "POST", { p_order_id: payload.id, p_status: payload.status });
    return { ok: true };
  }
  throw new Error("Ação não encontrada.");
}

Deno.serve(async (request: Request) => {
  if (request.method !== "POST") return new Response("Not found", { status: 404 });
  try {
    if (!await authorized(request)) return new Response(JSON.stringify({ error: "Unauthorized" }), { status: 401, headers });
    const payload = await request.json();
    const result = await handle(payload.action, payload);
    return new Response(JSON.stringify(result), { status: 200, headers });
  } catch (error) {
    return new Response(JSON.stringify({ error: error instanceof Error ? error.message : "Request failed." }),
      { status: 400, headers });
  }
});
