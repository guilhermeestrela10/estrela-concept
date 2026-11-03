import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const apiUrl = Deno.env.get("SUPABASE_URL")!;
const secretKeys = JSON.parse(Deno.env.get("SUPABASE_SECRET_KEYS") ?? "{}");
const serviceKey = secretKeys.default ?? Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
const publishableKey = "sb_publishable_IhLqps6ILjc2RmsEb9x4Kg_h-oSvS4E";
const headers = { "Content-Type": "application/json", "Cache-Control": "no-store" };

class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

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

async function auth(path: string, method: string, body: unknown, key: string, accessToken?: string) {
  const response = await fetch(`${apiUrl}/auth/v1/${path}`, {
    method,
    headers: { apikey: key, "Content-Type": "application/json", ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}) },
    body: JSON.stringify(body),
  });
  const text = await response.text();
  return { response, data: text ? JSON.parse(text) : null };
}

async function authorized(request: Request) {
  const tokenHash = request.headers.get("x-estrela-token-sha256") ?? "";
  if (!/^[a-f0-9]{64}$/.test(tokenHash)) return false;
  return await db("rpc/edge_verify_token", "POST", { p_token_hash: tokenHash }) === true;
}

async function sessionHash(token: string) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(token));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function validSession(token: unknown) {
  if (typeof token !== "string" || token.length !== 64) return false;
  const hash = await sessionHash(token);
  const query = new URLSearchParams({ select: "user_id", token_hash: `eq.${hash}`, expires_at: `gt.${new Date().toISOString()}` });
  const sessions = await db(`admin_sessions?${query}`);
  if (!sessions.length) return false;
  const accounts = await db(`admin_accounts?select=auth_user_id&id=eq.true&auth_user_id=eq.${sessions[0].user_id}`);
  return accounts.length === 1;
}

function newSessionToken() {
  return [...crypto.getRandomValues(new Uint8Array(32))].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function createAdmin(payload: any) {
  const username = payload.username;
  const password = payload.password;
  if (typeof username !== "string" || !/^[A-Za-z0-9_-]{4,40}$/.test(username)) throw new ApiError("Nome de usuário inválido.", 400);
  if (typeof password !== "string" || password.length < 12 || password.length > 256) throw new ApiError("Crie uma senha com pelo menos 12 caracteres.", 400);
  if ((await db("admin_accounts?select=id")).length) throw new ApiError("A conta administrativa já está configurada.", 409);

  const email = `${username.toLowerCase()}@estrela-concept.invalid`;
  const created = await auth("admin/users", "POST", {
    email, password, email_confirm: true, app_metadata: { role: "admin" }, user_metadata: { username },
  }, serviceKey!, serviceKey!);
  if (!created.response.ok) throw new ApiError("Não foi possível criar o acesso no Supabase Auth.", 400);
  const userId = created.data.id;
  try {
    await db("admin_accounts", "POST", { id: true, username, email, auth_user_id: userId }, "return=minimal");
  } catch (error) {
    await auth(`admin/users/${userId}`, "DELETE", {}, serviceKey!, serviceKey!).catch(() => {});
    throw error;
  }
  return { ok: true };
}

async function adminLogin(payload: any) {
  const username = typeof payload.username === "string" ? payload.username : "";
  const password = typeof payload.password === "string" ? payload.password : "";
  const query = new URLSearchParams({ select: "email,auth_user_id", id: "eq.true", username: `eq.${username}` });
  const accounts = await db(`admin_accounts?${query}`);
  if (accounts.length !== 1) throw new ApiError("Usuário ou senha incorretos.", 401);

  const signedIn = await auth("token?grant_type=password", "POST", { email: accounts[0].email, password }, publishableKey);
  if (!signedIn.response.ok || signedIn.data.user?.id !== accounts[0].auth_user_id
      || signedIn.data.user?.app_metadata?.role !== "admin") throw new ApiError("Usuário ou senha incorretos.", 401);

  const token = newSessionToken();
  const expiresAt = new Date(Date.now() + 8 * 60 * 60 * 1000).toISOString();
  await db("admin_sessions", "POST", { token_hash: await sessionHash(token), user_id: accounts[0].auth_user_id, expires_at: expiresAt }, "return=minimal");
  await auth("logout", "POST", {}, publishableKey, signedIn.data.access_token).catch(() => {});
  return { ok: true, sessionToken: token, expiresAt };
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

async function uploadProductImage(payload: any) {
  const formats: Record<string, string> = { "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp" };
  const contentType = payload.contentType;
  const encoded = payload.fileBase64;
  if (!formats[contentType] || typeof encoded !== "string" || encoded.length > 4 * Math.ceil(4 * 1024 * 1024 / 3)
      || !/^[A-Za-z0-9+/]+={0,2}$/.test(encoded)) throw new ApiError("Envie uma foto JPEG, PNG ou WebP de até 4 MB.", 400);
  let bytes: Uint8Array;
  try { bytes = Uint8Array.from(atob(encoded), (character) => character.charCodeAt(0)); }
  catch { throw new ApiError("O arquivo de imagem está inválido.", 400); }
  const valid = contentType === "image/jpeg" ? bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff
    : contentType === "image/png" ? [0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a].every((byte,index) => bytes[index] === byte)
    : new TextDecoder().decode(bytes.subarray(0, 4)) === "RIFF" && new TextDecoder().decode(bytes.subarray(8, 12)) === "WEBP";
  if (!bytes.length || bytes.length > 4 * 1024 * 1024 || !valid) throw new ApiError("O conteúdo não corresponde ao formato de imagem informado.", 400);
  const path = `products/${crypto.randomUUID()}.${formats[contentType]}`;
  const uploaded = await fetch(`${apiUrl}/storage/v1/object/product-images/${path}`, {
    method: "POST", headers: { apikey: serviceKey!, Authorization: `Bearer ${serviceKey}`, "Content-Type": contentType }, body: bytes,
  });
  if (!uploaded.ok) throw new ApiError("Não foi possível salvar a foto no Supabase Storage.", 502);
  return { url: `${apiUrl}/storage/v1/object/public/product-images/${path}` };
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
  if (action === "admin_status") return { configured: (await db("admin_accounts?select=id")).length > 0 };
  if (action === "admin_setup") return await createAdmin(payload);
  if (action === "admin_login") return await adminLogin(payload);
  if (action === "admin_session") return { authenticated: await validSession(payload.sessionToken) };
  if (action === "admin_logout") {
    if (typeof payload.sessionToken === "string") {
      await db(`admin_sessions?token_hash=eq.${await sessionHash(payload.sessionToken)}`, "DELETE");
    }
    return { ok: true };
  }
  const privateActions = new Set(["admin_products", "admin_categories", "orders", "summary", "save_product", "upload_product_image",
    "save_category", "set_product_active", "update_order_status"]);
  if (privateActions.has(action) && !await validSession(payload.sessionToken)) throw new ApiError("Entre no painel para continuar.", 401);
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
  if (action === "upload_product_image") return await uploadProductImage(payload);
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
  throw new ApiError("Ação não encontrada.", 404);
}

Deno.serve(async (request: Request) => {
  if (request.method !== "POST") return new Response("Not found", { status: 404 });
  try {
    if (!await authorized(request)) return new Response(JSON.stringify({ error: "Unauthorized" }), { status: 401, headers });
    const payload = await request.json();
    const result = await handle(payload.action, payload);
    return new Response(JSON.stringify(result), { status: 200, headers });
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 500;
    return new Response(JSON.stringify({ error: error instanceof Error ? error.message : "Request failed." }), { status, headers });
  }
});
