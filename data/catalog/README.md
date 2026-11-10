# Catalog vi phạm giao thông

Thư mục này là **nguồn sự thật** cho phần tra cứu mức phạt của chatbot. SQLite/Chroma sau này chỉ là bản build lại từ các file ở đây, không sửa tay.

## 1. Trạng thái hiện tại

| Hạng mục | Giá trị |
|---|---|
| Văn bản gốc | Nghị định 168/2024/NĐ-CP |
| Văn bản sửa đổi | Nghị định 238/2026/NĐ-CP, hiệu lực 15/08/2026 |
| Ngày hợp nhất | 09/11/2026 |
| Số bản ghi | **271** |
| Điều đã trích xuất | 6, 7, 12, 13, 14, 18, 32 |
| Bản ghi có phạt tiền | 259 |
| Bản ghi chỉ có hình phạt bổ sung | 10 (tịch thu phương tiện) |
| Bản ghi cảnh cáo | 2 |
| Có hình phạt bổ sung | 67 |
| Có biện pháp khắc phục hậu quả | 68 |
| Có trừ điểm GPLX | 109 |
| Quy tắc hình phạt/trừ điểm | 57 |
| Alias tiếng dân | 44 nhóm, 285 cách nói (229 biến thể sau chuẩn hóa) |
| Trạng thái kiểm chứng | `draft`. Đối chiếu tự động khớp 271/271. Hai lượt rà soát của người kiểm chứng đang chờ xác nhận. |

Phân bố theo Điều:

| Điều | Nội dung | Xe máy | Ô tô | Cả hai |
|---|---|---:|---:|---:|
| 6 | Ô tô – quy tắc giao thông | – | 75 | – |
| 7 | Xe máy – quy tắc giao thông | 65 | – | – |
| 12 | Người được chở trên xe máy/ô tô | 3 | 1 | – |
| 13 | Ô tô – điều kiện phương tiện | – | 23 | – |
| 14 | Xe máy – điều kiện phương tiện | 13 | – | – |
| 18 | Điều kiện người điều khiển | 12 | 11 | 1 |
| 32 | Chủ phương tiện (sang tên, biển số, đăng ký, cải tạo, giao xe...) | 15 | 50 | 2 |

## 2. Cấu trúc thư mục

```
data/
├── raw/                    # PDF/DOCX gốc tải từ nguồn chính thức
├── parsed/
│   ├── 168-2024-nd-cp-full.txt   # toàn văn 168 (Công báo)
│   ├── 238-2026-nd-cp.txt        # toàn văn 238
│   ├── 168-provisions.jsonl      # 1.242 điều/khoản/điểm đã parse
│   └── 168-articles.json
├── amendments/
│   └── 238-2026.json       # các patch sửa đổi đã mã hóa
├── overrides/
│   └── penalty-conditions.json   # điều kiện áp dụng bổ sung (thủ công)
├── catalog/
│   ├── draft/              # kết quả trích xuất từ 168 gốc
│   ├── consolidated/       # catalog hợp nhất với 238 (dùng cho chatbot)
│   ├── aliases.json        # cách nói của người dân → record_id
│   ├── review/             # phiếu review CSV sinh tự động
│   └── README.md
├── build/
│   └── catalog.db          # SQLite sinh tự động, không sửa tay
├── procedures/             # corpus thủ tục và danh mục nguồn
└── eval/                   # golden set và cách chấm baseline
```

**Dùng file nào?**

- `data/catalog/consolidated/violations.jsonl` — dùng để build DB/chatbot.
- `data/build/catalog.db` — SQLite sinh từ catalog + alias; dùng cho tra cứu/API.
- `data/catalog/draft/` — chỉ để đối chiếu lịch sử, không dùng trực tiếp.
- `data/catalog/aliases.json` — dùng cho bước intent/alias matching.

## 3. Schema bản ghi vi phạm

