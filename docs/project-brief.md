# Chatbot tra cứu xử phạt vi phạm giao thông

**Trạng thái:** Có catalog hợp nhất 271 bản ghi, corpus thủ tục, golden set 254 câu và API FastAPI. Catalog đang ở trạng thái `draft`.

**Cập nhật:** 10/11/2026

**Bối cảnh:** Đồ án môn học — chi phí triển khai không phải ràng buộc chính; ưu tiên khả năng thí nghiệm, tái lập và demo.

---

## 1. Tóm tắt một câu

Xây chatbot tiếng Việt cho người dân tra cứu: **hành vi vi phạm → mức phạt tiền → hình phạt bổ sung/trừ điểm GPLX → căn cứ pháp lý → thủ tục nộp phạt/khiếu nại**, giới hạn ở xe máy và ô tô.

## 2. Người dùng và nhu cầu

- **Người dùng chính:** người dân tự tra cứu, không có kiến thức pháp lý chuyên sâu.
- **Câu hỏi điển hình:**
  - "Xe máy vượt đèn đỏ bị phạt bao nhiêu?"
  - "Ô tô chạy quá tốc độ 20 km/h thì bị gì?"
  - "Không đội mũ bảo hiểm có bị tước bằng không?"
  - "Nộp phạt ở đâu, thời hạn bao lâu?"
  - "Muốn khiếu nại quyết định xử phạt thì làm thế nào?"
- **Điều chatbot phải làm tốt:** trả lời đúng số tiền, đúng căn cứ, biết hỏi lại khi thiếu loại xe, và **không bịa** khi không có dữ liệu.

## 3. Phạm vi đã chốt

| Trong phạm vi | Ngoài phạm vi |
|---|---|
| Người dân tra cứu | Cán bộ/CSGT tra cứu nghiệp vụ |
| Xe máy (mô tô, xe gắn máy) | Xe tải, xe khách, xe đạp, xe thô sơ, người đi bộ |
| Mức phạt tiền | Tra phạt nguội theo biển số |
| Hình phạt bổ sung: tước GPLX, tạm giữ phương tiện... | Tư vấn tranh tụng/luật sư |
| Trừ điểm GPLX (12 điểm) | Tích hợp thanh toán/nộp phạt trực tuyến |
| Căn cứ pháp lý: nghị định, điều/khoản/điểm | Đa ngôn ngữ (chỉ tiếng Việt) |
| Thủ tục nộp phạt, khiếu nại | Dự đoán kết quả xử lý thực tế |

**Nguyên tắc phạm vi:** thà trả lời hẹp mà đúng, còn hơn mở rộng sang xe tải/xe khách khi chưa kiểm chứng dữ liệu.

## 4. Quyết định kiến trúc

### 4.1. Hybrid: tra cứu có cấu trúc + RAG

```
Người dùng
   │
   ▼
Web chat (Next.js)
   │
   ▼
FastAPI
   ├─ Chuẩn hóa câu hỏi + intent router
   ├─ Structured lookup  ──► SQLite catalog (mức phạt, căn cứ)
   ├─ RAG                ──► Chroma + BM25 (thủ tục, giải thích)
   └─ Answer composer    ──► template + trích dẫn + guardrail
```

**Lý do chọn:**

1. **Đúng số tiền:** mức phạt lấy từ bảng đã kiểm chứng, LLM không được tự sinh số.
2. **Truy vết được:** mỗi câu trả lời gắn với đúng điều/khoản/điểm và phiên bản văn bản.
3. **Ít phụ thuộc API:** phần tra mức phạt vẫn chạy khi LLM provider lỗi.
4. **Phù hợp đồ án:** dễ tách thí nghiệm (structured-only vs RAG-only vs hybrid) để viết báo cáo.

### 4.2. Stack chốt cho MVP

