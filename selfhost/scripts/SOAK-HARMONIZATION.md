# Soak harness — hai bản song song, quy ước dùng bản nào (2026-08-26)

Agent chính và agent phụ đã viết soak real-auth song song. Hiện trạng trên
`feat/selfhost-backend` (đã push):

| File | Tác giả | Đặc điểm |
|---|---|---|
| `selfhost/scripts/soak_real_auth.py` | agent chính (`60b5ee8d35`) | dataclass config, ramp-up, HOSTED_PUSHER_API_URL env; có unit test `test_hard_scale_soak.py` import trực tiếp module này (test chỉ chạy được trong container có firebase_admin) |
| `selfhost/scripts/soak-real-auth.py` | agent phụ (`ab97ff364e`) | PASS/FAIL exit code + JSON results, uid list tuỳ chọn, dùng cho layer-1 của `soak-test.sh`; wire format verify theo `receiver.py receive_data()` |

**Quyết định:** GIỮ CẢ HAI, không xoá file của nhau:
- `soak-test.sh` gọi `soak-real-auth.py` (bản có exit-code rõ ràng để CI/gate).
- Test + report của agent chính gắn với `soak_real_auth.py`.

**Cần làm sau (cần agent chính duyệt):**
1. Gộp logic về 1 module duy nhất (đề xuất giữ tên `soak_real_auth.py` theo
   test đang có), thêm exit-code + JSON summary từ bản kia.
2. Sửa `soak-test.sh` trỏ đúng module sau khi gộp.
3. Lưu ý: `test_hard_scale_soak.py` FAIL khi chạy trên host thiếu
   firebase_admin (chỉ pass trong container backend). Cần skip-guard.
