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
