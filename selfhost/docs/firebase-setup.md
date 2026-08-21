# Firebase + Google console setup — Omi self-host (`omi-xuanloi`)

> **Who is this for?** You — the owner — clicking through the Firebase and Google Cloud consoles by hand.
> No code, no CLI. Every click, exact label, and URL is listed so you never have to ask "what next".
> Time: ~15 minutes (steps 1–6) + 2 minutes for step 7 after the backend is deployed.
>
> **Branch:** `feat/selfhost-backend` · **Project name:** `omi-xuanloi` · **Region:** `asia-southeast1`

---

## ⚠️ Security — read first

- **NEVER paste secrets into chat, email, GitHub, or any committed file.**
- **NEVER commit** the service-account JSON, `apiKey`, `client_secret`, or any value from the outputs table below.
- Secrets live in **two places only:**
  - On the VPS: `/opt/omi/.env` and `/opt/omi/secrets/firebase-service-account.json` (mode `600`)
  - On your Windows dev machine: `desktop/windows/.env` (this file is git-ignored)
- If you accidentally commit or share a secret, revoke/rotate it immediately (see the "If something leaked" note at the end).
- The outputs table at the end of this guide is for **your private notes** (password manager / local file). Do not check it in.

---

## Before you start

- A Google account that can create Firebase projects (any Gmail works; use the same account you will use for `xuanloi.me` DNS / VPS).
- A browser signed into that account.
- You do **not** need `gcloud` CLI, billing, or any prior Firebase project.

Keep two tabs open:

- **Firebase console:** https://console.firebase.google.com
- **Google Cloud console (same project):** https://console.cloud.google.com

> Tip: after step 1, every Firebase URL in this guide already includes the project id (`omi-xuanloi`). If you see a "Select project" dropdown in the top bar, pick **`omi-xuanloi`**.

---

## Step 1 — Create the Firebase project `omi-xuanloi` (Analytics OFF)

**Direct link:** https://console.firebase.google.com

1. Open https://console.firebase.google.com — you should see your existing Firebase projects (or "Create a project").
2. Click **Add project** (or **Create a project**).
3. In **Enter your project name**, type exactly:

   ```
   omi-xuanloi
   ```

   The helper text under it will show a project ID like `omi-xuanloi` (or `omi-xuanloi-xxxxx` if the name is taken — that is OK, just note what it actually created). **Keep this exact ID** — it becomes your `projectId`.

4. Click **Continue**.
5. **Google Analytics:** you will see a toggle/card **"Enable Google Analytics for this project"**.
   - **Turn it OFF** (toggle to grey / click "Disable").
   - This project does not need Analytics.
6. Click **Create project**. Wait ~20–60 seconds for "Your new project is ready".
7. Click **Continue** (or **Continue to console**).

**Verify:** the top bar / URL now shows `omi-xuanloi` (or the suffixed ID). The URL will be:

```
https://console.firebase.google.com/project/omi-xuanloi/overview
```

(if your ID got a suffix, replace `omi-xuanloi` in all later URLs with that exact ID).

**What to write down now:** `projectId` = the ID you saw (e.g. `omi-xuanloi`). Put it in the outputs table at the end.

---

## Step 2 — Enable Google sign-in (Authentication → Sign-in method → Google)

**Direct link:** https://console.firebase.google.com/project/omi-xuanloi/authentication/providers