```json
{
  "id": "nd168-d7-k7-c",
  "document": "168/2024/NĐ-CP",
  "document_title": "Nghị định 168/2024/NĐ-CP ... (hợp nhất với Nghị định 238/2026/NĐ-CP)",
  "article_title": "Xử phạt, trừ điểm giấy phép lái xe của người điều khiển xe mô tô ...",
  "vehicle_type": "xe_may",
  "behavior_group": "quy_tac_giao_thong",
  "behavior_text": "Không chấp hành hiệu lệnh của đèn tín hiệu giao thông;",
  "clause_text": "Phạt tiền từ 4.000.000 đồng đến 6.000.000 đồng ...",
  "fine_min": 4000000,
  "fine_max": 6000000,
  "fine_text": "Phạt tiền từ 4.000.000 đồng đến 6.000.000 đồng",
  "record_kind": "fine",
  "additional_penalties": [],
  "remedial_measures": [],
  "license_points": 4,
  "penalty_rule_ids": ["nd168-d7-k13-b"],
  "legal_basis": {
    "document": "168/2024/NĐ-CP",
    "article": 7,
    "clause": 7,
    "point": "c",
    "path": "7.7.c"
  },
  "source_url": "https://datafiles.chinhphu.vn/.../168-nd-cp.signed.pdf",
  "source_quote": "Phạt tiền từ ... || Không chấp hành hiệu lệnh ...",
  "verification": {
    "status": "draft",
    "verified_by": "",
    "verified_at": "",
    "notes": "Consolidated text after 238/2026/NĐ-CP; verify against both gazettes."
  },
  "version": {
    "effective_from": "2025-01-01",
    "effective_to": null,
    "amended_by": [],
    "last_amended": null,
    "consolidated_as_of": "2026-11-09"
  }
}
```

### Ý nghĩa các trường quan trọng

| Trường | Ghi chú |
|---|---|
| `vehicle_type` | `xe_may`, `o_to`, hoặc `both` |
| `subject` | `nguoi_dieu_khien`, `nguoi_duoc_cho` (Điều 12) hoặc `chu_phuong_tien` (Điều 32) |
| `record_kind` | `fine` (có khung tiền), `warning` (cảnh cáo, tiền = 0), `additional_only` (không phạt tiền, chỉ tịch thu) |
| `fine_min`, `fine_max` | Đơn vị đồng, mức phạt cá nhân. `null` với `additional_only` |
| `fine_by_subject.to_chuc` | Mức phạt tổ chức (thường gặp ở Điều 32) |
| `additional_penalties` | Tước GPLX/phù hiệu/giấy kiểm định, tịch thu phương tiện/biển số/thiết bị, thu hồi GPLX |
| `remedial_measures` | Buộc khắc phục hậu quả, thu hồi hồ sơ/đăng ký/giấy tờ không hợp lệ |
| `license_points` | Số điểm bị trừ, `0` nếu không trừ |
| `license_points_condition` | Điều kiện trừ điểm (vd. chỉ khi chủ phương tiện trực tiếp điều khiển) |
| `penalty_rule_ids` | Truy vết tới quy tắc trong `penalty-rules.jsonl` |
| `legal_basis.path` | Đường dẫn `Điều.Khoản.Điểm` để hiển thị trích dẫn |
| `source_quote` | Nguyên văn đoạn luật dùng để kiểm chứng |
| `verification.status` | `draft` / `verified` / `deprecated` |

### Hình phạt có điều kiện

Một số hình phạt chỉ áp dụng trong một trường hợp cụ thể. Khi đó object có thêm `condition`:

```json
{
  "type": "tich_thu_phuong_tien",
  "condition": "không chứng minh được nguồn gốc xuất xứ của phương tiện"
}
```

hoặc:

```json
{
  "type": "thu_hoi_gplx",
  "condition": "Giấy phép lái xe không do cơ quan có thẩm quyền cấp hoặc không hợp lệ"
}
```

**Quy tắc hiển thị:** không được viết "bị tịch thu xe" như hình phạt chắc chắn. Phải viết "có thể bị tịch thu nếu...". Các điều kiện này nằm trong `data/overrides/penalty-conditions.json` và được áp dụng tự động khi trích xuất.

