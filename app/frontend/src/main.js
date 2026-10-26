import Keycloak from "keycloak-js";
import { mountRequests } from "./requests.js";
import "./style.css";

const keycloak = new Keycloak({
  url: "http://localhost:8080",
  realm: "homelab",
  clientId: "promotion-web",
});

const redirectUri = `${window.location.origin}/`;
const status = document.querySelector("#status");
const loginButton = document.querySelector("#login");
const logoutButton = document.querySelector("#logout");
const identity = document.querySelector("#identity");

loginButton.addEventListener("click", async () => {
  loginButton.disabled = true;
  try {
    await keycloak.login({ redirectUri });
  } catch {
    status.textContent = "Unable to start sign-in. Please try again.";
    loginButton.disabled = false;
  }
});

logoutButton.addEventListener("click", async () => {
  logoutButton.disabled = true;
  try {
    await keycloak.logout({ redirectUri });
  } catch {
    status.textContent = "Unable to sign out. Please try again.";
    logoutButton.disabled = false;
  }
});

async function apiRequest(path, { method = "GET", body } = {}) {
  try {
    await keycloak.updateToken(30);
  } catch {
    throw new Error("Session expired. Please sign out and sign in again.");
  }

  let response;
  try {
    response = await fetch(path, {
      method,
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${keycloak.token}`,
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      cache: "no-store",
    });
  } catch {
    throw new Error("Unable to reach the API.");
  }

  if (!response.ok) {
    const messages = {
      401: "Session rejected. Please sign out and sign in again.",
      403: "You do not have permission to perform this action.",
      404: "Promotion request not found.",
      409: "This request already has a decision. Reopen it to refresh.",
      422: "Invalid input. Check the repository, digest and decision.",
      503: "Service temporarily unavailable.",
    };
    throw new Error(
      messages[response.status] ?? `API request failed (${response.status}).`,
    );
  }

  try {
    return await response.json();
  } catch {
    throw new Error("The API returned an invalid response.");
  }
}

async function loadIdentity() {
  try {
    await keycloak.updateToken(30);
  } catch {
    status.textContent = "Session expired. Please sign in again.";
    loginButton.hidden = false;
    loginButton.disabled = false;
    return;
  }

  const response = await fetch("/me", {
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${keycloak.token}`,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const messages = {
      401: "The API rejected the session. Please sign in again.",
      403: "Access denied.",
      503: "The authentication service is temporarily unavailable.",
    };
    status.textContent =
      messages[response.status] ?? `API request failed (${response.status}).`;

    if (response.status === 401) {
      loginButton.hidden = false;
      loginButton.disabled = false;
    }
    return;
  }

  const actor = await response.json();
  document.querySelector("#subject").textContent = actor.subject;
  document.querySelector("#roles").textContent =
    actor.roles.join(", ") || "No application roles";
  identity.hidden = false;
  status.textContent = "Signed in. Identity verified by the API.";

  await mountRequests(apiRequest, actor);
}

async function start() {
  let authenticated;
  try {
    authenticated = await keycloak.init({
      onLoad: "check-sso",
      pkceMethod: "S256",
      checkLoginIframe: false,
      redirectUri,
    });
  } catch {
    status.textContent =
      "Authentication initialization failed. Reload the page to retry.";
    return;
  }

  loginButton.hidden = authenticated;
  loginButton.disabled = false;
  logoutButton.hidden = !authenticated;

  if (!authenticated) {
    status.textContent = "Sign in to access promotion requests.";
    return;
  }

  try {
    await loadIdentity();
  } catch {
    status.textContent =
      "Unable to load the API identity. Check that the API is running.";
  }
}

await start();
