const WHATSAPP_NUMBER = "5586999269836";
const money = value => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(value);
let cartLoadWarning = false;
let cartSaveWarning = false;
function loadCart() {
  try {
    const stored = localStorage.getItem("estrela-cart");
    const saved = JSON.parse(stored || "[]");
    if (!Array.isArray(saved)) { cartLoadWarning = true; return []; }
    const valid = saved.filter(item => item && typeof item.productId === "string"
      && typeof item.size === "string" && typeof item.color === "string"
      && Number.isSafeInteger(item.quantity) && item.quantity > 0);
    cartLoadWarning = valid.length !== saved.length;
    return valid;
  } catch {
    cartLoadWarning = true;
    return [];
  }
}
function escapeHTML(value) {
  return String(value).replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}
function safeImageUrl(value) {
  try {
    const url = new URL(value, window.location.origin);
    return url.protocol === "https:" ? escapeHTML(url.href) : "/static/favicon.svg";
  } catch {
    return "/static/favicon.svg";
  }
}
const state = { products: [], cart: loadCart(), selectedSize: "", selectedColor: "" };
const grid = document.querySelector("#product-grid");
const dialog = document.querySelector("#product-dialog");
const cartPanel = document.querySelector("#cart-panel");
const overlay = document.querySelector("#overlay");
let cartReturnFocus = null;

function availableVariants(product) { return product.variants.filter(item => item.active && item.stock > 0); }
function imageFor(product) { return safeImageUrl(product.image); }
function updateCartStorage() {
  try { localStorage.setItem("estrela-cart", JSON.stringify(state.cart)); cartLoadWarning = false; cartSaveWarning = false; }
  catch { cartSaveWarning = true; }
  renderCart();
}
function cartKey(item) { return `${item.productId}|${item.size}|${item.color}`; }
function countCart() { return state.cart.reduce((total, item) => total + item.quantity, 0); }
function getCartProduct(item) { return state.products.find(product => product.id === item.productId); }
function getCartVariant(item) { return getCartProduct(item)?.variants.find(variant => variant.size === item.size && variant.color === item.color); }
function canCheckoutItem(item) {
  const product = getCartProduct(item);
  const variant = getCartVariant(item);
  return Boolean(product?.active && variant?.active && variant.stock > 0);
}

function renderProducts() {
  const query = document.querySelector("#search").value.trim().toLocaleLowerCase("pt-BR");
  const category = document.querySelector("#category").value;
  const size = document.querySelector("#size").value;
  const maxPrice = Number(document.querySelector("#price").value || Infinity);
  const products = state.products.filter(product => {
    const hasSize = !size || availableVariants(product).some(item => item.size === size);
    return product.active && product.name.toLocaleLowerCase("pt-BR").includes(query)
      && (!category || product.category === category) && hasSize && product.price <= maxPrice;
  });
  grid.innerHTML = products.map(product => `
    <article class="product-card" data-product="${escapeHTML(product.id)}" tabindex="0" aria-label="Ver ${escapeHTML(product.name)}">
      <div class="product-photo"><img src="${imageFor(product)}" alt="${escapeHTML(product.name)}" loading="lazy"><span class="product-badge">${escapeHTML(String(product.category).toUpperCase())}</span><button class="quick-add" data-quick-add="${escapeHTML(product.id)}" aria-label="Escolher ${escapeHTML(product.name)}">+</button></div>
      <div class="product-info"><span class="product-category">ESTRELA CONCEPT</span><div class="product-title-line"><h3>${escapeHTML(product.name)}</h3><span class="product-price">${money(product.price)}</span></div><p class="product-tagline">${escapeHTML(product.tagline)}</p></div>
    </article>`).join("");
  document.querySelector("#result-count").textContent = `${products.length} ${products.length === 1 ? "peça encontrada" : "peças encontradas"}`;
  document.querySelector("#empty-state").hidden = products.length > 0;
}

function openProduct(id) {
  const product = state.products.find(item => item.id === id);
  if (!product) return;
  const variants = availableVariants(product);
  state.selectedSize = variants[0]?.size || "";
  state.selectedColor = variants.find(item => item.size === state.selectedSize)?.color || "";
  document.querySelector("#product-detail").innerHTML = `<div class="detail-layout"><img src="${imageFor(product)}" alt="${escapeHTML(product.name)}"><div class="detail-copy"><p class="eyebrow">${escapeHTML(String(product.category).toUpperCase())} · ESTRELA CONCEPT</p><h2>${escapeHTML(product.name)}</h2><div class="detail-price">${money(product.price)}</div><p>${escapeHTML(product.description)}</p><p class="detail-label">Tamanho</p><div class="option-list" id="size-options"></div><p class="detail-label">Cor</p><div class="option-list" id="color-options"></div><p class="detail-status" id="detail-status"></p><button class="button button-dark" id="add-to-cart">Adicionar à sacola <span>↗</span></button></div></div>`;
  renderVariantOptions(product);
  dialog.showModal();
  const url = new URL(window.location.href); url.searchParams.set("produto", id); history.replaceState({}, "", url);
}