## 4. Schema alias

`aliases.json` gom cách nói thông thường của người dân về cùng một nhóm hành vi:

```json
{
  "id": "vuot-den-do",
  "canonical": "Không chấp hành hiệu lệnh của đèn tín hiệu giao thông",
  "citizen_phrases": ["vượt đèn đỏ", "chạy đèn đỏ", "vuot den do"],
  "records": {
    "o_to": [{"record_id": "nd168-d6-k9-b"}],
    "xe_may": [{"record_id": "nd168-d7-k7-c"}]
  }
}
```

- `requires_qualifier: true`: hành vi có nhiều khung phạt (tốc độ, nồng độ cồn...) — chatbot phải hỏi thêm trước khi chọn.
- Mỗi record trong danh sách nhiều record phải có `qualifier` để phân biệt.
- Alias không thay thế `behavior_text`; nó chỉ dùng cho bước khớp ý định ban đầu. Kết quả cuối vẫn phải trỏ về record có căn cứ pháp lý.

## 5. Quy trình rebuild

Chạy từ thư mục gốc repo:

```bash
# 1. Parse cấu trúc 168
python3 scripts/parse_168.py

# 2. Trích xuất bản nháp từ 168 gốc
python3 scripts/extract_violations.py

# 3. Áp dụng sửa đổi 238/2026
python3 scripts/apply_amendments_238.py

# 4. Kiểm tra toàn bộ catalog + alias
python3 scripts/validate_catalog.py

# 5. Build SQLite cho chatbot/tra cứu
python3 scripts/build_db.py
```

Kết quả mong đợi:

```
records: 271
penalty rules: 57
fine records checked: 259
source quotes checked: 271
errors: 0
warnings: 0 (hoặc chỉ warning về record chưa có alias)
built data/build/catalog.db
  violations: 271
  penalty rules: 57
  alias groups: 44 (229 phrases)
```

### Tra thử bằng CLI

`scripts/query_catalog.py` dùng đúng database mà API sẽ dùng:

```bash
# Tìm theo câu hỏi (ưu tiên alias, sau đó FTS)
python3 scripts/query_catalog.py search "xe máy vượt đèn đỏ"
python3 scripts/query_catalog.py search "nồng độ cồn" --vehicle o_to

# Xem câu trả lời thử theo template cố định
python3 scripts/query_catalog.py answer "vượt đèn đỏ"
python3 scripts/query_catalog.py answer "ô tô quá tốc độ"

# Xem một record đầy đủ
python3 scripts/query_catalog.py record nd168-d7-k7-c
python3 scripts/query_catalog.py record nd168-d7-k7-c --json

# Thống kê database
python3 scripts/query_catalog.py stats
```

Nguyên tắc của `answer`:

- Alias khớp chính xác → trả lời từ record, không để LLM tự chọn số.
- Thiếu loại xe → hỏi lại.
- Nhiều khung phạt (tốc độ, nồng độ cồn, không bằng lái...) → liệt kê để người dùng chọn.
- Không khớp alias → chỉ gợi ý các record gần nhất, không khẳng định mức phạt.
- Hình phạt có `condition` luôn hiển thị dạng "có thể bị... nếu...".

### Xuất phiếu review thủ công

```bash
# Toàn bộ 271 bản ghi
python3 scripts/export_review.py

# Chỉ 259 bản ghi có phạt tiền
python3 scripts/export_review.py --fine-only

# Phiếu riêng cho từng người rà soát
python3 scripts/export_review.py --fine-only --out data/catalog/review/nguoi-ra-soat-1.csv
python3 scripts/export_review.py --fine-only --out data/catalog/review/nguoi-ra-soat-2.csv
```

Repo có sẵn hai phiếu trống `nguoi-ra-soat-1.csv` và `nguoi-ra-soat-2.csv` cho 259 bản ghi có phạt tiền; hai người có thể mở trực tiếp và điền, hoặc tạo lại bằng lệnh trên.

File CSV dùng UTF-8 (mở trực tiếp bằng Excel/LibreOffice):

