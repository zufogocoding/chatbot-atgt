# Bàn giao kiểm chứng catalog

Tài liệu này dành cho người nhận bàn giao: hai người rà soát độc lập và một người gộp/release.

## 1. Trạng thái bàn giao

| Hạng mục | Giá trị |
|---|---|
| Commit dữ liệu catalog | `5de91b1` |
| Commit chốt phạm vi | `6d98f52` |
| Catalog | 276 bản ghi, 264 bản ghi có phạt tiền, 59 quy tắc |
| Trạng thái | `draft` — chưa có snapshot `verified` |
| Validation | 0 lỗi; audit 276/276 khớp |
| Test | 94/94 pass |
| Golden set | 261 câu; API đạt 187/187 ca mức phạt, 46/46 ca thủ tục |
| Phạm vi | Điều 6, 7, 12, 13, 14, 18, 32 |

Điểm b khoản 9a Điều 32 (thiết bị ghi nhận hình ảnh người lái xe) hoãn đến 01/01/2028, không nằm trong phạm vi rà soát.

## 2. Cần bàn giao cho ai

| Vai trò | Việc cần làm | Kết quả bàn giao |
|---|---|---|
| Người rà soát 1 | Điền độc lập phiếu `nguoi-ra-soat-1.csv` | CSV đã điền, có tên và ngày |
| Người rà soát 2 | Điền độc lập phiếu `nguoi-ra-soat-2.csv` | CSV đã điền, có tên và ngày |
| Người gộp/release | Gộp hai phiếu, build DB từ snapshot, chạy lại kiểm tra, tag | Snapshot `verified` + báo cáo + DB + tag |

Hai người rà soát phải là **hai người thật khác nhau**. Không dùng kết quả AI, kể cả các tệp `ai-precheck-*` và `spotcheck-*-ai-review.*`, để thay phiếu của người rà soát.

## 3. Trước khi gửi phiếu

Người bàn giao chạy lại các lệnh sau và chỉ gửi khi tất cả đều đạt:

```bash
git pull
git status --short
python3 scripts/validate_catalog.py
python3 scripts/audit_fines.py
python3 -m pytest -q
```

Kiểm tra hai phiếu có đúng 264 dòng dữ liệu:

```bash
python3 - <<'PY'
import csv
for name in ("nguoi-ra-soat-1.csv", "nguoi-ra-soat-2.csv"):
    path = f"data/catalog/review/{name}"
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    empty = sum(not (row["reviewer"] or "").strip() for row in rows)
    print(name, len(rows), "dòng", empty, "dòng chưa điền")
PY
```

Khi gửi, kèm theo:

- commit `6d98f52` hoặc link repo;
- hai phiếu `data/catalog/review/nguoi-ra-soat-1.csv` và `nguoi-ra-soat-2.csv`;
- [`data/catalog/review/README.md`](../data/catalog/review/README.md) — quy tắc điền phiếu;
- Công báo gốc trong `data/raw/168-2024-nd-cp.pdf` và `data/raw/238-2026-nd-cp.pdf`;
- tài liệu này.

Không gửi kèm phiếu đã điền của người kia.

## 4. Việc của người rà soát

1. Mỗi người chỉ mở phiếu của mình, không xem phiếu của người kia trước khi điền xong.
2. Với từng dòng, đối chiếu `behavior_text`, `fine_min/max`, `fine_unit`, `fine_cap`, `fine_org_min/max/cap`, `legal_path` và `source_quote` với Công báo 168/2024 và 238/2026.
3. Điền các cột review:
   - `expected_fine_min`, `expected_fine_max`;
   - `expected_fine_cap`, `expected_fine_org_min`, `expected_fine_org_max`, `expected_fine_org_cap`;
   - `fine_ok`, `org_fine_ok`, `citation_ok`, `text_ok`;
   - `reviewer`, `reviewed_at`, `note`.
4. Giá trị `*_ok` chỉ nhận `OK`, `SAI` hoặc `NA`.
   - `org_fine_ok = OK` nếu bản ghi có khung phạt tổ chức.
   - `org_fine_ok = NA` nếu bản ghi không có khung tổ chức.
5. Với Điều 32 khoản 5–6 (phạt theo người), điền cả `expected_fine_cap` và `expected_fine_org_cap`.
6. Không sửa các cột dữ liệu catalog. Nếu thấy sai, đánh `SAI` và ghi lý do cụ thể vào `note`.
7. Ghi tên mình vào `reviewer` và ngày hoàn thành vào `reviewed_at`.
8. Gửi lại đúng file CSV, không đổi tên cột và không gộp hai phiếu.

## 5. Việc của người gộp/release

Sau khi nhận đủ hai phiếu:

```bash
python3 scripts/merge_reviews.py --fine-only \
  --reviewer-a data/catalog/review/nguoi-ra-soat-1.csv \
  --reviewer-b data/catalog/review/nguoi-ra-soat-2.csv \
  --out data/catalog/verified/violations-2026-11-09.jsonl
```

Kết quả đúng cần có:

- `verified 276 records -> data/catalog/verified/violations-2026-11-09.jsonl`;
- báo cáo `data/catalog/verified/violations-2026-11-09.report.json`;
- ghi chú `12 record(s) outside the fine-review scope stay draft`.

Nếu script báo lỗi, không sửa tay snapshot. Trả phiếu cho người rà soát tương ứng và làm lại.

Sau khi gộp thành công, build bản phát hành từ snapshot đã xác nhận:

```bash
python3 scripts/build_db.py \
  --violations data/catalog/verified/violations-2026-11-09.jsonl
python3 scripts/evaluate_dataset.py \
  --violations data/catalog/verified/violations-2026-11-09.jsonl
python3 -m pytest -q
```

Sau đó commit snapshot, báo cáo và DB:

```bash
git add data/catalog/verified/ data/build/catalog.db
git commit -m "release: verify catalog with two independent reviews"
git tag catalog-verified-2026-11-11
git push origin main --tags
```

## 6. Điều kiện hoàn thành

Chỉ coi là bàn giao xong khi:

- [ ] Hai phiếu có tên người rà soát khác nhau.
- [ ] Cả 264 dòng có đủ `fine_ok`, `org_fine_ok`, `citation_ok`, `text_ok`.
- [ ] Không còn dòng `SAI` hoặc ô bắt buộc bị bỏ trống.
- [ ] `merge_reviews.py` chạy thành công và tạo snapshot + report.
- [ ] DB được build từ snapshot `verified`.
- [ ] `evaluate_dataset.py` và `pytest` đều đạt.
- [ ] Snapshot, report, DB và tag đã được push.

## 7. Giới hạn đã biết

- Runtime hiện chạy deterministic; chưa cấu hình API key cho LLM.
- Baseline CLI còn thấp so với API (recall@5 91/187, trả lời đúng 42/187); đây là baseline của CLI, không phải kết quả API.
- Câu hỏi chỉ dùng từ “xe khách”, “xe tải”, “xe đầu kéo” có thể bị từ chối là ngoài phạm vi; thêm “ô tô” sẽ định tuyến đúng. Đây là việc cải thiện định tuyến sau, không chặn bàn giao.
- 12 bản ghi cảnh cáo/tịch thu không có mức tiền vẫn `draft` sau khi gộp `--fine-only`.
- Điểm b khoản 9a Điều 32 chưa có trong catalog đến 01/01/2028.
