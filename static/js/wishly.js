// Small enhancements only – every page works without JavaScript.

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-copy]");
  if (!button) return;
  const input = document.querySelector(button.dataset.copy);
  input.select();
  navigator.clipboard?.writeText(input.value).then(() => {
    const label = button.textContent;
    button.textContent = "Kopiert ✓";
    setTimeout(() => { button.textContent = label; }, 1500);
  });
});

// Confirmation for one of several buttons in a form
document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-confirm-click]");
  if (button && !window.confirm(button.dataset.confirmClick)) event.preventDefault();
});

document.addEventListener("submit", (event) => {
  const message = event.target.dataset.confirm;
  if (message && !window.confirm(message)) event.preventDefault();
});

// Reload once product data fetched in the background has arrived
const pending = [...document.querySelectorAll("[data-status-url]")];
if (pending.length) {
  let tries = 0;
  const poll = async () => {
    tries += 1;
    for (const element of pending) {
      try {
        const response = await fetch(element.dataset.statusUrl, { headers: { Accept: "application/json" } });
        const { status } = await response.json();
        if (status !== "pending") {
          window.location.reload();
          return;
        }
      } catch {
        return;
      }
    }
    if (tries < 20) setTimeout(poll, 2000 + tries * 500);
  };
  setTimeout(poll, 1500);
}

// Product forms: fill empty fields from the shop link as soon as one is entered
for (const form of document.querySelectorAll("form[data-link-preview]")) {
  const urlInput = form.elements.shop_url;
  if (!urlInput) continue;
  const fields = ["title", "description", "image_url", "price", "currency"];
  const status = document.createElement("div");
  status.className = "link-preview";
  status.setAttribute("aria-live", "polite");
  urlInput.after(status);
  let lastUrl = urlInput.value.trim();

  const show = (text, image) => {
    status.replaceChildren();
    if (image) {
      const img = document.createElement("img");
      img.src = image;
      img.alt = "";
      img.referrerPolicy = "no-referrer";
      status.append(img);
    }
    const p = document.createElement("span");
    p.textContent = text;
    status.append(p);
  };

  const preview = async () => {
    const url = urlInput.value.trim();
    if (!/^https?:\/\/\S+\.\S+/.test(url) || url === lastUrl) return;
    lastUrl = url;
    show("Hole Angaben aus dem Link …");
    status.classList.add("loading");
    try {
      const response = await fetch(`${form.dataset.linkPreview}?url=${encodeURIComponent(url)}`, {
        headers: { Accept: "application/json" },
      });
      const data = await response.json();
      if (url !== urlInput.value.trim()) return;
      if (data.error) {
        show(`${data.error} Du kannst die Angaben selbst eintragen.`);
        return;
      }
      const found = [];
      for (const name of fields) {
        const input = form.elements[name];
        // Replace what an earlier link filled in, never what the user typed
        if (!input || !data[name] || (input.value && !input.dataset.autofilled && name !== "currency")) continue;
        input.value = data[name];
        input.dataset.autofilled = "1";
        found.push(name);
      }
      const labels = { title: "Name", image_url: "Bild", price: "Preis", description: "Beschreibung" };
      const names = found.map((n) => labels[n]).filter(Boolean);
      show(names.length ? `Übernommen: ${names.join(", ")}${data.title ? ` – „${data.title}“` : ""}`
                        : "Keine Angaben gefunden – trag sie gern selbst ein.", data.image_url);
    } catch {
      show("Der Link konnte gerade nicht geprüft werden – beim Speichern versuchen wir es noch einmal.");
    } finally {
      status.classList.remove("loading");
    }
  };

  for (const name of fields) {
    form.elements[name]?.addEventListener("input", (event) => { delete event.target.dataset.autofilled; });
  }
  urlInput.addEventListener("change", preview);
  urlInput.addEventListener("paste", () => setTimeout(preview, 0));
}
