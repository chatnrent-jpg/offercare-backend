/**
 * VettedCare clinician portal authentication (email, Google, Facebook, demo).
 * Loaded before app.js — exposes token helpers and wires the sign-in gate.
 */
(function portalAuthModule() {
  const STORAGE_KEY = "vettedcare_clinician_token";

  function getToken() {
    return localStorage.getItem(STORAGE_KEY) || "";
  }

  function setToken(value) {
    if (value) localStorage.setItem(STORAGE_KEY, value);
    else localStorage.removeItem(STORAGE_KEY);
  }

  function apiBaseUrl() {
    if (window.location.protocol === "http:" || window.location.protocol === "https:") {
      return window.location.origin;
    }
    const meta = document.querySelector('meta[name="portal-api-base"]');
    if (meta?.content?.trim()) return meta.content.trim().replace(/\/$/, "");
    return "http://127.0.0.1:8000";
  }

  function absoluteApiUrl(path) {
    const normalized = String(path || "").startsWith("/") ? path : `/${path}`;
    return new URL(normalized, `${apiBaseUrl()}/`).href;
  }

  function gateErrorEl() {
    return document.getElementById("gate-error");
  }

  function showGateError(message) {
    const el = gateErrorEl();
    if (!el) return;
    if (!message) {
      el.textContent = "";
      el.classList.add("hidden");
      return;
    }
    el.textContent = message;
    el.classList.remove("hidden");
  }

  function clearAuthQueryParams() {
    const url = new URL(window.location.href);
    let changed = false;
    for (const key of ["token", "auth_error", "auth_message"]) {
      if (url.searchParams.has(key)) {
        url.searchParams.delete(key);
        changed = true;
      }
    }
    if (changed) {
      const suffix = url.search ? url.search : "";
      window.history.replaceState({}, "", `${url.pathname}${suffix}`);
    }
  }

  function consumeOAuthReturn() {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    if (token) {
      setToken(token);
      clearAuthQueryParams();
      return true;
    }
    const authError = params.get("auth_error");
    if (authError) {
      const message = params.get("auth_message") || authError.replaceAll("_", " ");
      showGateError(message);
      clearAuthQueryParams();
    }
    return false;
  }

  function loginErrorMessage(detail) {
    const msg = String(detail || "");
    if (msg === "demo_email_requires_local_part") {
      return "Enter the full demo email (not just @offercare.demo).";
    }
    if (msg === "demo_clinician_not_seeded") {
      return "Demo clinician missing — tap “Use demo account” or ask admin to run demo setup.";
    }
    if (msg === "invalid_credentials") {
      return "Wrong email or password.";
    }
    if (msg === "oauth_account_not_found") {
      return "No clinician account matches that social email. Apply first, then sign in with the same email.";
    }
    return msg || "Sign in failed.";
  }

  const DEMO_EMAIL = "nj.snf.cna.a@offercare.demo";
  const DEMO_PASSWORD = "SecretPass1";

  async function postLogin(path, body, fallback) {
    let response = await fetch(absoluteApiUrl(path), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    if (response.status === 404 && fallback?.path) {
      response = await fetch(absoluteApiUrl(fallback.path), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(fallback.body ?? body),
        cache: "no-store",
      });
    }
    const text = await response.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = null;
    }
    if (!response.ok) {
      const detail = data?.detail || response.statusText;
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data;
  }

  async function loginWithPassword(email, password) {
    return postLogin(
      "/api/portal/auth/login",
      { email, password },
      { path: "/api/clinicians/login", body: { email, password } },
    );
  }

  async function loginWithDemo() {
    return postLogin(
      "/api/portal/auth/demo-login",
      {},
      { path: "/api/clinicians/login", body: { email: DEMO_EMAIL, password: DEMO_PASSWORD } },
    );
  }

  async function loadAuthProviders() {
    try {
      const response = await fetch(absoluteApiUrl("/api/portal/auth/providers"), { cache: "no-store" });
      if (!response.ok) return { google: false, facebook: false, demo: true, api_base: apiBaseUrl() };
      const data = await response.json();
      if (data.api_base) {
        const meta = document.querySelector('meta[name="portal-api-base"]');
        if (meta) meta.setAttribute("content", data.api_base);
      }
      return data;
    } catch {
      return { google: false, facebook: false, demo: true, api_base: apiBaseUrl() };
    }
  }

  function bindSocialButtons(providers) {
    const base = String(providers.api_base || apiBaseUrl()).replace(/\/$/, "");
    const row = document.getElementById("social-auth-row");
    const googleBtn = document.getElementById("google-login-btn");
    const facebookBtn = document.getElementById("facebook-login-btn");
    const oauthHint = document.getElementById("oauth-hint");
    const demoBtn = document.getElementById("demo-login-btn");
    const showSocial = Boolean(providers.google || providers.facebook);

    if (row) row.classList.toggle("hidden", !showSocial);
    if (oauthHint) oauthHint.classList.toggle("hidden", !showSocial);
    if (googleBtn) {
      googleBtn.classList.toggle("hidden", !providers.google);
      googleBtn.onclick = () => {
        window.location.href = `${base}/api/portal/auth/google/start`;
      };
    }
    if (facebookBtn) {
      facebookBtn.classList.toggle("hidden", !providers.facebook);
      facebookBtn.onclick = () => {
        window.location.href = `${base}/api/portal/auth/facebook/start`;
      };
    }
    if (demoBtn) {
      demoBtn.classList.toggle("hidden", providers.demo === false);
    }
  }

  async function setup(onAuthenticated) {
    consumeOAuthReturn();
    const providers = await loadAuthProviders();
    bindSocialButtons(providers);

    const loginForm = document.getElementById("login-form");
    if (loginForm && !loginForm.dataset.authBound) {
      loginForm.dataset.authBound = "1";
      loginForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        showGateError("");
        const email = document.getElementById("login-email")?.value?.trim() || "";
        const password = document.getElementById("login-password")?.value || "";
        try {
          const data = await loginWithPassword(email, password);
          setToken(data.access_token);
          if (typeof onAuthenticated === "function") await onAuthenticated(data);
        } catch (error) {
          showGateError(loginErrorMessage(error.message));
        }
      });
    }

    const demoBtn = document.getElementById("demo-login-btn");
    if (demoBtn && !demoBtn.dataset.authBound) {
      demoBtn.dataset.authBound = "1";
      demoBtn.addEventListener("click", async () => {
        showGateError("");
        const emailInput = document.getElementById("login-email");
        const passwordInput = document.getElementById("login-password");
        if (emailInput) emailInput.value = "nj.snf.cna.a@offercare.demo";
        if (passwordInput) passwordInput.value = "SecretPass1";
        try {
          const data = await loginWithDemo();
          setToken(data.access_token);
          if (typeof onAuthenticated === "function") await onAuthenticated(data);
        } catch (error) {
          showGateError(loginErrorMessage(error.message));
        }
      });
    }

    if (getToken() && typeof onAuthenticated === "function") {
      await onAuthenticated(null);
    }
  }

  window.PortalAuth = {
    getToken,
    setToken,
    setup,
    showGateError,
    loginErrorMessage,
  };
})();
