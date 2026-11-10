# Dữ liệu nộp phạt và khiếu nại

Snapshot ngày 09/11/2026 gồm 23 đoạn tiếng Việt, với 12 đoạn về nộp phạt và 11 đoạn về khiếu nại quyết định xử phạt giao thông. Mỗi dòng trong [procedures.jsonl](procedures.jsonl) là một đoạn có thể đưa vào chỉ mục RAG.

| Trường | Nội dung |
|---|---|
| `id`, `topic` | ID ổn định và nhóm `nop_phat` hoặc `khieu_nai` |
| `title`, `text`, `keywords` | Tiêu đề, nội dung diễn giải và từ khóa truy xuất |
| `sources` | `source_id`, điều/khoản hoặc mục trang web, và trang PDF đánh số từ 1 nếu có |
| `as_of` | Ngày snapshot |

Ghép `sources[].source_id` với `id` trong [sources.json](sources.json) để lấy số văn bản, URL và cơ quan ban hành. Hai bản hợp nhất của Văn phòng Quốc hội được lưu trong `data/raw/` cùng SHA-256 để đối chiếu. Mục Nghị định 118/2021/NĐ-CP có đường dẫn đến bản hợp nhất và các văn bản thành phần.

Phân biệt thời hạn thi hành quyết định, thời hiệu khiếu nại, hạn thụ lý và hạn giải quyết. Các bước thanh toán dựa trên hướng dẫn của cổng dịch vụ công. Mốc thời hạn và điều kiện pháp lý lấy từ văn bản luật.

`python3 scripts/build_db.py` nhập các đoạn và nguồn vào `data/build/catalog.db`. Các bảng `procedures`, `procedure_sources` và `procedure_citations` liên kết bằng khóa ngoại. `procedures_fts` hỗ trợ tìm kiếm BM25 theo tiêu đề, từ khóa và nội dung.

Chạy `python3 scripts/query_catalog.py procedure "thời hiệu khiếu nại" --limit 1` để xem đoạn nguồn và căn cứ. `python3 scripts/evaluate_dataset.py` chấm truy xuất BM25 trên chính SQLite này bằng [golden set](../eval/golden.jsonl).
