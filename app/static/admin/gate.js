(function () {
  const STORAGE_KEY = "offercare_admin_key";

  const gate = document.getElementById("gate");
  const app = document.getElementById("app");
  const input = document.getElementById("api-key-input");
  const btn = document.getElementById("connect-btn");
  const err = document.getElementById("gate-error");
  const showToggle = document.getElementById("show-key-toggle");
  const status = document.getElementById("gate-status");

  if (!gate || !app || !input || !btn || !err) {
    console.error("VettedMe admin gate: missing DOM nodes");
    return;
  }

  function getKey() {
    return localStorage.getItem(STORAGE_KEY) || "";
  }

  function setKey(value) {
    if (value) localStorage.setItem(STORAGE_KEY, value);
    else localStorage.removeItem(STORAGE_KEY);
  }

  window.offercareAdminGetKey = getKey;
  window.offercareAdminSetKey = setKey;

  async function checkApi() {
    if (!status) return;
    status.textContent = "Checking API…";
    status.className = "muted gate-status";
    try {
      const response = await fetch("/health/vettedme", { cache: "no-store" });
      if (!response.ok) throw new Error("health check failed");
      status.textContent = "API is running — paste your key and click Connect.";
      status.className = "muted gate-status ok";
    } catch {
      status.textContent =
        "API is not running. Double-click VettedMe Admin on your desktop, or run start-all.bat.";
      status.className = "muted gate-status fail";
    }
  }

  async function connect() {
    const key = input.value.trim();
    if (!key) {
      err.textContent = "Admin API key is required.";
      err.classList.remove("hidden");
      return;
    }

    const label = btn.textContent;
    btn.disabled = true;
    btn.textContent = "Connecting…";
    err.classList.add("hidden");
    setKey(key);

    try {
      const response = await fetch("/api/clinicians/pending", {
        headers: { "X-Admin-Key": key },
      });
      const text = await response.text();
      if (!response.ok) {
        let detail = text;
        try {
          const data = JSON.parse(text);
          detail = data.detail || text;
        } catch {
          /* keep raw text */
        }
        throw new Error(typeof detail === "string" ? detail : "Connection failed");
      }

      gate.classList.add("hidden");
      app.classList.remove("hidden");
      window.dispatchEvent(new CustomEvent("offercare-admin-connected"));
    } catch (error) {
      const message = String(error?.message || error || "unknown error");
      if (message.includes("admin_unauthorized")) {
        setKey("");
        err.textContent =
          "Connection failed: admin key rejected. Copy ADMIN_API_KEY from .env exactly, restart start-api.bat, then try again.";
      } else if (message.includes("Failed to fetch") || message.includes("NetworkError")) {
        err.textContent =
          "Connection failed: cannot reach the API. Start start-api.bat, then open http://127.0.0.1:8000/admin";
      } else {
        err.textContent = `Connection failed: ${message}`;
      }
      err.classList.remove("hidden");
      gate.classList.remove("hidden");
      app.classList.add("hidden");
    } finally {
      btn.disabled = false;
      btn.textContent = label;
    }
  }

  function disconnect() {
    setKey("");
    app.classList.add("hidden");
    gate.classList.remove("hidden");
    input.value = "";
    err.classList.add("hidden");
  }

  window.offercareAdminConnect = connect;
  window.offercareAdminDisconnect = disconnect;

  btn.addEventListener("click", connect);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") connect();
  });
  showToggle?.addEventListener("change", (event) => {
    input.type = event.target.checked ? "text" : "password";
  });

  checkApi();

  const saved = getKey();
  if (saved) {
    input.value = saved;
    connect();
  }
})();
