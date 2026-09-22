#!/usr/bin/env python3
"""Extract content from index.html, encrypt with AES-GCM + PBKDF2."""
import base64
import json
import os
import re
import sys
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PASSWORD = b"Alireza123"
ITERATIONS = 600000

html_path = sys.argv[1] if len(sys.argv) > 1 else "index.html"
output_path = sys.argv[2] if len(sys.argv) > 2 else "index.html"

with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# Extract everything inside <main ...> ... </main>
m = re.search(r'<main[^>]*>(.*?)</main>', html, re.DOTALL)
if not m:
    raise SystemExit("Could not find <main>")

main_html = m.group(1).strip()

# Encrypt
salt = os.urandom(16)
nonce = os.urandom(12)
kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITERATIONS)
key = kdf.derive(PASSWORD)
aesgcm = AESGCM(key)
ct = aesgcm.encrypt(nonce, main_html.encode("utf-8"), None)

# Encode as base64
blob_b64 = base64.b64encode(salt + nonce + ct).decode()

# Build the new HTML
new_html = html
# Replace main content with gate (preserve inner div structure)
new_html = re.sub(
    r'<main[^>]*>.*?</main>',
    '<main class="main" id="content-container"></main>',
    new_html,
    flags=re.DOTALL,
)

# Add noindex meta
new_html = new_html.replace(
    "<title>", '<meta name="robots" content="noindex, nofollow">\n<title>'
)

# Add gate CSS before the closing </style>
gate_css = """
/* ─── Gate ─── */
.gate-overlay {
  position: fixed; inset: 0; z-index: 9999;
  background: var(--bg-page, #0d0a08);
  display: flex; align-items: center; justify-content: center;
}
.gate-box {
  text-align: center; max-width: 380px; width: 90%;
  padding: 3rem 2rem;
}
.gate-icon { font-size: 2.5rem; margin-bottom: 1rem; }
.gate-title {
  font-size: var(--fs-xl, 1.75rem); font-weight: 800;
  color: var(--text-gold, #c7a45b); margin: 0;
}
.gate-sub {
  font-size: var(--fs-sm, 0.8125rem); color: var(--text-tertiary, #5c5248);
  margin: 0.25rem 0 1.5rem;
}
.gate-hint {
  font-size: var(--fs-sm, 0.8125rem); color: var(--text-secondary, #b8aea4);
  margin-bottom: 1rem;
}
.gate-input {
  width: 100%; padding: 0.8rem 1rem; border-radius: 10px;
  border: 1px solid var(--border-med, rgba(255,255,255,0.07));
  background: var(--bg-card, #1c1712); color: var(--text-primary, #f0ebe6);
  font: inherit; font-size: 1rem; text-align: center;
  outline: none; transition: border-color 0.2s;
}
.gate-input:focus { border-color: var(--gold-400, #c7a45b); }
.gate-error {
  color: #e57373; font-size: var(--fs-sm, 0.8125rem); margin: 0.5rem 0;
}
.gate-btn {
  margin-top: 1rem; width: 100%; padding: 0.8rem;
  border: none; border-radius: 10px;
  background: var(--gold-400, #c7a45b); color: var(--clay-900, #0d0a08);
  font: inherit; font-size: 1rem; font-weight: 700; cursor: pointer;
  transition: opacity 0.2s;
}
.gate-btn:hover { opacity: 0.9; }
.gate-btn:disabled { opacity: 0.5; cursor: not-allowed; }
"""
new_html = new_html.replace("</style>", gate_css + "\n</style>")

# Add encrypted blob + gate + decryption script before </body>
gate_script = f"""
<!-- encrypted content gate -->
<script>
const ENCRYPTED_BLOB = "{blob_b64}";
const PBKDF2_ITERATIONS = {ITERATIONS};
</script>
<script>
(function(){{
// ─── Password Gate ───
const STORAGE_KEY = "sz_playbook_auth";

function base64ToBytes(b64) {{
    const bin = atob(b64);
    const u8 = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
    return u8;
}}

async function deriveKey(password, salt) {{
    const enc = new TextEncoder();
    const keyMaterial = await crypto.subtle.importKey(
        "raw", enc.encode(password), {{ name: "PBKDF2" }}, false, ["deriveKey"]
    );
    return crypto.subtle.deriveKey(
        {{ name: "PBKDF2", salt, iterations: PBKDF2_ITERATIONS, hash: "SHA-256" }},
        keyMaterial,
        {{ name: "AES-GCM", length: 256 }},
        false,
        ["decrypt"]
    );
}}

async function decryptContent(password) {{
    try {{
        const raw = base64ToBytes(ENCRYPTED_BLOB);
        const salt = raw.slice(0, 16);
        const nonce = raw.slice(16, 28);
        const ct = raw.slice(28);
        const key = await deriveKey(password, salt);
        const plain = await crypto.subtle.decrypt(
            {{ name: "AES-GCM", iv: nonce }}, key, ct
        );
        return new TextDecoder().decode(plain);
    }} catch {{ return null; }}
}}

async function unlock(password) {{
    const content = await decryptContent(password);
    if (!content) return false;
    sessionStorage.setItem(STORAGE_KEY, "1");
    renderContent(content);
    return true;
}}

function renderContent(html) {{
    const container = document.getElementById("content-container");
    container.innerHTML = html;
    document.getElementById("gate-screen").style.display = "none";
    container.style.display = "block";
    // Re-init scroll spy and progress
    if (window.initPostRender) window.initPostRender();
}}

// ─── Gate UI ───
function showGate() {{
    const container = document.getElementById("content-container");
    container.style.display = "none";
    const gate = document.createElement("div");
    gate.id = "gate-screen";
    gate.innerHTML = `
    <div class="gate-overlay">
      <div class="gate-box">
        <div class="gate-icon">🔐</div>
        <h1 class="gate-title">سرزمین</h1>
        <p class="gate-sub">۳D Production Playbook</p>
        <p class="gate-hint">این صفحه خصوصی است. رمز عبور را وارد کنید.</p>
        <input type="password" id="gate-password"
               placeholder="رمز عبور" autocomplete="off"
               class="gate-input">
        <p class="gate-error" id="gate-error" style="display:none">رمز اشتباه است.</p>
        <button class="gate-btn" id="gate-btn">ورود</button>
      </div>
    </div>`;
    document.body.insertBefore(gate, document.body.firstChild);

    const input = document.getElementById("gate-password");
    const btn = document.getElementById("gate-btn");
    const err = document.getElementById("gate-error");

    async function attempt() {{
        err.style.display = "none";
        btn.disabled = true;
        btn.textContent = "در حال بررسی…";
        const ok = await unlock(input.value);
        if (!ok) {{
            err.style.display = "block";
            btn.disabled = false;
            btn.textContent = "ورود";
            input.value = "";
            input.focus();
        }}
    }}

    btn.addEventListener("click", attempt);
    input.addEventListener("keydown", e => {{ if (e.key === "Enter") attempt(); }});
    input.focus();
}}

// ─── Bootstrap ───
(async function() {{
    // If already authed this session, try silent decrypt
    if (sessionStorage.getItem(STORAGE_KEY)) {{
        const pwd = prompt("🔐 رمز عبور:");
        if (pwd && await unlock(pwd)) return;
        sessionStorage.removeItem(STORAGE_KEY);
    }}
    showGate();
}})();
</script>
"""
new_html = new_html.replace("</body>", gate_script + "\n</body>")

with open(output_path, "w", encoding="utf-8") as f:
    f.write(new_html)

print(f"✅ Encrypted and written to {output_path}")
print(f"   Blob size: {len(blob_b64)} bytes base64")