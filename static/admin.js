const currency = value => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(value);
const escapeText = value => String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const statusNames = {novo:"Novo", em_andamento:"Em andamento", concluido:"Concluído", cancelado:"Cancelado"};
const state = { products: [], orders: [], categories: [] };
const notice = document.querySelector("#admin-notice");
let imageItems = [];
const recoveryHash = new URLSearchParams(location.hash.slice(1));
let recoveryAccessToken = recoveryHash.get("type") === "recovery" ? recoveryHash.get("access_token") || "" : "";
const recoveryLinkError = recoveryHash.has("error") || recoveryHash.has("error_code");
if (recoveryAccessToken || recoveryLinkError) history.replaceState(null, "", location.pathname + location.search);
async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { "Content-Type":"application/json", ...(options.headers || {}) } });
  const body = await response.json();
  if (response.status === 401 && path.startsWith("/api/admin/") && !["/api/admin/login","/api/admin/setup","/api/admin/password-update"].includes(path)) {
    fetch("/api/admin/session").then(result => result.json()).then(session => showAuth(!session.configured, session.setupTokenRequired, session.setupAllowed));
  }
  if (!response.ok) throw new Error(body.error || "Não foi possível concluir a operação.");
  return body;
}
function showAuth(setup, tokenRequired = false, setupAllowed = true) {
  document.querySelector("#auth-form").hidden = false;
  document.querySelector("#recovery-form").hidden = true;
  document.querySelector("#reset-form").hidden = true;
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
  document.querySelector("#forgot-password").hidden = setup || !window.recoveryAvailable;
  document.querySelector("#auth-error").textContent = "";
  if (setup && !setupAllowed) document.querySelector("#auth-error").textContent = "A configuração inicial foi bloqueada. Defina ESTRELA_ADMIN_SETUP_TOKEN no servidor ou configure o acesso localmente antes da publicação.";
  document.querySelector('#auth-form [name="password"]').value = "";
  document.querySelector('#auth-form [name="confirmPassword"]').value = "";
}
function showPasswordReset() {
  document.querySelector("#admin-auth").hidden = false;
  document.querySelector("#admin-app").hidden = true;
  document.querySelector("#logout").hidden = true;
  document.querySelector("#auth-form").hidden = true;
  document.querySelector("#recovery-form").hidden = true;
  document.querySelector("#reset-form").hidden = false;
  if (!recoveryAccessToken) document.querySelector("#reset-error").textContent = "Link inválido ou expirado. Solicite uma nova recuperação.";
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
function renderProductImages() {
  const list = document.querySelector("#product-image-list");
  list.innerHTML = imageItems.map((item, index) => {
    const source = item.kind === "file" ? item.preview : /^https:\/\//i.test(item.url) ? item.url : "/static/favicon.svg";
    const detail = item.kind === "file" ? item.file.name : item.kind === "existing" ? "Foto cadastrada" : "URL adicionada";
    return `<article class="product-image-item"><img src="${escapeText(source)}" alt="Prévia da foto ${index + 1}"><div><strong>${index === 0 ? "Capa" : `Foto ${index + 1}`}</strong><small>${escapeText(detail)}</small></div><button type="button" data-image-up="${index}" aria-label="Mover foto ${index + 1} para cima" ${index === 0 ? "disabled" : ""}>↑</button><button type="button" data-image-down="${index}" aria-label="Mover foto ${index + 1} para baixo" ${index === imageItems.length - 1 ? "disabled" : ""}>↓</button><button type="button" data-image-remove="${index}" aria-label="Remover foto ${index + 1}">×</button></article>`;
  }).join("") || `<p class="image-list-empty">Nenhuma foto adicionada ainda.</p>`;
}
function syncImageInputs() {
  const form = document.querySelector("#product-form");
  form.elements.images.value = imageItems.filter(item => item.kind === "url").map(item => item.url).join("\n");
  const selection = new DataTransfer();
  imageItems.filter(item => item.kind === "file").forEach(item => selection.items.add(item.file));
  form.elements.imageFiles.files = selection.files;
}
function updatePendingImages() {
  const form = document.querySelector("#product-form");
  const urls = [...new Set(form.elements.images.value.split(/\r?\n/).map(url => url.trim()).filter(Boolean))];
  const files = [...form.elements.imageFiles.files];
  const previous = imageItems;
  const next = previous.filter(item => item.kind === "existing" || (item.kind === "url" ? urls.includes(item.url) : files.includes(item.file)));
  for (const url of urls) if (!next.some(item => item.kind === "url" && item.url === url)) next.push({kind:"url",url});
  for (const file of files) if (!next.some(item => item.kind === "file" && item.file === file)) next.push({kind:"file",file,preview:URL.createObjectURL(file)});
  previous.filter(item => item.kind === "file" && !files.includes(item.file)).forEach(item => URL.revokeObjectURL(item.preview));
  imageItems = next;
  syncImageInputs(); renderProductImages();
}
function editProduct(product) {
  const form = document.querySelector("#product-form"); form.reset();
  form.elements.id.value = product?.id || ""; form.elements.name.value = product?.name || "";
  form.elements.category.value = product?.category || state.categories.find(item => item.active)?.name || "";
  form.elements.price.value = product?.price ?? ""; form.elements.tagline.value = product?.tagline || "";
  form.elements.description.value = product?.description || ""; form.elements.images.value = "";
  imageItems = [...new Set(product?.images?.length ? product.images : product?.image ? [product.image] : [])].map(url => ({kind:"existing",url}));
  renderProductImages();
  form.elements.variants.value = product?.variants.map(item => `${item.size} | ${item.color} | ${item.stock}`).join("\n") || "";
  form.elements.active.checked = product?.active ?? true;
  document.querySelector("#product-form-title").textContent = product ? "Editar produto" : "Novo produto";
  document.querySelector("#product-form-error").textContent = "";
  document.querySelector("#image-upload-status").textContent = "Até 10 fotos no total, JPEG, PNG ou WebP; até 4 MB por arquivo. A ordem selecionada será mantida.";
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
document.querySelector("#forgot-password").addEventListener("click", () => {
  document.querySelector("#auth-form").hidden = true;
  document.querySelector("#recovery-form").hidden = false;
  document.querySelector("#recovery-error").textContent = "";
});
document.querySelector("#recovery-cancel").addEventListener("click", () => showAuth(false));
document.querySelector("#reset-cancel").addEventListener("click", () => showAuth(false));
document.querySelector("#recovery-form").addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const submit = form.querySelector("button[type=submit],button:not([type])");
  submit.disabled = true;
  try {
    const result = await api("/api/admin/password-recovery", { method:"POST", body:JSON.stringify({ username:form.elements.username.value.trim() }) });
    document.querySelector("#recovery-error").textContent = result.message;
  } catch (error) { document.querySelector("#recovery-error").textContent = error.message; }
  finally { submit.disabled = false; }
});
document.querySelector("#reset-form").addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const error = document.querySelector("#reset-error");
  if (!recoveryAccessToken) return;
  if (form.elements.password.value !== form.elements.confirmPassword.value) { error.textContent = "As senhas não coincidem."; return; }
  const submit = form.querySelector("button[type=submit],button:not([type])");
  submit.disabled = true;
  try {
    await api("/api/admin/password-update", { method:"POST", body:JSON.stringify({ accessToken:recoveryAccessToken, password:form.elements.password.value }) });
    recoveryAccessToken = "";
    form.reset();
    showAuth(false);
    document.querySelector("#auth-error").textContent = "Senha alterada. Entre com sua nova senha.";
  } catch (e) { error.textContent = e.message; }
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
  const form = event.currentTarget; updatePendingImages(); const data = new FormData(form);
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
    const newUrls = imageItems.filter(item => item.kind === "url").map(item => item.url);
    const files = imageItems.filter(item => item.kind === "file").map(item => item.file);
    if (newUrls.some(url => url.length > 2048 || !/^https:\/\//i.test(url))) throw new Error("Use URLs HTTPS válidas, uma por linha.");
    if (imageItems.length > 10) throw new Error("O produto pode ter no máximo 10 fotos.");
    if (files.some(file => file.size > 4 * 1024 * 1024)) throw new Error("Cada foto deve ter no máximo 4 MB.");
    if (files.some(file => !["image/jpeg","image/png","image/webp"].includes(file.type))) throw new Error("Use apenas arquivos JPEG, PNG ou WebP.");
    if (!imageItems.length) throw new Error("Informe ao menos uma URL ou escolha uma foto.");
    let uploadedImages = [];
    if (files.length) {
      let completed = 0;
      const uploads = await Promise.allSettled(files.map(async file => {
        const response = await fetch("/api/admin/upload-image", { method:"POST", headers:{ "Content-Type":file.type }, body:file });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Não foi possível enviar uma das fotos.");
        uploadStatus.textContent = `Enviando fotos (${++completed}/${files.length})…`;
        return result.url;
      }));
      const failedUpload = uploads.find(result => result.status === "rejected");
      if (failedUpload) throw failedUpload.reason;
      uploadedImages = uploads.map(result => result.value);
    }
    uploadStatus.textContent = files.length ? `${files.length} foto(s) enviada(s) ao Supabase.` : "";
    const uploadedByFile = new Map(files.map((file, index) => [file, uploadedImages[index]]));
    const images = imageItems.map(item => item.kind === "file" ? uploadedByFile.get(item.file) : item.url);
    const product = { id, name:data.get("name").trim(), category:data.get("category"), price:Number(data.get("price")), tagline:data.get("tagline").trim(), description:data.get("description").trim(), images, image:images[0], variants, active:form.elements.active.checked };
    await api(product.id && state.products.some(item => item.id === product.id) ? `/api/admin/products/${encodeURIComponent(product.id)}` : "/api/admin/products", { method:product.id && state.products.some(item => item.id === product.id) ? "PUT":"POST", body:JSON.stringify(product) });
    refresh(); document.querySelector("#product-dialog").close(); showMessage("Produto salvo com sucesso.");
  } catch(error) { document.querySelector("#product-form-error").textContent = error.message; }
  finally { submit.disabled = false; }
});
document.querySelector("#product-form").addEventListener("change", event => {
  if (event.target.name === "imageFiles") updatePendingImages();
});
document.querySelector("#product-form").addEventListener("click", event => {
  const button = event.target.closest("[data-image-up],[data-image-down],[data-image-remove]");
  if (!button) return;
  const index = Number(button.dataset.imageUp ?? button.dataset.imageDown ?? button.dataset.imageRemove);
  if (button.hasAttribute("data-image-remove")) {
    const [removed] = imageItems.splice(index, 1);
    if (removed.kind === "file") URL.revokeObjectURL(removed.preview);
  }
  else {
    const next = index + (button.hasAttribute("data-image-up") ? -1 : 1);
    [imageItems[index], imageItems[next]] = [imageItems[next], imageItems[index]];
  }
  syncImageInputs(); renderProductImages();
});
document.querySelector('#product-form [name="images"]').addEventListener("change", updatePendingImages);
document.querySelector("#product-dialog").addEventListener("close", () => {
  imageItems.filter(item => item.kind === "file").forEach(item => URL.revokeObjectURL(item.preview));
  imageItems = [];
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
document.querySelector("#test-order-email").addEventListener("click", async event => {
  const button = event.currentTarget;
  const status = document.querySelector("#email-test-status");
  button.disabled = true;
  button.textContent = "Enviando…";
  status.textContent = "Conectando ao Gmail…";
  status.classList.remove("error");
  try {
    const result = await api("/api/admin/test-email", {method:"POST", body:"{}"});
    status.textContent = `${result.message} Se não chegar em alguns minutos, confira o spam.`;
  } catch(error) {
    status.textContent = error.message;
    status.classList.add("error");
  } finally {
    button.disabled = false;
    button.textContent = "Enviar e-mail de teste";
  }
});
api("/api/admin/session").then(session => {
  window.recoveryAvailable = session.recoveryAvailable;
  if (recoveryAccessToken || recoveryLinkError) {
    showPasswordReset();
    if (recoveryLinkError) document.querySelector("#reset-error").textContent = "Link inválido ou expirado. Solicite uma nova recuperação.";
  } else if (session.authenticated) { showAdmin(); refresh(); }
  else {
    showAuth(!session.configured, session.setupTokenRequired, session.setupAllowed);
    if (recoveryLinkError) document.querySelector("#auth-error").textContent = "Link inválido ou expirado. Solicite uma nova recuperação.";
  }
}).catch(error => {
  if (recoveryAccessToken || recoveryLinkError) {
    showPasswordReset();
    if (recoveryAccessToken) document.querySelector("#reset-error").textContent = error.message;
  } else {
    showAuth(false);
    document.querySelector("#auth-error").textContent = error.message;
  }
});
