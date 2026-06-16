// --- App Configuration ---
// RPS-velden (foto, telefoon, functie) worden door de Rijksprofielservice beheerd.
// Naam en e-mail komen uit de Rijks-SSO en hoeven apps niet aan de gebruiker te vragen.
const APP_CONFIG = {
  wies: {
    name: "Wies",
    color: "#00796b",
    description: "Wies gebruikt je profielfoto, telefoonnummer en functie om je vindbaar te maken voor collega's.",
    requestedFields: ["avatar", "phone", "jobTitle"],
    fieldLabels: { avatar: "Profielfoto", phone: "Telefoonnummer", jobTitle: "Functie" },
  },
  amt: {
    name: "AMT",
    color: "#6a1b9a",
    description: "AMT gebruikt je profielfoto om te tonen wie aan een algoritmeregistratie werkt.",
    requestedFields: ["avatar"],
    fieldLabels: { avatar: "Profielfoto" },
  },
};

const FIELD_LABELS = {
  firstName: "Voornaam",
  lastName: "Achternaam",
  avatar: "Profielfoto",
  email: "E-mailadres",
  phone: "Telefoonnummer",
  jobTitle: "Functie",
};

// --- SSO accounts (simuleren rijks-SSO; naam + email komen hier vandaan) ---
const SSO_ACCOUNTS = {
  matthijs: { id: "matthijs", firstName: "Matthijs", lastName: "Beekman",     email: "matthijs.beekman@rijksoverheid.nl"     },
  ruben:    { id: "ruben",    firstName: "Ruben",    lastName: "Rouwhof",     email: "ruben.rouwhof@rijksoverheid.nl"        },
  robbert:  { id: "robbert",  firstName: "Robbert",  lastName: "Uittenbroek", email: "robbert.uittenbroek@rijksoverheid.nl"  },
};

function getSsoIdentity() {
  const id = localStorage.getItem("sso_identity");
  return id && SSO_ACCOUNTS[id] ? SSO_ACCOUNTS[id] : null;
}

function setSsoIdentity(accountId) {
  if (!SSO_ACCOUNTS[accountId]) return;
  localStorage.setItem("sso_identity", accountId);
}

function clearSsoIdentity() {
  localStorage.removeItem("sso_identity");
}

// --- Profile (RPS-beheerde velden: avatar, phone, jobTitle) ---
// Opgeslagen per SSO-account zodat verschillende accounts verschillende profielen hebben.
function getProfile() {
  const sso = getSsoIdentity();
  if (!sso) return null;
  const raw = localStorage.getItem("rps_profile_" + sso.id);
  return raw ? JSON.parse(raw) : {};
}

function setProfile(data) {
  const sso = getSsoIdentity();
  if (!sso) return;
  localStorage.setItem("rps_profile_" + sso.id, JSON.stringify(data));
}

// Combineer SSO-identity met RPS-profiel tot één gegevensbundel.
function getFullProfile() {
  const sso = getSsoIdentity();
  if (!sso) return null;
  const rps = getProfile() || {};
  return { ...sso, ...rps };
}

// --- Consents (per SSO-account) ---
function consentsKey() {
  const sso = getSsoIdentity();
  return sso ? "rps_consents_" + sso.id : null;
}

function getConsents() {
  const key = consentsKey();
  if (!key) return {};
  const raw = localStorage.getItem(key);
  return raw ? JSON.parse(raw) : {};
}

function setConsents(data) {
  const key = consentsKey();
  if (!key) return;
  localStorage.setItem(key, JSON.stringify(data));
}

function grantConsent(appId, fields) {
  const consents = getConsents();
  consents[appId] = {
    granted: true,
    fields: fields,
    grantedAt: new Date().toISOString(),
  };
  setConsents(consents);
}

function revokeConsent(appId) {
  const consents = getConsents();
  delete consents[appId];
  setConsents(consents);
}

function hasConsent(appId) {
  const consents = getConsents();
  return consents[appId]?.granted === true;
}