> Menu path (if the link doesn't open directly): left sidebar **Build → Authentication** → if you see **Get started**, click it → top tab **Sign-in method**.

1. In the Firebase console for `omi-xuanloi`, open the left sidebar → **Build** → **Authentication**.
   - First time: you will see a **Get started** button. Click **Get started** and confirm.
2. You are now on **Authentication → Sign-in method** (or "Sign-in method" tab). You will see a list of providers: **Email/Password**, **Google**, etc.
3. Find the row **Google** → click it (or click the pencil/edit icon on the Google row).
4. In the Google provider panel:
   - Toggle **Enable** to **on** (blue).
   - **Project support email:** pick your email from the dropdown (required field).
   - Leave **Project public-facing name** as default (or `omi-xuanloi`).
   - Leave the default **email scope** as-is.
5. Click **Save**.
6. Back on the **Sign-in method** list, the **Google** row should now show **Enabled** (green check).

**Verify:** reload the page — **Google → Enabled**, **Status: Enabled**.

> No redirect URI to add here. The app's Google OAuth flow uses the backend's own OAuth client (step 6), not this toggle's client.

---

## Step 3 — Create the Firestore Database (Build → Firestore Database, production mode, region `asia-southeast1`)

**Direct link:** https://console.firebase.google.com/project/omi-xuanloi/firestore

> Menu path: left sidebar **Build → Firestore Database**.

1. In the left sidebar click **Build → Firestore Database**.
2. Click **Create database** (big button in the center).
3. **Secure rules:** choose **Start in production mode** (not test mode). Click **Next**.
4. **Location:**
   - If asked **Firestore location type**, leave **Regional** (or just the location picker).
   - **Location** dropdown → select **`asia-southeast1`** (Singapore — closest to the VPS at `103.116.39.65`).
   - Do not change anything else.
5. Click **Enable** (or **Create**). Wait ~30–90 seconds while Firestore provisions.
6. When done you will see an empty **Firestore Database** page with tabs **Data / Rules / Indexes / Usage**.

**Verify:** **Firestore Database → Data** shows "No documents yet" and the location badge reads `asia-southeast1`.

> Billing: Firestore on the free Spark plan is fine (1 GiB / 50k reads/day). No card needed for this step.

---

## Step 4 — Generate the service-account private key JSON (Project settings → Service accounts → Generate new private key)

**Direct link:** https://console.firebase.google.com/project/omi-xuanloi/settings/serviceaccounts/adminsdk

> Menu path: click the **⚙ (gear) icon** next to **Project Overview** at the top of the left sidebar → **Project settings** → top tab **Service accounts**.

1. Click the **⚙ (gear)** icon in the top-left (next to **Project Overview**) → **Project settings**.
2. Across the top of Project settings, click the **Service accounts** tab.
3. You will see **Firebase Admin SDK** (section title) with a panel showing **Admin SDK configuration snippet** (Node.js / Python / etc.) and a button **Generate new private key**.
   - Service account name will look like `firebase-adminsdk-xxxxx@omi-xuanloi.iam.gserviceaccount.com` — that is correct.
4. Click **Generate new private key**.
5. A confirmation dialog "Generate new private key?" appears — click **Generate key**.
6. Your browser will download a JSON file named like `omi-xuanloi-firebase-adminsdk-xxxxx-xxxxxxxxxx.json`.

**What to do with it:**

- **Do NOT open it in chat. Do NOT email it. Do NOT commit it.** It contains a private key that gives full admin access to your Firebase project.
- Save it somewhere safe on your local machine for now (e.g. `Downloads/`). You will need the filename for the outputs table.
- **Later (Task 4, after the VPS exists):** this file will be copied to the VPS via SCP to:

  ```
  /opt/omi/secrets/firebase-service-account.json
  ```

  with permissions `600` (owner-only read/write). The deploy step will run:

  ```bash
  scp -i ~/.ssh/omi_agent \
    ./omi-xuanloi-firebase-adminsdk-*.json \
    root@103.116.39.65:/opt/omi/secrets/firebase-service-account.json
  ssh -i ~/.ssh/omi_agent root@103.116.39.65 "chmod 600 /opt/omi/secrets/firebase-service-account.json"
  ```

  You do not need to run this now — just keep the file and note its local path. If you lose it, you can return to this same screen and click **Generate new private key** again (the old key stays valid until you delete it in IAM).

**Verify:** the downloaded file is valid JSON and contains fields like `type`, `project_id`, `private_key`, `client_email`.

**What to write down now:** the filename (e.g. `omi-xuanloi-firebase-adminsdk-xxxxx-xxxxxxxxxx.json`) and that its destination is `/opt/omi/secrets/firebase-service-account.json`.

---

## Step 5 — Create the Web app config (Project settings → Your apps → Web app → SDK setup and configuration)

**Direct link:** https://console.firebase.google.com/project/omi-xuanloi/settings/general

> Menu path: **⚙ (gear) → Project settings → General** tab → scroll to **Your apps** section.

1. Still in **Project settings**, click the **General** tab (first tab).
2. Scroll down to the section titled **Your apps**.
3. Click the **Web app** icon: **`</>`** (tooltip: "Web").
   - Alternative label: **Add app → Web** or the `</>` button next to iOS/Android icons.
4. Dialog **Add Firebase to your web app** (or **Create web app**):
   - **App nickname:** type `omi-desktop`
   - **Also set up Firebase Hosting for this app:** leave **unchecked** (do not enable Hosting).
   - Click **Register app** (or **Register**).
5. You will now see **SDK setup and configuration** (or **Add Firebase SDK**) with two tabs: **CDN** and **Config**.
   - Select **Config** (or look for the `firebaseConfig` object).
6. You will see a code block like:

   ```js
   const firebaseConfig = {
     apiKey: "AIzaSy...XXXX",
     authDomain: "omi-xuanloi.firebaseapp.com",
     projectId: "omi-xuanloi",
     storageBucket: "omi-xuanloi.firebasestorage.app",
     messagingSenderId: "1234567890",
     appId: "1:1234567890:web:abcdef123456",
     measurementId: "G-XXXX"
   };
   ```

7. **Copy exactly these three values** (triple-click each line or use the copy button):

   - `apiKey` (starts with `AIza...`)
   - `authDomain` (like `omi-xuanloi.firebaseapp.com`)
   - `projectId` (same as step 1, e.g. `omi-xuanloi`)

**Where to store them:**

- **For the Windows app (Task 7):** paste into `desktop/windows/.env` as:

  ```
  VITE_FIREBASE_API_KEY=<apiKey>
  VITE_FIREBASE_AUTH_DOMAIN=<authDomain>
  VITE_FIREBASE_PROJECT_ID=<projectId>
  ```

  (Leave the other `VITE_...` lines as-is; Task 7 will fill `VITE_OMI_API_BASE` etc.)
  This file is git-ignored — never commit it.

- Also record them in the outputs table at the end of this guide (local notes only).

**Verify:** the **Your apps** section now shows an app named `omi-desktop` with **App ID** and **SDK setup and configuration** expandable.

> If you see **"No apps in your project"** after registering, refresh — Firebase sometimes hides the card until reload. The config is also reachable via **Project settings → General → Your apps → SDK setup and configuration**.

---

## Step 6 — Create the Google Cloud OAuth **Desktop app** client (APIs & Services → Credentials → Create credentials → OAuth client ID)

**Direct link (project-scoped):** https://console.cloud.google.com/apis/credentials?project=omi-xuanloi

> Full menu path: **Google Cloud console → top project selector → `omi-xuanloi` → hamburger ☰ → APIs & Services → Credentials → + CREATE CREDENTIALS → OAuth client ID → Application type: Desktop app**

This client is **the backend's Google OAuth client** — the same client that `backend/routers/auth.py` expects as `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`. The backend exchanges the user's Google code for a Firebase custom token.

### 6A — Make sure the OAuth consent screen is configured (one-time)

Before you can create a client ID, the **OAuth consent screen** must be set up. If you have never done this, you will see a "Configure consent screen" prompt.

1. Go to https://console.cloud.google.com/apis/credentials/consent?project=omi-xuanloi
   - Or from the Credentials page: click **CONFIGURE CONSENT SCREEN** when prompted.
2. Click **Get started** (or **Create**).
3. **App information:**
   - **App name:** `Omi Self-Host` (or `omi-xuanloi`)
   - **User support email:** pick your email from the dropdown.
4. **Audience / User Type:** choose **External** → click **Create** (or **Next**).
   - If asked "Who can access?" leave as **External** (Internal only works for Workspace orgs).
5. **Contact Information → Email addresses:** enter your email again.
6. Check **I agree to the Google API Services: User Data Policy** → click **Continue** / **Create**.
7. If there is a **Data Access / Scopes** step: click **Add or remove scopes** — you do **not** need to add anything now (the backend requests `openid email profile` at runtime). Just click **Save and continue** or **Update**.
8. You should now be back on the **OAuth consent screen** with status **Testing** or **In production** — either is fine for one user.

> If the consent screen was already configured (you see "App name" and "Support email" filled), skip to 6B.

### 6B — Create the Desktop app OAuth client

1. Open https://console.cloud.google.com/apis/credentials?project=omi-xuanloi
2. At the top, confirm the project dropdown shows **`omi-xuanloi`** (click the dropdown and select it if it shows a different project).
3. In the left sidebar (if visible): **APIs & Services → Credentials**.
4. At the top of the Credentials page, click **+ CREATE CREDENTIALS** → **OAuth client ID**.
   - If the button says **Create credentials**, same thing — pick **OAuth client ID**.
5. **Application type:** select **`Desktop app`** from the dropdown. (Do NOT pick Web application, Android, iOS, TV, etc.)
6. **Name:** type `omi-desktop-backend` (or `omi-selfhost-desktop`) — this name is just a label inside the console.
7. Click **Create** (or **CREATE**).
8. A dialog appears: **"OAuth client created"** showing:

   ```
   Your Client ID:       1234567890-abcdefghijklmnopqrstuvwxyz.apps.googleusercontent.com
   Your Client Secret:   GOCSPX-xxxxxxxxxxxxxxxxxxxx
   ```

   Two buttons: **DOWNLOAD JSON** and **OK**.

9. Click **DOWNLOAD JSON** to keep a copy (optional), and also copy both values on the spot.

**What to copy and where to store it:**

- `client_id` (ends with `.apps.googleusercontent.com`)
- `client_secret` (starts with `GOCSPX-...`)

Record them in the outputs table (local notes only). **Later (Task 4):** they go into `/opt/omi/.env` on the VPS as:

```
GOOGLE_CLIENT_ID=<client_id>
GOOGLE_CLIENT_SECRET=<client_secret>
```

**Redirect URI note:** `Application type: Desktop app` uses a loopback redirect (`http://127.0.0.1:<random-port>/callback`) that the Windows app opens locally. You do **not** need to add an authorized redirect URI now. Once the domain `omi-api.xuanloi.me` is live, the backend's callback will be:

```
https://omi-api.xuanloi.me/v1/auth/callback
```

The Desktop app client does not need this URI registered in the console (Google permits loopback for Desktop app type). Just keep the client ID/secret safe.

**Verify:** back on **APIs & Services → Credentials**, under **OAuth 2.0 Client IDs** you now see `omi-desktop-backend` / `omi-selfhost-desktop` of type **Desktop**.

---

## Step 7 — Firestore owner-only rules (⚠️ Publish AFTER backend deploy — Task 4)

> **Do NOT publish these rules until the backend is deployed (Task 4).**
> Reason: the backend must be reachable first so Firestore access via the service account works. If you publish now it is harmless, but the intended order is Task 4 → then publish.

**Direct link:** https://console.firebase.google.com/project/omi-xuanloi/firestore/rules

> Menu path: **Build → Firestore Database → Rules** tab (second tab at the top of Firestore).

1. Complete Task 4 (backend deploy) first — you will be told when to come back to this step.
2. Return to https://console.firebase.google.com/project/omi-xuanloi/firestore/rules
3. You will see a text editor with default rules (something like `allow read, write: if false;` or `allow read, write: if request.time < ...;`).
4. **Select all** the text in the editor (`Ctrl+A` / `Cmd+A`) and **replace** it entirely with the block below — **copy it verbatim** (no edits):

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{uid}/{document=**} {
      allow read, write: if request.auth != null && request.auth.uid == uid;
    }
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```

5. Click **Publish** (blue button above or below the editor).
6. If prompted, confirm. The editor will show "Rules published successfully" and the timestamp will update.

**What this does:** only the signed-in user can read/write their own `users/{uid}/...` subtree; everything else is denied. No other collection is world-readable.

**Verify:** the **Rules** tab now shows exactly the block above and **Last published: just now · Published**.

---

## Outputs table — fill in as you go (keep private, never commit)

Copy this table into your private notes (password manager, local `.txt`, or a paper note). **Do not put it in any git-ignored file that might be shared? Actually do not put real values in any tracked file at all — local notes only.**

| # | Value | Example format | Where you got it | Where it goes next | Your value |
|---|-------|----------------|------------------|--------------------|------------|
| 1 | `projectId` | `omi-xuanloi` | Step 1 — "Project name / project ID" | `desktop/windows/.env` → `VITE_FIREBASE_PROJECT_ID`, `/opt/omi/.env` on VPS as `FIREBASE_PROJECT_ID` (Task 4) | |
| 2 | `apiKey` | `AIzaSy...` | Step 5 — Web app Config → `apiKey` | `desktop/windows/.env` → `VITE_FIREBASE_API_KEY` (Task 7) | |
| 3 | `authDomain` | `omi-xuanloi.firebaseapp.com` | Step 5 — Web app Config → `authDomain` | `desktop/windows/.env` → `VITE_FIREBASE_AUTH_DOMAIN` (Task 7) | |
| 4 | `client_id` | `...apps.googleusercontent.com` | Step 6 — OAuth client Created dialog → Client ID | `/opt/omi/.env` → `GOOGLE_CLIENT_ID` (Task 4) | |
| 5 | `client_secret` | `GOCSPX-...` | Step 6 — OAuth client Created dialog → Client Secret | `/opt/omi/.env` → `GOOGLE_CLIENT_SECRET` (Task 4) | |
| 6 | Service-account filename | `omi-xuanloi-firebase-adminsdk-xxxxx-xxxxxxxxxx.json` | Step 4 — downloaded JSON | Later SCP to `/opt/omi/secrets/firebase-service-account.json` (`chmod 600`) (Task 4) | |
| 7 | Firestore region | `asia-southeast1` | Step 3 | Confirm in Firebase console → Firestore Database → Data (badge) | `asia-southeast1` |

> After filling the table, double-check:
> - `projectId` in step 1 matches `projectId` in step 5's config block.
> - `client_id` ends with `.apps.googleusercontent.com`.
> - You still have the downloaded service-account JSON (and its contents start with `{"type": "service_account",`).

---

## Quick self-check (after steps 1–6, before Task 4)

Open these three URLs and confirm what you see — then tell the operator "Firebase ready, values recorded":

1. https://console.firebase.google.com/project/omi-xuanloi/overview — shows project `omi-xuanloi`.
2. https://console.firebase.google.com/project/omi-xuanloi/authentication/providers — **Google → Enabled**.
3. https://console.firebase.google.com/project/omi-xuanloi/firestore — **Data** tab exists, region `asia-southeast1`.
4. https://console.firebase.google.com/project/omi-xuanloi/settings/serviceaccounts/adminsdk — service account email visible.
5. https://console.firebase.google.com/project/omi-xuanloi/settings/general — **Your apps** shows `omi-desktop` (Web).
6. https://console.cloud.google.com/apis/credentials?project=omi-xuanloi — **OAuth 2.0 Client IDs** lists `omi-desktop-backend` (Desktop app).

If all six are true, you are done with steps 1–6. Leave step 7 for after the backend deploy.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| **"Project name is already taken"** in step 1 | Add a suffix, e.g. `omi-xuanloi-2`. Use the actual generated project ID everywhere. |
| **Can't find Build → Authentication** | Try direct link: https://console.firebase.google.com/project/omi-xuanloi/authentication/providers . If you land on "Welcome to Firebase", click **Project Overview** first. |
| **Can't find Build → Firestore Database** | Direct link: https://console.firebase.google.com/project/omi-xuanloi/firestore . |
| **Gear icon does nothing in step 4/5** | Make sure you are in the Firebase console for the right project (`omi-xuanloi` in the top bar). The gear is to the right of **Project Overview** in the left sidebar. |
| **"Generate new private key" is disabled / needs IAM permission** | You must be **Owner** or **Editor** on the Firebase project. Check IAM: https://console.cloud.google.com/iam-admin/iam?project=omi-xuanloi . |
| **"OAuth consent screen: needs verification"** | Ignore for one-user testing — leave it in **Testing** mode. The warning only matters for public apps. |
| **Can't select "Desktop app" in step 6** | You picked **Web application** by mistake — cancel and start again via **+ CREATE CREDENTIALS → OAuth client ID → Desktop app**. |
| **Outputs table: apiKey/authDomain missing** | Re-open https://console.firebase.google.com/project/omi-xuanloi/settings/general → scroll to **Your apps** → click **SDK setup and configuration → Config**. |
| **Lost the service-account JSON** | Re-generate: **⚙ → Project settings → Service accounts → Generate new private key** again. Old key stays valid until you delete it under IAM → Service Accounts. |

---

## If something leaked (secret committed or pasted)

1. **Service-account JSON:** Firebase console → **⚙ → Project settings → Service accounts** → note the service account email → Cloud console **IAM → Service Accounts** → find that account → **Keys** tab → **Delete** the leaked key → **Generate new private key** → re-SCP to VPS.
2. **OAuth client secret:** Cloud console → **APIs & Services → Credentials** → click the client ID → **Reset secret** (or delete and recreate as Desktop app).
3. **Web `apiKey`:** it is not a privileged secret (it is meant to be in the client), but rotate by deleting and re-creating the Web app if you prefer.

---

## Links — all console URLs used in this guide

- Firebase console home: https://console.firebase.google.com
- Project overview: https://console.firebase.google.com/project/omi-xuanloi/overview
- Authentication → Sign-in method → Google: https://console.firebase.google.com/project/omi-xuanloi/authentication/providers
- Firestore Database: https://console.firebase.google.com/project/omi-xuanloi/firestore
- Firestore Rules: https://console.firebase.google.com/project/omi-xuanloi/firestore/rules
- Project settings → General (Your apps / Web config): https://console.firebase.google.com/project/omi-xuanloi/settings/general
- Project settings → Service accounts (private key): https://console.firebase.google.com/project/omi-xuanloi/settings/serviceaccounts/adminsdk
- Google Cloud Credentials (OAuth clients): https://console.cloud.google.com/apis/credentials?project=omi-xuanloi
- Google Cloud OAuth consent screen: https://console.cloud.google.com/apis/credentials/consent?project=omi-xuanloi
- Google Cloud IAM (if permission errors): https://console.cloud.google.com/iam-admin/iam?project=omi-xuanloi

---

*Source: spec § Firebase & Google setup (design doc 2026-08-21) and task-2 brief. Step 7 rules copied verbatim; step 7 marked "publish AFTER backend deploy (Task 4)". Real values never go in committed files.*
