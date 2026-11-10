# Kết quả rà soát 30 dòng ngày 10/11/2026

Phiếu: `spotcheck-2026-11-10-ai-review.csv`. Người rà soát: **Codex (AI)**.

Đối chiếu trực tiếp hai TXT Nghị định 168 và DOCX Nghị định 238 do người dùng cung cấp. Áp dụng sửa đổi có hiệu lực từ 15/08/2026 theo Điều 20 khoản 1 NĐ 238, tại mốc rà soát 10/11/2026. Đây là kiểm tra dữ liệu trên các tài liệu được cung cấp; không xác thực chữ ký hay tính đầy đủ của các sửa đổi ngoài bộ tài liệu này.

## Cách điền

- Chỉ điền 8 cột rà soát. Giữ nguyên 17 cột dữ liệu có sẵn, kể cả `verification_status=draft`.
- `fine_ok`: khung tiền và câu mức phạt khớp nguồn; `expected_fine_min/max` là mức cá nhân tại các khoản có cả cá nhân và tổ chức. Mức tổ chức ghi riêng trong `note`.
- `citation_ok`: địa chỉ Điều/khoản/điểm đúng với hành vi; khi câu chữ đổi, ghi thêm căn cứ sửa đổi trong `note`.
- `text_ok`: `behavior_text` và `source_quote` khớp nguồn sau sửa đổi, bỏ qua xuống dòng/dàn trang. Điểm, hình phạt bổ sung và khắc phục được nhận xét riêng trong `note` vì phiếu không có cột chấm riêng cho chúng.
- 30/30 dòng có ba kết quả `OK`. Điều này xác nhận ba nội dung trên, không đồng nghĩa mọi mô tả chế tài phụ đều đầy đủ.
- Không dùng kết quả AI này làm xác nhận của người rà soát độc lập hoặc tự đổi trạng thái thành `verified`.

## Những nội dung cần chú ý

- `nd168-d13-k6-a`: mô tả thu hồi trong `remedial_measures` còn thiếu giấy chứng nhận/tem kiểm định không do cơ quan có thẩm quyền cấp ở khoản 12 Điều 13. Điều kiện thu hồi đăng ký cũng cần giữ đầy đủ. Điểm d khoản 11 quy định riêng việc nộp lại giấy bị tẩy xóa.
- `nd168-d13-k4-a`, `nd168-d13-k6-a`, `nd168-d14-k2-a`, `nd168-d14-k2-b`: nhãn tịch thu rút gọn cần đọc kèm đầy đủ nhánh hành vi và điều kiện nguồn gốc. Khi đủ điều kiện điều luật quy định “bị tịch thu”. Riêng hết hạn/hết hiệu lực không mặc nhiên dẫn đến tịch thu theo quy định này.
- `nd168-d14-k2-b`: nhãn thu hồi đăng ký cần ghi điều kiện không đúng số khung/số máy hoặc không đúng thẩm quyền theo khoản 7 Điều 14; việc nộp lại giấy bị tẩy xóa nằm ở điểm b khoản 6.
- Ba dòng Điều 18: 02 điểm trừ vào GPLX được cấp mới nhất trong hệ thống. Các dòng 32.11.a/b/đ: 02 điểm chỉ áp dụng khi chủ xe trực tiếp điều khiển. Các điều kiện được ghi trong từng dòng.
- Ba dòng 14.1.a/b/c có biện pháp khắc phục là đúng sau Điều 19 khoản 5 NĐ 238. Cụm từ “chứng nhận kiểm định” ở 13.3.d, 13.4.b, 32.1.b và chế tài 32.11.b đúng theo Điều 19 khoản 11 NĐ 238. Hành vi 13.8.b đúng theo Điều 3 NĐ 238.
- Căn cứ thay thế cụm từ trong DOCX được cung cấp là **Điều 19 khoản 11**, không phải Điều 11 khoản 11. Điều 11 của DOCX chỉ có 5 khoản.
- Các hành vi thuộc mẫu đều ở phần 1. Đã đối chiếu thêm khoản 3 Điều 47 ở phần 2 (dòng 450–493): một số hành vi tại Điều 13/14 chuyển sang mức xử phạt tương ứng của Điều 32 nếu chủ xe trực tiếp điều khiển; điều kiện này được ghi ở các dòng liên quan. Điều 50 ở phần 2 quy định nguyên tắc trừ điểm; điểm đ khoản 1 được sửa tại Điều 17 khoản 1 NĐ 238 (DOCX đoạn 187–188). Không có nội dung cần để trống vì thiếu căn cứ sau khi đã nhận DOCX 238.

## Bảng căn cứ

Số dòng tính theo xuống dòng trong TXT gốc; số đoạn DOCX tính theo các phần tử đoạn văn của `word/document.xml`, gồm đoạn trống.