// Voor consumerende apps: SSO-velden (naam + email) zijn altijd beschikbaar zodra ingelogd.
// RPS-velden (avatar/phone/jobTitle) alleen na consent.
function getProfileForApp(appId) {
  const sso = getSsoIdentity();
  if (!sso) return null;
  const result = { firstName: sso.firstName, lastName: sso.lastName, email: sso.email };
  if (!hasConsent(appId)) return result;
  const profile = getProfile() || {};
  const allowedFields = getConsents()[appId].fields;
  for (const field of allowedFields) {
    if (profile[field] !== undefined) {
      result[field] = profile[field];
    }
  }
  return result;
}

// --- Avatar helpers ---
function getInitials(firstName, lastName) {
  const f = (firstName || "").trim();
  const l = (lastName || "").trim();
  return ((f[0] || "") + (l[0] || "")).toUpperCase();
}

function renderAvatar(container, profile, size = 80) {
  container.innerHTML = "";
  container.style.width = size + "px";
  container.style.height = size + "px";
  container.style.borderRadius = "50%";
  container.style.overflow = "hidden";
  container.style.display = "flex";
  container.style.alignItems = "center";
  container.style.justifyContent = "center";
  container.style.fontSize = size * 0.38 + "px";
  container.style.fontWeight = "600";
  container.style.flexShrink = "0";

  if (profile?.avatar) {
    const img = document.createElement("img");
    img.src = profile.avatar;
    img.style.width = "100%";
    img.style.height = "100%";
    img.style.objectFit = "cover";
    container.appendChild(img);
  } else {
    container.style.backgroundColor = "#c2d1df";
    container.style.color = "#154273";
    container.textContent = getInitials(
      profile?.firstName,
      profile?.lastName
    );
  }
}

function resizeImage(file, maxDim = 200) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement("canvas");
        let w = img.width,
          h = img.height;
        if (w > h) {
          if (w > maxDim) { h = (h * maxDim) / w; w = maxDim; }
        } else {
          if (h > maxDim) { w = (w * maxDim) / h; h = maxDim; }
        }
        canvas.width = w;
        canvas.height = h;
        canvas.getContext("2d").drawImage(img, 0, 0, w, h);
        resolve(canvas.toDataURL("image/jpeg", 0.7));
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  });
}

// --- SSO account picker overlay ---
// Toont een "Rijks-SSO"-overlay waarin de gebruiker een nep-account kiest.
// Roept onPick(accountId) aan na keuze. Self-contained: gebruikt eigen DOM, geen CSS-koppeling buiten shared.css.
function showSsoPicker(onPick) {
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.innerHTML =
    '<div class="modal">' +
      '<h2>Inloggen met Rijks-SSO</h2>' +
      '<p>Kies een account om in te loggen.</p>' +
      '<div class="sso-account-list" id="ssoAccountList"></div>' +
      '<div class="modal-actions"><button class="btn btn-secondary" id="ssoCancel">Annuleren</button></div>' +
    '</div>';
  document.body.appendChild(overlay);

  const list = overlay.querySelector("#ssoAccountList");
  for (const id of Object.keys(SSO_ACCOUNTS)) {
    const acc = SSO_ACCOUNTS[id];
    const btn = document.createElement("button");
    btn.className = "sso-account-row";
    btn.innerHTML =
      '<div class="sso-account-avatar">' + getInitials(acc.firstName, acc.lastName) + '</div>' +
      '<div class="sso-account-text">' +
        '<div class="sso-account-name">' + acc.firstName + ' ' + acc.lastName + '</div>' +
        '<div class="sso-account-email">' + acc.email + '</div>' +
      '</div>';
    btn.addEventListener("click", () => {
      overlay.remove();
      onPick(id);
    });
    list.appendChild(btn);
  }

  overlay.querySelector("#ssoCancel").addEventListener("click", () => overlay.remove());
}

// --- Transition screen ---
function showTransition(message, targetUrl, delay = 1500) {
  const overlay = document.createElement("div");
  overlay.className = "transition-overlay";
  overlay.innerHTML =
    '<div class="transition-content">' +
      '<div class="transition-spinner"></div>' +
      '<div class="transition-message">' + message + '</div>' +
    '</div>';
  document.body.appendChild(overlay);
  setTimeout(() => { window.location.href = targetUrl; }, delay);
}

// --- URL helpers ---
function getUrlParam(key) {
  return new URLSearchParams(window.location.search).get(key);
}

function clearUrlParams() {
  history.replaceState(null, "", window.location.pathname);
}