function renderVariantOptions(product) {
  const variants = availableVariants(product);
  const sizes = [...new Set(product.variants.filter(v => v.active).map(v => v.size))];
  const colors = [...new Set(variants.map(v => v.color))];
  document.querySelector("#size-options").innerHTML = sizes.map(size => `<button class="option-button ${size === state.selectedSize ? "selected" : ""}" data-size="${escapeHTML(size)}" ${variants.some(v => v.size === size) ? "" : "disabled"}>${escapeHTML(size)}</button>`).join("");
  const validColors = [...new Set(variants.filter(v => v.size === state.selectedSize).map(v => v.color))];
  if (!validColors.includes(state.selectedColor)) state.selectedColor = validColors[0] || "";
  document.querySelector("#color-options").innerHTML = colors.map(color => `<button class="option-button ${color === state.selectedColor ? "selected" : ""}" data-color="${escapeHTML(color)}" ${validColors.includes(color) ? "" : "disabled"}>${escapeHTML(color)}</button>`).join("");
  document.querySelector("#detail-status").textContent = validColors.length ? "" : "Sem estoque no momento.";
  document.querySelector("#add-to-cart").disabled = !validColors.length;
}

function addItem(product, size, color, quantity = 1) {
  const variant = product.variants.find(item => item.size === size && item.color === color && item.active);
  const existing = state.cart.find(item => cartKey(item) === cartKey({ productId: product.id, size, color }));
  const requested = (existing?.quantity || 0) + quantity;
  if (!variant || requested > variant.stock) return false;
  if (existing) existing.quantity = requested;
  else state.cart.push({ productId: product.id, size, color, quantity });
  updateCartStorage();
  return true;
}

function renderCart() {
  document.querySelector("#cart-count").textContent = countCart();
  const lines = state.cart.map(item => {
    const product = getCartProduct(item);
    const available = canCheckoutItem(item);
    const title = product?.name || "Produto indisponível";
    const image = product ? `<img src="${imageFor(product)}" alt="">` : `<div class="cart-missing-image" aria-hidden="true">✳</div>`;
    const controls = available
      ? `<strong>${money(product.price * item.quantity)}</strong><div class="quantity-control"><button data-quantity="-1" data-key="${escapeHTML(cartKey(item))}" aria-label="Diminuir quantidade">−</button><span>${item.quantity}</span><button data-quantity="1" data-key="${escapeHTML(cartKey(item))}" aria-label="Aumentar quantidade">+</button></div>`
      : `<p class="cart-unavailable">Esta opção não está mais disponível.</p>`;
    return `<div class="cart-row${available ? "" : " cart-row-unavailable"}">${image}<div><h3>${escapeHTML(title)}</h3><p>${escapeHTML(item.size)} · ${escapeHTML(item.color)}</p>${controls}</div><button class="remove-item" data-remove="${escapeHTML(cartKey(item))}" aria-label="Remover ${escapeHTML(title)}">×</button></div>`;
  }).join("");
  document.querySelector("#cart-items").innerHTML = lines;
  const empty = state.cart.length === 0;
  document.querySelector("#cart-empty").hidden = !empty;
  document.querySelector("#cart-summary").hidden = empty;
  const subtotal = state.cart.reduce((sum, item) => sum + (canCheckoutItem(item) ? getCartProduct(item).price * item.quantity : 0), 0);
  document.querySelector("#cart-subtotal").textContent = money(subtotal);
  document.querySelector("#whatsapp-order-link").hidden = true;
  const unavailable = state.cart.some(item => !canCheckoutItem(item));
  document.querySelector("#cart-notice").textContent = cartLoadWarning
    ? "A sacola salva estava inválida; começamos uma nova sacola vazia."
    : cartSaveWarning ? "O navegador não salvou a sacola; ela ficará disponível apenas nesta sessão." : "";
  document.querySelector("#checkout").disabled = unavailable;
  document.querySelector("#checkout-message").textContent = unavailable
    ? "Remova as opções indisponíveis para preparar o pedido." : "";
}

function showCart() {
  cartReturnFocus = document.activeElement;
  overlay.hidden = false; cartPanel.hidden = false; document.body.style.overflow = "hidden";
  document.querySelector("#cart-close").focus();
}
function hideCart() {
  overlay.hidden = true; cartPanel.hidden = true; document.body.style.overflow = "";
  if (cartReturnFocus?.isConnected) cartReturnFocus.focus();
}
function whatsappUrl(message) { return `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(message)}`; }