| Thành phần | Lựa chọn | Ghi chú |
|---|---|---|
| Backend | Python 3.11 + FastAPI | API chat, health check, logging |
| Frontend | Next.js (React) | Nếu nhóm không có người làm FE: Streamlit dự phòng |
| CSDL có cấu trúc | SQLite | Zero-config, dễ backup, đủ cho đồ án |
| Vector store | ChromaDB | Chạy local, dễ reset index |
| Embedding | `BAAI/bge-m3` (local) | Hỗ trợ tiếng Việt; không cần GPU cho lượng dữ liệu nhỏ |
| Retrieval | BM25 + dense + RRF | Hybrid tốt hơn dense thuần với văn bản luật |
| LLM | Gemini Flash (free tier) + fallback Groq/OpenRouter; Ollama Qwen 7B cho demo offline | Tách lớp `LLMClient` để đổi provider |
| Đánh giá | pytest + script chấm điểm | Golden set dạng JSONL |
| Đóng gói | Docker Compose (tùy chọn) | Không bắt buộc nếu demo local |

**Không dùng trong MVP:** fine-tuning LLM, multi-agent, graph database, GPU self-host.

### 4.3. Vai trò của LLM

LLM chỉ làm 3 việc:

1. Trích xuất slot từ câu hỏi: `vehicle_type`, `behavior`, `intent`.
2. Chọn bản ghi vi phạm khớp nhất trong top-k ứng viên (structured output).
3. Diễn giải câu trả lời và tóm tắt văn bản luật cho phần thủ tục.

**LLM không được:** tự tính tiền, tự bịa điều luật, tự quyết định khi độ khớp thấp.

## 5. Nguồn dữ liệu và phiên bản luật

### 5.1. Văn bản áp dụng tại 11/2026

| Văn bản | Vai trò | Ghi chú hiệu lực |
|---|---|---|
| Luật Trật tự, an toàn giao thông đường bộ 36/2024/QH15 | Khung pháp lý, trừ điểm GPLX | Hiệu lực 01/01/2025 |
| Luật 118/2025/QH15 | Sửa đổi 10 luật, có 36/2024/QH15 | Hiệu lực 01/07/2026 |
| Nghị định 168/2024/NĐ-CP | Mức phạt, hình phạt bổ sung, trừ điểm | Hiệu lực 01/01/2025 |
| **Nghị định 238/2026/NĐ-CP** | **Sửa đổi, bổ sung 168/2024** | **Hiệu lực 15/08/2026** |
| Luật Xử lý vi phạm hành chính, 90/VBHN-VPQH | Thi hành quyết định, nộp phạt và quyền khiếu nại | Bản hợp nhất ngày 30/03/2026 |
| Luật Khiếu nại, 28/VBHN-VPQH | Trình tự, hồ sơ, thời hiệu và thời hạn giải quyết khiếu nại | Gồm sửa đổi theo Luật 136/2025/QH15 có hiệu lực từ 01/07/2026 |
| Nghị định 189/2025/NĐ-CP | Thẩm quyền xử phạt | Chỉ cần nếu trả lời "ai có quyền phạt" |

**Lưu ý sống còn:** Nghị định 168/2024 đã bị sửa đổi bởi **Nghị định 238/2026/NĐ-CP** từ 15/08/2026. Dataset phải dùng **văn bản hợp nhất** hoặc đọc cả 168 + 238, không được chỉ lấy toàn văn 168/2024.

### 5.2. Nguồn thu thập

- **Chính thức:** `vbpl.vn`, `vanban.chinhphu.vn`, `datafiles.chinhphu.vn`, Công báo.
- **Văn bản hợp nhất:** ưu tiên các file `VBHN` do cơ quan nhà nước công bố (ví dụ 55/VBHN-VPQH cho Luật 36/2024).
- **Thủ tục:** Cổng Dịch vụ công quốc gia (`dichvucong.gov.vn`), trang của Bộ Công an.
- **Quy tắc:** báo/news chỉ dùng để phát hiện văn bản mới; **mọi con số phải đối chiếu văn bản gốc/hợp nhất**.

### 5.3. Versioning