- Các cột đầu là dữ liệu catalog: `id`, `behavior_text`, `fine_min/max`, `legal_path`, `source_quote`...
- Các cột trống để người review điền: `expected_fine_min/max`, `fine_ok`, `citation_ok`, `text_ok`, `reviewer`, `reviewed_at`, `note`.
- Giá trị gợi ý cho `*_ok`: `OK`, `SAI`, `NA`.

Hai người đối chiếu độc lập với Công báo 168 và 238 theo đề cương. Mỗi người dùng một bản phiếu riêng. Chỉ chuyển bản ghi sang `verified` sau khi hai lượt đều xác nhận số tiền, căn cứ và nội dung. Tạo phiếu mới bằng `--out` để giữ kết quả đã điền.

Sau khi cả hai phiếu đã điền, gộp thành snapshot `verified`:

```bash
python3 scripts/merge_reviews.py --fine-only \
  --reviewer-a data/catalog/review/nguoi-ra-soat-1.csv \
  --reviewer-b data/catalog/review/nguoi-ra-soat-2.csv \
  --out data/catalog/verified/violations-2026-11-09.jsonl
```

Script từ chối ghi snapshot nếu thiếu bản ghi, hai phiếu cùng một người, có mục `SAI`/bỏ trống, hoặc số tiền hai người nhập khác catalog. Với `--fine-only`, 259 bản ghi có phạt tiền được chuyển `verified`; 12 bản ghi cảnh cáo/tịch thu không có mức tiền giữ nguyên `draft`. Báo cáo gộp được ghi cạnh snapshot (`.report.json`).

Dùng snapshot đã xác nhận để build bản phát hành:

```bash
python3 scripts/build_db.py \
  --violations data/catalog/verified/violations-2026-11-09.jsonl
python3 scripts/evaluate_dataset.py \
  --violations data/catalog/verified/violations-2026-11-09.jsonl
```

[`fine-audit-2026-11-10.csv`](review/fine-audit-2026-11-10.csv) lưu kết quả đối chiếu tự động riêng cho 271 bản ghi, gồm mức tiền cá nhân, tổ chức và đoạn luật dùng để đối chiếu. Chạy lại với `python3 scripts/audit_fines.py`. Dùng `--out` để xuất CSV mới.

### Khi có văn bản mới

1. Tải toàn văn vào `data/raw/`, parse vào `data/parsed/`.
2. Mã hóa thay đổi vào `data/amendments/<so-hieu>.json`:
   - `patches`: sửa text của record đã có (`replace` hoặc `set_text`).
   - `added`: bản ghi mới.
   - `rule_patches`: sửa quy tắc hình phạt/trừ điểm.
3. Cập nhật `scripts/apply_amendments_238.py` (hoặc tạo script mới) và chạy lại validation.
4. Cập nhật `consolidated_as_of` và chạy lại golden set trước khi phát hành.

## 6. Kiểm chứng

`scripts/validate_catalog.py` kiểm tra:

- `fine_min <= fine_max`; bản ghi cảnh cáo có tiền = 0; bản ghi tịch thu có tiền = `null`.
- `legal_basis.path` khớp với `article/clause/point`.
- `source_quote` không rỗng.
- Text hành vi và điều khoản xuất hiện trong văn bản gốc 168 hoặc 238 (sau khi chuẩn hóa khoảng trắng). Với record bị sửa, script hoàn nguyên patch rồi đối chiếu bản gốc.
- Không còn cụm từ đã bị 238 thay thế (ví dụ "giấy chứng nhận kiểm định", "chở người trên nóc xe").
- Mọi `penalty_rule_id` tồn tại; mọi tham chiếu của quy tắc khớp ít nhất một record.
- Alias trỏ đúng record và đúng loại xe.
- Spot-check các bản ghi phổ biến: vượt đèn đỏ, quá tốc độ 20–35 km/h, nồng độ cồn, mũ bảo hiểm, biển số.

