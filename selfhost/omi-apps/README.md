# omi-apps — Dịch vụ app tích hợp Omi tự host

FastAPI service nhận các webhook từ Omi (memory trigger, real-time transcript,
audio bytes, day summary) và phục vụ chat tools cho app Omi private.

## Endpoints

| Route | Mục đích | Payload |
|---|---|---|
| `GET /health` | Health check | — |
| `POST /webhook/memory?uid=` | Memory creation trigger | JSON memory object |
| `POST /webhook/transcript?uid=&session_id=` | Real-time transcript | JSON `{segments: [...]}` |
| `POST /webhook/audio?uid=&sample_rate=` | Raw audio bytes | PCM16 binary |
| `POST /webhook/day_summary?uid=` | Daily summary cron | JSON có `summary_json` |
| `GET /.well-known/omi-tools.json` | Chat tools manifest | — |

Nguyên tắc (theo docs.omi.me): trả 200 nhanh (<5s), xử lý nặng chạy background,
đọc `uid` từ query params, dùng `summary_json` thay vì `summary` legacy.

## Chạy test

Trong container (không cần Python trên host):

```bash
docker build -t omi-apps-test --target builder .   # hoặc dùng image runtime
docker run --rm -v $PWD:/srv -w /srv python:3.11-slim sh \
  -c "pip install -q -r requirements.txt -r requirements-dev.txt && python -m pytest -q"
```

## Biến môi trường

Xem `selfhost/.env.template` — nhóm biến `OMI_APPS_*`. Không bao giờ commit key thật.