- Mỗi bản ghi có `effective_from`, `effective_to`.
- Catalog được snapshot theo mốc, ví dụ `legal-2026-11`.
- Chatbot hiển thị: "Áp dụng văn bản đến ngày 09/11/2026".
- Khi có văn bản mới: tạo diff, chạy lại golden set, rồi mới phát hành.

## 6. Mô hình dữ liệu

### 6.1. Các bảng/file chính

Nguồn sự thật là các file JSONL/JSON trong `data/`; SQLite chỉ là bản build lại.

| Thành phần | Nội dung |
|---|---|
| `data/parsed/168-provisions.jsonl` | 1.242 điều/khoản/điểm đã parse từ Công báo 168/2024 |
| `data/parsed/238-2026-nd-cp.txt` | Toàn văn Nghị định 238/2026 |
| `data/amendments/238-2026.json` | 20 bản vá nội dung, 1 bản ghi mới và 7 bản vá quy tắc |
| `data/catalog/consolidated/violations.jsonl` | **271 bản ghi vi phạm** đã hợp nhất 168 + 238 |
| `data/catalog/consolidated/penalty-rules.jsonl` | 57 quy tắc hình phạt bổ sung/trừ điểm |
| `data/catalog/aliases.json` | 44 nhóm alias, 285 cách nói của người dân (229 biến thể sau chuẩn hóa) |
| `data/overrides/penalty-conditions.json` | Điều kiện áp dụng cho hình phạt có điều kiện |
| `data/build/catalog.db` | SQLite sinh tự động: violations, penalty_rules, alias_*, FTS5 |
| `data/procedures/` | 23 đoạn thủ tục và danh mục nguồn |
| `data/eval/golden.jsonl` | 254 câu có nhãn và căn cứ kỳ vọng |

### 6.2. Schema một bản ghi vi phạm

```json
{
  "id": "nd168-d7-k7-c",
  "document": "168/2024/NĐ-CP",
  "document_title": "Nghị định 168/2024/NĐ-CP ... (hợp nhất với Nghị định 238/2026/NĐ-CP)",
  "article_title": "Xử phạt, trừ điểm giấy phép lái của người điều khiển xe mô tô ...",
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
    "notes": "Auto-extracted; verify amount and citation against the gazette."
  },
  "version": {
    "effective_from": "2025-01-01",
    "effective_to": null,
    "amended_by": [],
    "consolidated_as_of": "2026-11-09"
  }
}
```

Khác với bản nháp ban đầu:

- `id` dạng `nd168-d<Điều>-k<Khoản>-<Điểm>` để truy vết trực tiếp.
- Alias **không nằm trong record**; tách ở `data/catalog/aliases.json`.
- `legal_basis.document` luôn là văn bản gốc 168; sửa đổi ghi ở `version.amended_by`.
- `penalty_rule_ids` truy vết hình phạt bổ sung/trừ điểm về bảng quy tắc.
- Hình phạt có điều kiện có thêm `condition`; UI phải hiển thị "có thể bị... nếu...".
- `document_title` và `version.consolidated_as_of` cho biết catalog đang áp dụng bản hợp nhất nào.

**Nguồn sự thật:** các file `data/catalog/*.jsonl` (dễ review, dễ diff). SQLite và Chroma được build lại bằng script, không sửa tay.

## 7. Luồng trả lời

1. **Chuẩn hóa:** lowercase, bỏ dấu (tùy chọn), từ điển teencode, tách câu.
2. **Trích xuất slot:** `vehicle_type` (xe máy/ô tô), `behavior`, `intent` (tra mức phạt / thủ tục / khác).
3. **Định tuyến:**
   - `penalty_lookup` → tìm top-k ứng viên trong catalog (BM25 + embedding trên `behavior_text` + `aliases`).
   - `procedure` → RAG trên văn bản thủ tục.
   - Thiếu loại xe → hỏi lại, không đoán.
4. **Chọn bản ghi:** LLM chọn ứng viên khớp nhất; nếu độ tin cậy thấp → hỏi lại hoặc từ chối.
5. **Soạn câu trả lời:** template cố định cho phần con số; LLM chỉ viết phần diễn giải.
6. **Guardrail:** bắt buộc có căn cứ; không có nguồn → từ chối; hiển thị disclaimer.