`scripts/build_db.py` kiểm tra thêm khi build SQLite: số record khớp JSONL, FTS không thiếu bản ghi, foreign key alias → record, `penalty_rule_id` không treo, alias phrase không rỗng.

**Đã đối chiếu thủ công** các nhóm sau với Công báo:

| Hành vi | Record | Kết quả |
|---|---|---|
| Ô tô vượt đèn đỏ | `nd168-d6-k9-b` | 18–20 triệu, trừ 4 điểm |
| Xe máy vượt đèn đỏ | `nd168-d7-k7-c` | 4–6 triệu, trừ 4 điểm |
| Ô tô quá tốc độ 20–35 km/h | `nd168-d6-k6-a` | 6–8 triệu, trừ 4 điểm |
| Xe máy không đội mũ | `nd168-d7-k2-h` | 400–600 nghìn, không trừ điểm |
| Ô tô nồng độ cồn ≤ 50 mg | `nd168-d6-k6-c` | 6–8 triệu, trừ 4 điểm |
| Xe máy nồng độ cồn ≤ 50 mg | `nd168-d7-k6-a` | 2–3 triệu, trừ 4 điểm |
| Ô tô không có biển số | `nd168-d13-k7-b` | 10–12 triệu, trừ 6 điểm |
| Xe máy không có biển số | `nd168-d14-k3-a` | 4–6 triệu, trừ 6 điểm |
| Ô tô không có GPLX | `nd168-d18-k9-b` | 18–20 triệu |
| Xe máy ≤ 125 cm³ không có GPLX | `nd168-d18-k5-a` | 2–4 triệu |

Catalog giữ trạng thái **draft** đến khi hoàn tất hai lượt đối chiếu số tiền theo đề cương.

## 7. Giới hạn hiện tại

- Thủ tục nộp phạt và khiếu nại nằm trong [`data/procedures/`](../procedures/). Nhánh trả lời bằng RAG đang chờ tích hợp.
- **Điều 32 (chủ phương tiện) đã trích xuất phần lõi**: sang tên/thay đổi chủ xe, đăng ký/biển số, cải tạo xe, giao xe cho người không đủ điều kiện, đưa xe không biển số/đăng ký tham gia giao thông, tịch thu phương tiện (một số trường hợp). **Chưa gồm**: khoản 5, 6 (phạt theo số người vượt quá, có trần tối đa — mô hình phạt khác), các điểm 238/2026 bổ sung như 9a, 11.e, 13.e, và một số hành vi tham chiếu Điều 20/21/22/34 chưa có trong catalog.
- **Điều 12 mới trích xuất nhóm người được chở**: mũ bảo hiểm, dây đai an toàn, bám kéo, che ô/dù. Các hành vi công cộng khác của Điều 12 (bán hàng vỉa hè, vật cản, drone...) nằm ngoài phạm vi. **Chưa trích xuất Điều 17 và 20–24** (môi trường, vận tải hành khách/hàng hóa).
- **Một số điểm luật gộp nhiều hành vi thay thế** (ví dụ Điều 18 khoản 5 điểm a). Record giữ nguyên văn cả điểm; hình phạt bổ sung có `condition` để tránh khẳng định sai. Khi làm UI nên tách hoặc hỏi lại hành vi cụ thể.
- **Chưa xử lý quy định chuyển tiếp** của 238/2026 và các mức phạt thay đổi theo thời điểm. Catalog là ảnh chụp tại 09/11/2026.
- [Golden set và kết quả baseline](../eval/README.md) tách độ khớp của dữ liệu khỏi chất lượng chọn bản ghi và câu trả lời.

## 8. Quy ước đặt ID

```
nd168-d<Điều>-k<Khoản>[-<Điểm>]
```

Ví dụ:

- `nd168-d6-k9-b` = Nghị định 168, Điều 6, khoản 9, điểm b.
- `nd168-d6-k1a` = khoản 1a được 238 bổ sung.
- `nd168-d18-k5-a` = Điều 18, khoản 5, điểm a.

ID không đổi khi văn bản được sửa đổi; thay đổi được ghi ở `version.amended_by` và `version.last_amended`.
