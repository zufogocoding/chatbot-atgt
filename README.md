# Chatbot tra cứu xử phạt giao thông

Chatbot tiếng Việt giúp người dân tra cứu mức phạt vi phạm giao thông cho **xe máy** và **ô tô**: số tiền, hình phạt bổ sung, trừ điểm GPLX, căn cứ pháp lý và thủ tục nộp phạt/khiếu nại.

- Phạm vi, kiến trúc, kế hoạch đánh giá: [`docs/project-brief.md`](docs/project-brief.md)
- Schema catalog, quy trình rebuild, giới hạn: [`data/catalog/README.md`](data/catalog/README.md)

## Trạng thái hiện tại

| Hạng mục | Giá trị |
|---|---|
| Văn bản áp dụng | 168/2024/NĐ-CP, hợp nhất với 238/2026/NĐ-CP (hiệu lực 15/08/2026) |
| Ngày snapshot | 09/11/2026 |
| Bản ghi vi phạm | 267 (Điều 6, 7, 13, 14, 18, 32) — gồm vi phạm người điều khiển và chủ phương tiện |
| Alias tiếng dân | 30 nhóm, 201 cách nói |
| Kiểm chứng | `draft` — validation 0 lỗi, chưa review thủ công 100% |
| Tra cứu thử | SQLite + FTS5 + CLI |

Phạm vi catalog hiện tại: quy tắc giao thông, điều kiện phương tiện, điều kiện người lái, và **Điều 32 (chủ phương tiện)** — bao gồm sang tên/không chính chủ, giao xe cho người không đủ điều kiện, biển số/đăng ký, cải tạo xe. Chưa gồm: Điều 32 khoản 5–6 (phạt trên mỗi người vượt quá, có trần), các điểm 238/2026 thêm mới 9a/11.e/13.e, Điều 12, 17.

Phần **thủ tục nộp phạt/khiếu nại** chưa được thu thập; CLI hiện nói rõ điều này thay vì bịa.

## Chạy nhanh

Yêu cầu: Python 3.11+ (không cần thư viện ngoài cho phần catalog).

```bash
# 1. Parse văn bản 168 (đã có file parsed, chạy lại nếu cần)
python3 scripts/parse_168.py

# 2. Trích xuất bản nháp từ 168
python3 scripts/extract_violations.py

# 3. Hợp nhất sửa đổi 238/2026
python3 scripts/apply_amendments_238.py

# 4. Kiểm tra catalog + alias
python3 scripts/validate_catalog.py

# 5. Build SQLite + FTS5
python3 scripts/build_db.py
```

Tra thử:

```bash
python3 scripts/query_catalog.py search "xe máy vượt đèn đỏ"
python3 scripts/query_catalog.py answer "ô tô quá tốc độ"
python3 scripts/query_catalog.py answer "vượt đèn đỏ"          # hỏi lại loại xe
python3 scripts/query_catalog.py answer "xe máy không chính chủ" # chủ phương tiện (Điều 32)
python3 scripts/query_catalog.py record nd168-d7-k7-c
python3 scripts/query_catalog.py stats
```

## Cấu trúc

```
data/raw/          PDF/DOCX gốc từ nguồn chính thức
data/parsed/       Text + cấu trúc điều/khoản/điểm
data/amendments/   Patch sửa đổi (238/2026)
data/catalog/      violations.jsonl, penalty-rules.jsonl, aliases.json
data/overrides/    Điều kiện hình phạt thủ công
data/build/        SQLite sinh tự động (không sửa tay)
scripts/           Parse, extract, consolidate, validate, build, query
docs/              Project brief
```

## Nguyên tắc

1. Không có nguồn → không trả lời.
2. Con số và căn cứ lấy từ catalog, không do LLM sinh.
3. Thiếu loại xe hoặc thiếu mức vi phạm → hỏi lại.
4. Hình phạt có điều kiện phải hiển thị "có thể bị... nếu...".
5. Văn bản luật thay đổi → cập nhật patch + chạy lại validation/golden set.

> Thông tin trong repo dùng cho đồ án và tra cứu tham khảo, không thay thế tư vấn pháp lý.