### 7.1. Định dạng câu trả lời

- **Mức phạt:** `[min] – [max] VNĐ`
- **Hình phạt bổ sung:** tước GPLX, tạm giữ...
- **Trừ điểm GPLX:** số điểm (nếu có)
- **Căn cứ:** văn bản + điều/khoản/điểm
- **Lưu ý:** thẩm quyền, thời hạn, ngoại lệ (nếu có)
- **Nguồn:** link/trích đoạn
- **Disclaimer:** "Thông tin tham khảo, không thay thế tư vấn pháp lý."

### 7.2. Các trường hợp đặc biệt

| Tình huống | Hành vi chatbot |
|---|---|
| Thiếu loại xe | Hỏi: "Bạn đi xe máy hay ô tô?" |
| Hành vi mơ hồ | Đưa 2–3 khả năng gần nhất để chọn |
| Không tìm thấy | Nói rõ chưa có dữ liệu + gợi ý tra văn bản gốc |
| Câu hỏi ngoài phạm vi | Từ chối lịch sự, nêu phạm vi hỗ trợ |
| Provider LLM lỗi | Vẫn trả kết quả structured + link văn bản; phần diễn giải tạm ẩn |

## 8. Pipeline thu thập và xử lý dữ liệu

| Bước | Việc làm | Output | Quality gate |
|---|---|---|---|
| 1. Thu thập | Tải PDF/HTML từ nguồn chính thức | `data/raw/` | Có URL, ngày tải, số ký hiệu |
| 2. Parse | Chuyển sang text, giữ cấu trúc Điều/Khoản/Điểm | `data/parsed/` | Không mất dòng, kiểm tra thủ công 10% |
| 3. Trích xuất | LLM + JSON schema trích hành vi, mức phạt, căn cứ | `data/catalog/draft/` | Mỗi bản ghi có `source_quote` |
| 4. Kiểm chứng | Rule + người đối chiếu từng con số | `data/catalog/verified/` | 100% mức tiền được review; quy tắc 2 người cho số tiền |
| 5. Chuẩn hóa | Alias, nhóm hành vi, loại xe | Catalog hoàn chỉnh | Không trùng ID; alias không xung đột |
| 6. Build index | SQLite + FTS5 (Chroma/BM25 ở giai đoạn sau) | `data/build/` | Build tái lập được từ catalog |
| 7. Regression | Chạy golden set | Báo cáo | Không giảm điểm so với baseline |

**Ước lượng quy mô:** khoảng 150–300 bản ghi hành vi cho xe máy + ô tô (cần kiểm chứng khi trích xuất thực tế).

**Quy tắc vàng:** một bản ghi chỉ được `verified` khi:
- Có `source_url` và `source_quote` khớp nguyên văn.
- `fine_min <= fine_max`.
- Căn cứ tồn tại trong văn bản.
- Đã đối chiếu phiên bản hiệu lực tại ngày tra cứu.

## 9. Đánh giá và thí nghiệm

### 9.1. Golden set

Khoảng **200–300 câu**, gồm:

| Nhóm | Số lượng dự kiến | Mục đích |
|---|---|---|
| Tra mức phạt xe máy | 60–80 | Độ đúng số tiền + căn cứ |
| Tra mức phạt ô tô | 60–80 | Độ đúng số tiền + căn cứ |
| Thủ tục nộp phạt/khiếu nại | 40–50 | Chất lượng RAG + trích dẫn |
| Thiếu thông tin/ngoài phạm vi | 20–30 | Hỏi lại/từ chối đúng |
| Teencode/không dấu | 20–30 | Độ bền của chuẩn hóa |

Mỗi case gồm: câu hỏi, `expected_violation_id`, `expected_fine`, `expected_legal_basis`, `expected_answer_type`.

### 9.2. Metrics

