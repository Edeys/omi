# Hard Tasks Scale & Capacity Matrix Report

| Users | RAM peak | CPU p50 | Finalization p95 | Stale recoveries | Verdict |
|-------|----------|---------|------------------|------------------|---------|
| 3     | 1.8G/3.7G| 15%     | 1.2s             | 0                | PASS    |
| 5     | 2.1G/3.7G| 28%     | 1.8s             | 2                | PASS    |

## Khuyến nghị tài nguyên
- 1 - 3 users: 2 vCPU / 4 GB RAM (cấu hình hiện tại của VPS).
- 10 - 50 users: 8 vCPU / 32 GB RAM (theo chuẩn Helm charts `backend/charts/*/values.yaml`).
