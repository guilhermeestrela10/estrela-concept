const currency = value => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(value);
const escapeText = value => String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const statusNames = {novo:"Novo", em_andamento:"Em andamento", concluido:"Concluído", cancelado:"Cancelado"};
const state = { products: [], orders: [], categories: [] };
const notice = document.querySelector("#admin-notice");
async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { "Content-Type":"application/json", ...(options.headers || {}) } });
  const body = await response.json();
  if (response.status === 401 && path.startsWith("/api/admin/") && !["/api/admin/login","/api/admin/setup"].includes(path)) {
    fetch("/api/admin/session").then(result => result.json()).then(session => showAuth(!session.configured, session.setupTokenRequired, session.setupAllowed));
  }
  if (!response.ok) throw new Error(body.error || "Não foi possível concluir a operação.");
  return body;
}
function showAuth(setup, tokenRequired = false, setupAllowed = true) {
  document.querySelector("#admin-auth").hidden = false;
  document.querySelector("#admin-app").hidden = true;
  document.querySelector("#logout").hidden = true;
  document.querySelector("#confirm-password-label").hidden = !setup;
  document.querySelector("#setup-token-label").hidden = !setup || !tokenRequired;
  document.querySelector("#auth-title").textContent = setup ? "Crie seu acesso" : "Acesso ao painel";
  document.querySelector("#auth-description").textContent = setup
    ? "Crie o acesso de administrador, protegido pelo Supabase Auth. Use pelo menos 12 caracteres."
    : "Entre com seu usuário e senha.";
  document.querySelector("#auth-submit").textContent = setup ? "Criar acesso e entrar" : "Entrar";
  document.querySelector("#auth-error").textContent = "";
  if (setup && !setupAllowed) document.querySelector("#auth-error").textContent = "A configuração inicial foi bloqueada. Defina ESTRELA_ADMIN_SETUP_TOKEN no servidor ou configure o acesso localmente antes da publicação.";
  document.querySelector('#auth-form [name="password"]').value = "";
  document.querySelector('#auth-form [name="confirmPassword"]').value = "";
}
function showAdmin() {
  document.querySelector("#admin-auth").hidden = true;
  document.querySelector("#admin-app").hidden = false;
  document.querySelector("#logout").hidden = false;
}
function showError(error) { notice.textContent = error.message; notice.classList.add("error"); }
function showMessage(message) { notice.textContent = message; notice.classList.remove("error"); }
fetch("/api/status").then(response => response.json()).then(status => {
  const online = status.backend === "supabase";
  document.querySelector("#backend-label").textContent = online ? "ESTRELA CONCEPT · SUPABASE ONLINE" : "ESTRELA CONCEPT · SUPABASE OFFLINE";
  document.querySelector("#backend-footnote").textContent = online
    ? "Dados no Supabase. Os produtos do catálogo são exemplos editáveis."
    : status.error || "Configure a conexão segura com o Supabase no servidor.";
}).catch(() => {});
async function refresh() {
  notice.textContent = "Carregando dados…";
  try {
    const [summary, products, orders, categories] = await Promise.all([
      api("/api/admin/summary"), api("/api/admin/products"), api("/api/admin/orders"), api("/api/admin/categories")
    ]);
    state.products = products.products; state.orders = orders.orders; state.categories = categories.categories;
    renderMetrics(summary); renderProducts(); renderOrders(); renderCategories();
    notice.textContent = "Painel atualizado."; notice.classList.remove("error");
  } catch(error) { showError(error); }
}
function renderMetrics(summary) {
  const count = summary.byStatus || {};
  document.querySelector("#metrics").innerHTML = [
    ["Produtos ativos", summary.products], ["Pedidos", summary.orders], ["Vendas concluídas", currency(summary.sales)], ["Variações com estoque baixo", summary.lowStockVariants]
  ].map(([label,value]) => `<article class="metric-card"><span>${escapeText(label)}</span><strong>${escapeText(value)}</strong></article>`).join("");
}
function renderProducts() {
  document.querySelector("#products-list").innerHTML = state.products.map(product => {
    const stock = product.variants.reduce((sum, variant) => sum + variant.stock, 0);
    return `<tr><td><strong>${escapeText(product.name)}</strong><small>${escapeText(product.id)}</small></td><td>${escapeText(product.category)}</td><td>${currency(product.price)}</td><td>${stock} un.</td><td><span class="status-pill ${product.active ? "status-live":"status-off"}">${product.active ? "Visível":"Oculto"}</span></td><td class="row-actions"><button data-edit="${escapeText(product.id)}">Editar</button><button data-toggle="${escapeText(product.id)}" data-active="${product.active}">${product.active ? "Ocultar":"Reativar"}</button></td></tr>`;
  }).join("") || `<tr><td colspan="6">Nenhum produto cadastrado.</td></tr>`;
}
function renderOrders() {
  const filter = document.querySelector("#order-filter").value;
  const orders = state.orders.filter(order => !filter || order.status === filter);
  document.querySelector("#orders-list").innerHTML = orders.map(order => {
    const items = order.items.map(item => `${item.quantity}× ${escapeText(item.name)} · ${escapeText(item.size)} · ${escapeText(item.color)}`).join("<br>");
    const date = new Date(order.createdAt).toLocaleString("pt-BR", { dateStyle:"short", timeStyle:"short" });
    const phone = String(order.customerPhone).replace(/\D/g, "");
    const waPhone = phone.startsWith("55") ? phone : `55${phone}`;
    const choices = Object.entries(statusNames).map(([key,name]) => `<option value="${key}" ${order.status === key ? "selected":""}>${name}</option>`).join("");
    return `<article class="order-card"><div class="order-main"><div class="order-title"><strong>Pedido #${escapeText(order.id)}</strong><span class="status-pill status-${escapeText(order.status)}">${statusNames[order.status] || escapeText(order.status)}</span></div><p>${escapeText(order.customerName)} · <a href="https://wa.me/${escapeText(waPhone)}" target="_blank" rel="noreferrer">${escapeText(order.customerPhone)} ↗</a></p><p>${items}</p><small>${date}</small></div><div class="order-side"><strong>${currency(order.total)}</strong><label>Status<select data-order-status="${escapeText(order.id)}" ${["cancelado","concluido"].includes(order.status) ? "disabled":""}>${choices}</select></label></div></article>`;
  }).join("") || `<div class="admin-empty">Nenhum pedido ${filter ? "com este status":"recebido"} ainda.</div>`;
}
function renderCategories() {
  document.querySelector("#categories-list").innerHTML = state.categories.map(category => `<span class="category-chip">${escapeText(category.name)}</span>`).join("");
  const options = state.categories.filter(item => item.active).map(item => `<option value="${escapeText(item.name)}">${escapeText(item.name)}</option>`).join("");
  document.querySelector('#product-form [name="category"]').innerHTML = options || `<option value="">Cadastre uma categoria primeiro</option>`;
}
function editProduct(product) {
  const form = document.querySelector("#product-form"); form.reset();
  form.elements.id.value = product?.id || ""; form.elements.name.value = product?.name || "";
  form.elements.category.value = product?.category || state.categories.find(item => item.active)?.name || "";
  form.elements.price.value = product?.price ?? ""; form.elements.tagline.value = product?.tagline || "";
  form.elements.description.value = product?.description || ""; form.elements.image.value = product?.image || "";
  form.elements.variants.value = product?.variants.map(item => `${item.size} | ${item.color} | ${item.stock}`).join("\n") || "";
  form.elements.active.checked = product?.active ?? true;
  document.querySelector("#product-form-title").textContent = product ? "Editar produto" : "Novo produto";
  document.querySelector("#product-form-error").textContent = "";
  document.querySelector("#product-dialog").showModal();
}
document.querySelector("#refresh").addEventListener("click", refresh);
document.querySelector("#auth-form").addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const setup = !document.querySelector("#confirm-password-label").hidden;
  const password = form.elements.password.value;
  if (setup && document.querySelector("#setup-token-label").hidden === false && !form.elements.setupToken.value) {
    document.querySelector("#auth-error").textContent = "Informe o token inicial de configuração."; return;
  }
  if (setup && password !== form.elements.confirmPassword.value) {
    document.querySelector("#auth-error").textContent = "As senhas não coincidem."; return;
  }
  const submit = document.querySelector("#auth-submit"); submit.disabled = true;
  try {
    await api(`/api/admin/${setup ? "setup":"login"}`, { method:"POST", body:JSON.stringify({username:form.elements.username.value.trim(),password,setupToken:form.elements.setupToken.value}) });
    showAdmin(); form.elements.password.value = ""; form.elements.confirmPassword.value = ""; await refresh();
  } catch(error) { document.querySelector("#auth-error").textContent = error.message; }
  finally { submit.disabled = false; }
});
document.querySelector("#logout").addEventListener("click", async () => {
  try { await api("/api/admin/logout", {method:"POST",body:"{}"}); showAuth(false); }
  catch(error) { showError(error); }
});
document.querySelector("#order-filter").addEventListener("change", renderOrders);
document.querySelectorAll(".admin-tab").forEach(tab => tab.addEventListener("click", () => {
  document.querySelectorAll(".admin-tab").forEach(item => item.classList.toggle("active", item === tab));
  ["orders","products","categories"].forEach(name => document.querySelector(`#${name}-section`).hidden = tab.dataset.tab !== name);
}));
document.querySelector("#new-product").addEventListener("click", () => editProduct());
document.querySelector("#product-cancel").addEventListener("click", () => document.querySelector("#product-dialog").close());
document.querySelector("#products-list").addEventListener("click", async event => {
  const edit = event.target.closest("[data-edit]");
  const toggle = event.target.closest("[data-toggle]");
  if (edit) { editProduct(state.products.find(item => item.id === edit.dataset.edit)); return; }
  if (toggle) {
    try { await api(`/api/admin/products/${encodeURIComponent(toggle.dataset.toggle)}`, { method:"PATCH", body:JSON.stringify({active:toggle.dataset.active !== "true"}) }); await refresh(); }
    catch(error) { showError(error); }
  }
});
document.querySelector("#product-form").addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.currentTarget; const data = new FormData(form);
  const submit = form.querySelector(".admin-submit"); submit.disabled = true;
  const uploadStatus = document.querySelector("#image-upload-status");
  document.querySelector("#product-form-error").textContent = "";
  try {
    const id = data.get("id") || data.get("name").trim().toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    const variants = data.get("variants").split(/\r?\n/).filter(line => line.trim()).map(line => {
      const [size,color,stock] = line.split("|").map(part => part.trim());
      if (!size || !color || !/^\d+$/.test(stock || "")) throw new Error("Use uma variação por linha no formato: M | Preto | 5.");
      return { size, color, stock:Number(stock), active:true };
    });
    let image = data.get("image").trim();
    const file = form.elements.imageFile.files[0];
    if (file) {
      if (file.size > 4 * 1024 * 1024) throw new Error("A foto deve ter no máximo 4 MB.");
      uploadStatus.textContent = "Enviando foto…";
      const response = await fetch("/api/admin/upload-image", { method:"POST", headers:{ "Content-Type":file.type }, body:file });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Não foi possível enviar a foto.");
      image = result.url; uploadStatus.textContent = "Foto enviada ao Supabase.";
    }
    if (!image) throw new Error("Informe a URL da foto ou escolha um arquivo.");
    const product = { id, name:data.get("name").trim(), category:data.get("category"), price:Number(data.get("price")), tagline:data.get("tagline").trim(), description:data.get("description").trim(), image, variants, active:form.elements.active.checked };
    await api(product.id && state.products.some(item => item.id === product.id) ? `/api/admin/products/${encodeURIComponent(product.id)}` : "/api/admin/products", { method:product.id && state.products.some(item => item.id === product.id) ? "PUT":"POST", body:JSON.stringify(product) });
    document.querySelector("#product-dialog").close(); showMessage("Produto salvo com sucesso."); await refresh();
  } catch(error) { document.querySelector("#product-form-error").textContent = error.message; }
  finally { submit.disabled = false; }
});
document.querySelector("#category-form").addEventListener("submit", async event => {
  event.preventDefault();
  try { await api("/api/admin/categories", {method:"POST", body:JSON.stringify({name:event.currentTarget.elements.name.value})}); event.currentTarget.reset(); await refresh(); showMessage("Categoria cadastrada."); }
  catch(error) { showError(error); }
});
document.querySelector("#orders-list").addEventListener("change", async event => {
  const select = event.target.closest("[data-order-status]"); if (!select) return;
  try { await api(`/api/admin/orders/${encodeURIComponent(select.dataset.orderStatus)}`, {method:"PATCH",body:JSON.stringify({status:select.value})}); await refresh(); }
  catch(error) { showError(error); await refresh(); }
});
api("/api/admin/session").then(session => {
  if (session.authenticated) { showAdmin(); refresh(); }
  else showAuth(!session.configured, session.setupTokenRequired, session.setupAllowed);
}).catch(showError);