- **Exact fine match:** cả `min` và `max` đúng.
- **Citation accuracy:** đúng văn bản + điều/khoản/điểm.
- **Retrieval recall@5:** bản ghi đúng nằm trong top-5.
- **Intent accuracy** và **slot extraction accuracy**.
- **Clarification/refusal accuracy.**
- **Hallucination rate:** số câu trả lời có số tiền/căn cứ không tồn tại.
- **Latency p95.**

Mục tiêu MVP: exact fine ≥ 90%, citation ≥ 95%, hallucination = 0 trên bộ test.

### 9.3. Thí nghiệm cho báo cáo

| Thí nghiệm | Biến | Câu hỏi nghiên cứu |
|---|---|---|
| Baseline 1 | RAG thuần trên văn bản luật | RAG có đủ chính xác cho câu hỏi số tiền? |
| Baseline 2 | Structured lookup + template | Không dùng LLM thì được bao nhiêu? |
| Đề xuất | Hybrid + router | Cải thiện độ đúng và độ ổn định bao nhiêu? |
| Ablation 1 | Dense vs BM25 vs hybrid | Retrieval nào tốt nhất với tiếng Việt pháp lý? |
| Ablation 2 | Chunk theo điều vs theo khoản/điểm | Chunk nào giữ ngữ cảnh tốt hơn? |
| Ablation 3 | Có/không reranker | Reranker có đáng chi phí? |
| Ablation 4 | Có/không chuẩn hóa alias/teencode | Ảnh hưởng đến tỷ lệ khớp hành vi |

Phần này là điểm mạnh để viết báo cáo: không chỉ "làm chatbot", mà **so sánh kiến trúc có đo lường**.

## 10. Roadmap 8 tuần

| Tuần | Mốc | Kết quả bàn giao |
|---|---|---|
| 1 | Chốt đề tài, nguồn luật, schema | Brief + danh sách văn bản + schema |
| 2 | Trích xuất 30 bản ghi mẫu | Catalog mẫu đã verify + script parse |
| 3 | Hoàn thiện catalog xe máy/ô tô | Catalog + bộ test sơ bộ |
| 4 | RAG baseline + UI chat | Demo trả lời câu hỏi thủ tục |
| 5 | Structured lookup + router | Demo tra mức phạt chính xác |
| 6 | Clarification + guardrail + thủ tục | Luồng hỏi lại/từ chối hoàn chỉnh |
| 7 | Chạy golden set + ablation | Bảng kết quả + phân tích lỗi |
| 8 | Đóng gói, viết báo cáo, demo | Repo hoàn chỉnh + slide |

## 11. Phân công và cấu trúc repo

### 11.1. Vai trò

| Vai trò | Việc chính |
|---|---|
| Data/Legal | Thu thập văn bản, trích xuất, kiểm chứng số tiền, alias |
| Backend/RAG | Pipeline, retrieval, router, API |
| Frontend | Chat UI, answer card, hiển thị nguồn |
| Eval/PM | Golden set, metrics, báo cáo, demo script |

Nếu nhóm 3 người: gộp Data + Eval, Backend + RAG, Frontend + tích hợp.

### 11.2. Cấu trúc repo đề xuất

```
chatbot-atgt/
├── docs/
│   └── project-brief.md
├── data/
│   ├── raw/              # PDF/HTML gốc
│   ├── parsed/           # text đã parse
│   ├── catalog/          # JSONL đã verify (nguồn sự thật)
│   └── eval/             # golden set
├── src/
│   ├── ingestion/        # parse + extract
│   ├── catalog/          # schema + loader
│   ├── retrieval/        # BM25 + vector + fusion
│   ├── agent/            # router + answer composer
│   ├── api/              # FastAPI
│   └── web/              # Next.js
├── scripts/              # build_index, run_eval
├── tests/
├── .env.example
└── README.md
```

## 12. Rủi ro và nguyên tắc

