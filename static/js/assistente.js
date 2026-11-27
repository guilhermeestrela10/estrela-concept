const form = document.querySelector("#assistant-form");
const question = document.querySelector("#assistant-question");
const submit = document.querySelector("#assistant-submit");
const status = document.querySelector("#assistant-status");
const messages = document.querySelector("#assistant-messages");

function addMessage(text, role, sources = []) {
  const message = document.createElement("div");
  message.className = `assistant-message${role === "user" ? " user" : ""}`;
  message.textContent = text;
  if (sources.length) {
    const references = document.createElement("small");
    references.textContent = `Informações consultadas: ${sources.join(" · ")}`;
    message.append(references);
  }
  messages.append(message);
  message.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

fetch("/api/status").then(response => response.json()).then(result => {
  if (result.assistantConfigured === true) {
    status.textContent = "Atendimento disponível. As respostas são baseadas nas informações públicas da loja.";
    return;
  }
  if (result.assistantFAQAvailable === true) {
    status.textContent = "Perguntas rápidas sobre catálogo, entrega e peças com defeito estão disponíveis. Para outras dúvidas, fale com a equipe pelo WhatsApp.";
    return;
  }
  status.textContent = "O atendimento assistido está sendo preparado. Enquanto isso, nossa equipe atende pelo WhatsApp.";
  status.classList.add("error");
  question.disabled = true;
  submit.disabled = true;
}).catch(() => {
  status.textContent = "Não foi possível verificar o atendimento agora. Fale com a equipe pelo WhatsApp.";
  status.classList.add("error");
  question.disabled = true;
  submit.disabled = true;
});

document.querySelectorAll(".assistant-suggestions button").forEach(button => {
  button.addEventListener("click", () => {
    if (question.disabled || submit.disabled) return;
    question.value = button.textContent;
    form.requestSubmit();
  });
});

form.addEventListener("submit", async event => {
  event.preventDefault();
  const prompt = question.value.trim();
  if (!prompt || prompt.length > 500 || submit.disabled) return;
  addMessage(prompt, "user");
  question.value = "";
  question.disabled = true;
  submit.disabled = true;
  status.classList.remove("error");
  status.textContent = "Consultando as informações da loja…";
  try {
    const response = await fetch("/api/assistant/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: prompt }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Não foi possível responder agora.");
    addMessage(result.answer, "assistant", Array.isArray(result.sources) ? result.sources : []);
    status.textContent = "Resposta baseada no catálogo e nas informações públicas da loja.";
  } catch (error) {
    addMessage(error.message || "Não foi possível responder agora. Fale com a equipe pelo WhatsApp.", "assistant");
    status.textContent = "Se precisar de confirmação, nossa equipe atende pelo WhatsApp.";
  } finally {
    question.disabled = false;
    submit.disabled = false;
    question.focus();
  }
});