cartPanel.addEventListener("keydown", event => {
  if (event.key === "Escape") { event.preventDefault(); hideCart(); return; }
  if (event.key !== "Tab") return;
  const focusable = [...cartPanel.querySelectorAll('a[href], button:not([disabled])')]
    .filter(element => element.getClientRects().length > 0);
  if (!focusable.length) { event.preventDefault(); cartPanel.focus(); return; }
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
});

document.querySelector("#search").addEventListener("input", renderProducts);
["#category", "#size", "#price"].forEach(selector => document.querySelector(selector).addEventListener("change", renderProducts));
grid.addEventListener("click", event => {
  const quick = event.target.closest("[data-quick-add]");
  if (quick) { event.stopPropagation(); openProduct(quick.dataset.quickAdd); return; }
  const card = event.target.closest("[data-product]"); if (card) openProduct(card.dataset.product);
});
grid.addEventListener("keydown", event => { if ((event.key === "Enter" || event.key === " ") && event.target.matches("[data-product]")) { event.preventDefault(); openProduct(event.target.dataset.product); } });
document.querySelector("#product-detail").addEventListener("click", event => {
  const sizeButton = event.target.closest("[data-size]");
  const colorButton = event.target.closest("[data-color]");
  const productId = new URLSearchParams(location.search).get("produto");
  const product = state.products.find(item => item.id === productId);
  if (sizeButton && product) { state.selectedSize = sizeButton.dataset.size; renderVariantOptions(product); }
  if (colorButton && product) { state.selectedColor = colorButton.dataset.color; renderVariantOptions(product); }
  if (event.target.id === "add-to-cart" && product) {
    const ok = addItem(product, state.selectedSize, state.selectedColor);
    document.querySelector("#detail-status").textContent = ok ? "Peça adicionada à sacola." : "Não há estoque suficiente para esta opção.";
    if (ok) setTimeout(() => dialog.close(), 500);
  }
});
document.querySelector("#product-close").addEventListener("click", () => dialog.close());
dialog.addEventListener("close", () => { const url = new URL(location.href); url.searchParams.delete("produto"); history.replaceState({}, "", url); });
document.querySelector("#cart-open").addEventListener("click", showCart);
document.querySelector("#cart-close").addEventListener("click", hideCart);
document.querySelector("#continue-shopping").addEventListener("click", hideCart);
overlay.addEventListener("click", hideCart);
document.querySelector("#cart-items").addEventListener("click", event => {
  const remove = event.target.closest("[data-remove]");
  if (remove) { state.cart = state.cart.filter(item => cartKey(item) !== remove.dataset.remove); updateCartStorage(); return; }
  const control = event.target.closest("[data-quantity]");
  if (!control) return;
  const item = state.cart.find(entry => cartKey(entry) === control.dataset.key);
  if (!item) return;
  const product = state.products.find(entry => entry.id === item.productId);
  const variant = product?.variants.find(entry => entry.size === item.size && entry.color === item.color);
  const next = item.quantity + Number(control.dataset.quantity);
  if (next < 1) state.cart = state.cart.filter(entry => entry !== item);
  else if (variant && next <= variant.stock) item.quantity = next;
  updateCartStorage();
});
document.querySelector("#checkout").addEventListener("click", async () => {
  const button = document.querySelector("#checkout");
  const message = document.querySelector("#checkout-message");
  button.disabled = true; message.textContent = "Conferindo disponibilidade…";
  try {
    const response = await fetch("/api/checkout", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ items: state.cart }) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Não foi possível preparar o pedido.");
    const summary = result.items.map(item => `• ${item.name} — ${item.size}, ${item.color} — ${item.quantity}x ${money(item.lineTotal)}`).join("\n");
    const text = `Olá! Quero conversar sobre este pedido da Estrela Concept:\n\n${summary}\n\nSubtotal: ${money(result.total)}\n\nPedido de demonstração, sem pagamento pelo site.`;
    message.textContent = "Pedido pronto. Você pode continuar pelo WhatsApp ou fechar esta janela.";
    const link = document.querySelector("#whatsapp-order-link");
    link.href = whatsappUrl(text);
    link.hidden = false;
  } catch (error) { message.textContent = error.message; }
  finally { button.disabled = false; }
});
document.querySelector("#contact-link").href = whatsappUrl("Olá! Vim pelo site da Estrela Concept e gostaria de tirar uma dúvida.");

async function start() {
  try {
    const response = await fetch("/api/products");
    if (!response.ok) throw new Error("Não foi possível carregar a coleção.");
    state.products = (await response.json()).products;
    const categories = [...new Set(state.products.map(product => product.category))];
    document.querySelector("#category").innerHTML += categories.map(category => `<option value="${escapeHTML(category)}">${escapeHTML(category)}</option>`).join("");
    renderProducts(); renderCart();
    const productId = new URLSearchParams(location.search).get("produto");
    if (productId) openProduct(productId);
  } catch (error) {
    document.querySelector("#result-count").textContent = error.message;
    document.querySelector("#empty-state").hidden = false;
  }
}
start();