| Rủi ro | Cách giảm |
|---|---|
| Sai số tiền do trích xuất | 100% review thủ công; rule validate; test golden |
| Dùng văn bản hết hiệu lực | Versioning + kiểm tra ngày hiệu lực trước khi trả lời |
| LLM bịa căn cứ | Số tiền/căn cứ chỉ lấy từ DB; bắt buộc trích dẫn |
| Câu hỏi mơ hồ | Hỏi lại thay vì đoán |
| Scope creep | Giữ đúng xe máy + ô tô trong MVP |
| Provider API lỗi | Structured path + fallback + cache |
| Dữ liệu luật thay đổi | Diff catalog + chạy lại regression trước khi phát hành |

**5 nguyên tắc:**

1. Không có nguồn → không trả lời.
2. Con số không do LLM sinh.
3. Thiếu slot → hỏi lại.
4. Mọi bản ghi phải truy vết được.
5. Thay đổi luật = thay đổi dữ liệu có version, không sửa tay lặng lẽ.

## 13. Việc cần chốt với nhóm

- [ ] Deadline nộp và thời gian demo.
- [ ] Số thành viên và kỹ năng frontend.
- [ ] Có yêu cầu demo offline không (nếu có, chuẩn bị Ollama + model local).
- [ ] Thủ tục nộp phạt/khiếu nại làm ngay trong MVP hay để giai đoạn 2.
- [ ] Định dạng báo cáo/slide của môn học.

### Trạng thái và việc tiếp theo (10/11/2026)

**Đã xong:**

- Thu thập 168/2024, 238/2026, Luật 36/2024 hợp nhất.
- Parse 1.242 điều/khoản/điểm; trích xuất 271 bản ghi cho Điều 6, 7, 12 (người được chở), 13, 14, 18, 32.
- Hợp nhất 238/2026; validation 0 lỗi, còn cảnh báo các record chưa có alias.
- 44 nhóm alias / 285 cách nói, gồm nhóm vượt đèn đỏ gây tai nạn, bốn nhóm cho người được chở và chín nhóm thiết bị/điều kiện xe.
- Build SQLite + FTS5 và CLI tra thử (`scripts/query_catalog.py`), có phân biệt chủ phương tiện/người điều khiển và mức phạt tổ chức.
- Đối chiếu khung tiền, loại xử phạt và căn cứ của 271 bản ghi bằng `scripts/audit_fines.py`. Kết quả chi tiết lưu trong `data/catalog/review/fine-audit-2026-11-10.csv`.
- Thu thập 23 đoạn thủ tục và chạy golden set 254 câu. Cách chạy và số đo ở [`data/eval/README.md`](../data/eval/README.md).
- Có `GET /health` và `POST /chat` cho hai nhánh mức phạt và thủ tục. Backend hiện dùng truy xuất SQLite/FTS5 và soạn câu trả lời từ bản ghi có nguồn.
- API trả `penalty.source_quote` (đoạn luật áp dụng), `options` (phương án hỏi lại) và `related` (bản ghi tương ứng cho loại xe còn lại khi xác định duy nhất). Client có thể gửi `record_id` để tra thẳng phương án đã chọn.
- Có giao diện Next.js tại `src/web`, hiển thị thẻ mức phạt, đoạn luật áp dụng, đoạn thủ tục, nguồn, nút chọn phương án hỏi lại và nút so sánh loại xe còn lại.

**Việc tiếp theo:**

1. Hai người điền phiếu rà soát độc lập cho 259 bản ghi có phạt tiền, rồi chạy `scripts/merge_reviews.py --fine-only` để chuyển `verified` và lưu snapshot vào `data/catalog/verified/`. Script đã chặn thiếu bản ghi, trùng người và lệch số tiền.
2. Bổ sung phần còn thiếu của Điều 32 (khoản 5–6 phạt theo số người vượt quá có trần; điểm 238/2026 thêm mới 9a/11.e/13.e), sau đó cân nhắc Điều 17 và 20–24.
3. Cải thiện baseline CLI: recall@5 hiện 86/182, trả lời được 42/182; API đã đạt 182/182 trên golden set. Mở rộng định tuyến cho cách nói tự nhiên và câu hỏi phức tạp.
4. Đánh giá chất lượng câu trả lời thủ tục có trích dẫn (không chỉ recall@5) và bổ sung corpus nếu thiếu.
