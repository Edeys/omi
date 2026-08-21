# Cloudflare DNS — Omi self-host

> **VPS IP:** `103.116.39.65` · **Domain:** `xuanloi.me` · **Branch:** `feat/selfhost-backend`
> Mirrors the 9Router pattern in `D:\Websites\HUONG-DAN-HA-TANG.md` §3 (DNS-only A records).

## Records to add (Cloudflare → DNS → Records → Add record)

All three records are **Type A**, **Proxy status: DNS only** (grey cloud, not orange), TTL Auto.

| # | Type | Name | Content (IPv4) | Proxy | TTL |
|---|------|------|-----------------|-------|-----|
| 1 | A | `omi-api` | `103.116.39.65` | DNS only (grey) | Auto |
| 2 | A | `omi-desk` | `103.116.39.65` | DNS only (grey) | Auto |
| 3 | A | `omi-ws` | `103.116.39.65` | DNS only (grey) | Auto |

Full hostnames after creation:

- `omi-api.xuanloi.me` → `103.116.39.65`
- `omi-desk.xuanloi.me` → `103.116.39.65`
- `omi-ws.xuanloi.me` → `103.116.39.65`

## Click path (Cloudflare dashboard)

1. Open https://dash.cloudflare.com → select account → select zone **`xuanloi.me`**.
2. Left sidebar → **DNS** → **Records** (or **DNS → Records**).
3. Click **Add record**.
4. For each of the three rows above:
   - **Type:** `A`
   - **Name:** `omi-api` (then `omi-desk`, then `omi-ws`)
   - **IPv4 address:** `103.116.39.65`
   - **Proxy status:** click the orange cloud to toggle to **DNS only** (grey). Existing 9Router (`9router.xuanloi.me`) and `n8n.xuanloi.me` are DNS-only — match that.
   - **TTL:** `Auto`
   - Click **Save**.
5. Verify the table now shows:

| Name | Type | Content | Proxy |
|------|------|---------|-------|
| `omi-api.xuanloi.me` | A | 103.116.39.65 | DNS only |
| `omi-desk.xuanloi.me` | A | 103.116.39.65 | DNS only |
| `omi-ws.xuanloi.me` | A | 103.116.39.65 | DNS only |
| `9router.xuanloi.me` | A | 103.116.39.65 | DNS only (existing) |
| `n8n.xuanloi.me` | A | 103.116.39.65 | DNS only (existing) |

## Why DNS only (grey cloud)

- Matches §3 for `9router.xuanloi.me` / `n8n.xuanloi.me`.
- Let's Encrypt `certbot --nginx` needs direct origin access for HTTP-01 challenge — proxied (orange) would hide the origin and break issuance unless Cloudflare origin certs are used (not the plan).
- After SSL is issued, you may switch to Proxied if desired, but keep DNS-only until `certbot` succeeds.

## Verify after adding

```bash
# From any machine (local or VPS)
dig +short omi-api.xuanloi.me   # → 103.116.39.65
dig +short omi-desk.xuanloi.me  # → 103.116.39.65
dig +short omi-ws.xuanloi.me    # → 103.116.39.65

# Or
nslookup omi-api.xuanloi.me
nslookup omi-desk.xuanloi.me
nslookup omi-ws.xuanloi.me
```

If `dig` still returns empty, wait 1–2 minutes and retry (Cloudflare publishes instantly, but local resolver may cache).

## Next step — certbot (run AFTER DNS resolves)

> **Do NOT run before the three A records resolve to 103.116.39.65.** The SSH commands below are for the VPS (`root@103.116.39.65`).

```bash
# On the VPS (after DNS propagates)
certbot --nginx -d omi-api.xuanloi.me -d omi-desk.xuanloi.me -d omi-ws.xuanloi.me
# Follow interactive prompts: email, agree ToS, redirect choice.
# Then verify:
nginx -t && systemctl reload nginx
curl -I https://omi-api.xuanloi.me   # expect 502 until backend is deployed (nginx up, backend not yet)
curl -I https://omi-desk.xuanloi.me  # same
curl -I https://omi-ws.xuanloi.me    # same
```

Certbot will edit `/etc/nginx/sites-available/omi-*` to inject real cert paths; keep the `ssl_certificate` lines in the repo as the intended state.

## Reference

- Existing VPS DNS pattern: `D:\Websites\HUONG-DAN-HA-TANG.md` §3 — `9router.xuanloi.me` and `n8n.xuanloi.me` are `A 103.116.39.65 DNS only`.
- Nginx vhosts on VPS: `/etc/nginx/sites-available/omi-api`, `omi-desk`, `omi-ws` (source: `selfhost/nginx/*.conf` in this repo).
- Related Task 3 files: `selfhost/scripts/vps-prep.sh`, `selfhost/nginx/omi-*.conf`.

*Source: Task 3 brief (2026-08-21); infra doc `D:\Websites\HUONG-DAN-HA-TANG.md` §3.*