| ID | Vị trí trong TXT | Mức cá nhân (đồng) | Căn cứ đổi hành vi |
|---|---|---|---|
| nd168-d12-k2-d | 168-congbao-part1.txt, dòng 1143 | 200000–250000 | Giữ nguyên hành vi bản gốc |
| nd168-d12-k4 | 168-congbao-part1.txt, dòng 1155 | 350000–400000 | Giữ nguyên hành vi bản gốc |
| nd168-d12-k5-a | 168-congbao-part1.txt, dòng 1161 | 400000–600000 | Giữ nguyên hành vi bản gốc |
| nd168-d12-k5-b | 168-congbao-part1.txt, dòng 1165 | 400000–600000 | Giữ nguyên hành vi bản gốc |
| nd168-d13-k1 | 168-congbao-part1.txt, dòng 1250 | 200000–400000 | Giữ nguyên hành vi bản gốc |
| nd168-d13-k2-a | 168-congbao-part1.txt, dòng 1255 | 400000–600000 | Giữ nguyên hành vi bản gốc |
| nd168-d13-k2-b | 168-congbao-part1.txt, dòng 1261 | 400000–600000 | Giữ nguyên hành vi bản gốc |
| nd168-d13-k2-c | 168-congbao-part1.txt, dòng 1262 | 400000–600000 | Giữ nguyên hành vi bản gốc |
| nd168-d13-k3-a | 168-congbao-part1.txt, dòng 1268 | 1000000–2000000 | Giữ nguyên hành vi bản gốc |
| nd168-d13-k3-d | 168-congbao-part1.txt, dòng 1274 | 1000000–2000000 | 238/2026 Điều 19 khoản 11 (DOCX đoạn 205) |
| nd168-d13-k4-a | 168-congbao-part1.txt, dòng 1280 | 2000000–3000000 | Giữ nguyên hành vi bản gốc |
| nd168-d13-k4-b | 168-congbao-part1.txt, dòng 1288 | 2000000–3000000 | 238/2026 Điều 19 khoản 11 (DOCX đoạn 205) |
| nd168-d13-k6-a | 168-congbao-part1.txt, dòng 1308 | 4000000–6000000 | Giữ nguyên hành vi bản gốc |
| nd168-d13-k8-a | 168-congbao-part1.txt, dòng 1330 | 20000000–26000000 | Giữ nguyên hành vi bản gốc |
| nd168-d13-k8-b | 168-congbao-part1.txt, dòng 1334 | 20000000–26000000 | 238/2026 Điều 3 (DOCX đoạn 33–34) |
| nd168-d14-k1-a | 168-congbao-part1.txt, dòng 1405 | 400000–600000 | Giữ nguyên hành vi bản gốc |
| nd168-d14-k1-b | 168-congbao-part1.txt, dòng 1407 | 400000–600000 | Giữ nguyên hành vi bản gốc |
| nd168-d14-k1-c | 168-congbao-part1.txt, dòng 1408 | 400000–600000 | Giữ nguyên hành vi bản gốc |
| nd168-d14-k2-a | 168-congbao-part1.txt, dòng 1415 | 2000000–3000000 | Giữ nguyên hành vi bản gốc |
| nd168-d14-k2-b | 168-congbao-part1.txt, dòng 1423 | 2000000–3000000 | Giữ nguyên hành vi bản gốc |
| nd168-d18-k5-c | 168-congbao-part1.txt, dòng 1685 | 2000000–4000000 | Giữ nguyên hành vi bản gốc |
| nd168-d18-k7-d | 168-congbao-part1.txt, dòng 1705 | 6000000–8000000 | Giữ nguyên hành vi bản gốc |
| nd168-d18-k8-c | 168-congbao-part1.txt, dòng 1716 | 8000000–10000000 | Giữ nguyên hành vi bản gốc |
| nd168-d32-k1-a | 168-congbao-part1.txt, dòng 2438 | 200000–300000 | Giữ nguyên hành vi bản gốc |
| nd168-d32-k1-b | 168-congbao-part1.txt, dòng 2440 | 200000–300000 | 238/2026 Điều 19 khoản 11 (DOCX đoạn 205) |
| nd168-d32-k10 | 168-congbao-part1.txt, dòng 2604 | 8000000–10000000 | Giữ nguyên hành vi bản gốc |
| nd168-d32-k11-a | 168-congbao-part1.txt, dòng 2616 | 10000000–12000000 | Giữ nguyên hành vi bản gốc |
| nd168-d32-k11-b | 168-congbao-part1.txt, dòng 2622 | 10000000–12000000 | Giữ nguyên hành vi bản gốc |
| nd168-d32-k11-c | 168-congbao-part1.txt, dòng 2626 | 10000000–12000000 | Giữ nguyên hành vi bản gốc |
| nd168-d32-k11-đ | 168-congbao-part1.txt, dòng 2634 | 10000000–12000000 | Giữ nguyên hành vi bản gốc |

## Kiểm tra tệp kết quả

Đã đọc lại CSV bằng bộ đọc CSV: đủ 30 ID, đủ 25 cột, không trùng ID, đủ 8 ô rà soát mỗi dòng, toàn bộ cột dữ liệu nguồn được giữ nguyên. Tệp xuất UTF-8 có BOM để mở bằng Excel.

SHA-256 của tài liệu đầu vào:

- `spotcheck-2026-11-10.csv`: `e5ef2f96f8becfb07450e854e9c90923a02820fb626db051632ab9785801475d`
- `168-congbao-part1.txt`: `e71486839e23d5e200c80afe826dc16ae0570fd829c0a64d982452c9a5cc3bf5`
- `168-congbao-part2.txt`: `f450cc1eb2433d6ec0a1628858211068b61c3583ea9ae2561097a84012a66390`
- `238-2026-nd-cp.docx`: `e103437f9b4489db2b55ea005365c430c9b2711f5ae4bf2bab5c87de6f6c479a`
