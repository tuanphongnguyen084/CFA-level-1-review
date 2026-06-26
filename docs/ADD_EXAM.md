# Thêm đề mới

Có 2 cách. **Cách 1 (Excel/CSV) là khuyến nghị** cho người không code.

---

## Cách 1 — Từ Excel/CSV (khuyến nghị)

### Bước 1. Điền câu hỏi

Mở **`tools/template.xlsx`** (sheet `questions`). Mỗi dòng là 1 câu hỏi.
Các câu có cùng `exam_id` sẽ gộp thành **1 đề**.

| Cột | Bắt buộc | Ý nghĩa |
|---|---|---|
| `exam_id` | ✅ | Mã đề, dùng làm tên file. VD `reading-1`, `mock-1-s1`. Cùng mã = cùng đề. |
| `exam_name` |  | Tên hiển thị. Trống → lấy bằng `exam_id`. |
| `group` |  | Tiêu đề nhóm hiển thị trong môn (VD "Reading 39–46"). |
| `question` | ✅ | Nội dung câu hỏi. |
| `A`, `B` | ✅ | Đáp án A, B. |
| `C`, `D` |  | Đáp án C, D (để trống nếu không có). |
| `answer` | ✅ | Đáp án đúng: đúng 1 chữ `A`/`B`/`C`/`D`. |
| `explanation` |  | Lời giải (hiện sau khi chấm). |
| `tags` |  | Nhãn, cách nhau bằng `;` hoặc `,` (VD `LOS 39.a; dễ`). |

> Mẹo: 1 file Excel có thể chứa **nhiều đề** — cứ đổi `exam_id` sang nhóm dòng
> tiếp theo. Cũng có thể tách mỗi đề thành 1 sheet riêng.
>
> Nếu dùng CSV cho tiếng Việt: lưu **UTF-8** (Excel: *Save As → CSV UTF-8*).

### Bước 2. Convert sang JSON

```bash
python tools/xlsx_to_json.py duong_dan/de_cua_ban.xlsx --subject economics
```

- `--subject` là **tên thư mục môn** trong `content/` (xem bảng bên dưới).
- Thêm `--dry-run` để thử mà chưa ghi file.
- Lệnh tạo `content/<subject>/<exam_id>.json` cho mỗi đề.

Tên thư mục các môn:

| Môn | `--subject` |
|---|---|
| Ethics | `ethics` |
| Quantitative Methods | `quant` |
| Economics | `economics` |
| Financial Statement Analysis | `fsa` |
| Corporate Issuers | `corporate` |
| Equity | `equity` |
| Fixed Income | `fixed-income` |
| Derivatives | `derivatives` |
| Alternative Investments | `alternatives` |
| Portfolio Management | `portfolio` |
| Mock Exams | `mock` |

(Muốn thêm môn mới? Tạo thư mục `content/<tên>/` và file `_subject.json` trong
đó — xem mẫu ở bất kỳ môn nào.)

### Bước 3. Kiểm tra

```bash
python tools/validate.py
```

Phải báo `0 file lỗi`. Nếu có lỗi (đáp án không khớp, thiếu trường…), nó chỉ rõ
file và dòng để sửa.

### Bước 4. Đẩy lên & deploy

```bash
git add content/
git commit -m "Add economics exams"
git push
```

Streamlit Cloud tự build lại; đề mới xuất hiện trong môn tương ứng.

---

## Cách 2 — Viết tay JSON

Tạo file `content/<subject>/<exam_id>.json`:

```json
{
  "schema_version": 1,
  "id": "reading-1",
  "name": "Reading 1 — Tên đề",
  "group": "Nhóm hiển thị (tuỳ chọn)",
  "questions": [
    {
      "id": "r1-q1",
      "question": "Nội dung câu hỏi?",
      "options": { "A": "...", "B": "...", "C": "..." },
      "answer": "B",
      "explanation": "Vì sao B đúng.",
      "tags": ["LOS 1.a"]
    }
  ]
}
```

Quy tắc: `options` có ≥ 2 lựa chọn; `answer` phải là 1 key có trong `options`.
Hỗ trợ A/B/C và cả A/B/C/D. Chạy `python tools/validate.py` trước khi push.

---

## Reset / sửa đề

- **Sửa**: chỉnh file JSON (hoặc Excel rồi convert lại — sẽ ghi đè), validate, push.
- **Xoá đề**: xoá file `.json` tương ứng rồi push.
- **Xoá tiến độ người dùng**: nút *"🗑️ Xoá toàn bộ tiến độ"* trong sidebar
  (mỗi người tự xoá trên trình duyệt của họ).
