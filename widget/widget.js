(function () {
  "use strict";

  const script = document.currentScript;
  const publicId = script?.dataset.widgetId;

  if (!publicId) {
    console.error("FlyRank Widget: Missing data-widget-id.");
    return;
  }

  const apiBase = new URL(script.src).origin;
  const container = document.createElement("div");
  container.id = `flyrank-widget-${publicId}`;
  script.insertAdjacentElement("afterend", container);

  const shadow = container.attachShadow({ mode: "open" });

  shadow.innerHTML = `
    <style>
      * { box-sizing: border-box; }
      .card {
        font-family: Arial, sans-serif;
        max-width: 420px;
        padding: 24px;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        background: #fff;
        color: #111827;
        box-shadow: 0 8px 28px rgba(0,0,0,.08);
      }
      h2 { margin: 0 0 8px; font-size: 21px; }
      .field { margin-top: 15px; }
      label { display: block; margin-bottom: 6px; font-size: 13px; }
      input, textarea {
        width: 100%; padding: 11px; border: 1px solid #d1d5db;
        border-radius: 7px; font: inherit;
      }
      textarea { min-height: 90px; resize: vertical; }
      button {
        width: 100%; margin-top: 18px; padding: 12px;
        border: 0; border-radius: 7px; background: #2563eb;
        color: white; font-weight: 600; cursor: pointer;
      }
      button:disabled { opacity: .6; cursor: wait; }
      .message { margin-top: 12px; font-size: 13px; }
      .error { color: #dc2626; }
      .success { color: #15803d; }
      .trap { position: absolute; left: -10000px; }
    </style>
    <div class="card">
      <h2>Loading form...</h2>
      <div class="message" role="status" aria-live="polite"></div>
    </div>
  `;

  const card = shadow.querySelector(".card");
  const message = shadow.querySelector(".message");

  function showMessage(text, type) {
    message.textContent = text;
    message.className = `message ${type || ""}`;
  }

  async function initialize() {
    try {
      const response = await fetch(
        `${apiBase}/api/public/widgets/${encodeURIComponent(publicId)}/config`,
        { headers: { Accept: "application/json" } }
      );

      if (!response.ok) throw new Error("Widget configuration unavailable.");

      const config = await response.json();
      const settings = config.configuration || {};
      const fields = settings.fields || [];

      card.querySelector("h2").textContent =
        settings.title || config.name || "Contact us";

      const form = document.createElement("form");

      fields.forEach((field) => {
        const wrapper = document.createElement("div");
        wrapper.className = "field";

        const label = document.createElement("label");
        label.textContent = field.label || field.name;
        label.htmlFor = `field-${field.name}`;

        const input = document.createElement(
          field.type === "textarea" ? "textarea" : "input"
        );

        input.id = `field-${field.name}`;
        input.name = field.name;
        input.required = Boolean(field.required);

        if (field.type !== "textarea") {
          input.type = field.type === "email" ? "email" : "text";
        }

        wrapper.append(label, input);
        form.appendChild(wrapper);
      });

      const trap = document.createElement("div");
      trap.className = "trap";
      const honeypot = document.createElement("input");
      honeypot.name = "website";
      honeypot.tabIndex = -1;
      honeypot.autocomplete = "off";
      trap.appendChild(honeypot);
      form.appendChild(trap);

      const button = document.createElement("button");
      button.type = "submit";
      button.textContent = settings.submit_text || "Submit";
      form.appendChild(button);

      card.querySelector("h2").insertAdjacentElement("afterend", form);

      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        button.disabled = true;
        showMessage("Sending...", "");

        const data = Object.fromEntries(new FormData(form).entries());
        if (!data.website) delete data.website;

        try {
          const result = await fetch(
            `${apiBase}/api/public/widgets/${encodeURIComponent(publicId)}/submissions`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                "Idempotency-Key": crypto.randomUUID()
              },
              body: JSON.stringify({ data })
            }
          );

          const body = await result.json();

          if (!result.ok) {
            throw new Error(body.detail || "Submission failed.");
          }

          form.reset();
          showMessage("Your submission was received.", "success");
        } catch (error) {
          showMessage(error.message || "Please try again.", "error");
        } finally {
          button.disabled = false;
        }
      });
    } catch (error) {
      showMessage(error.message || "Unable to load widget.", "error");
    }
  }

  initialize();
})();