# CFA Quiz — App ôn thi CFA (Streamlit)

Web app luyện đề trắc nghiệm CFA, **chia theo môn**. Mỗi môn gồm nhiều đề; mỗi
đề chấm ngay từng câu kèm giải thích, có *làm lại câu sai* / *làm lại full*, và
**lưu tiến độ trên trình duyệt** (không cần đăng nhập).

Thêm đề mới = thả 1 file JSON vào `content/<môn>/` rồi push — app tự cập nhật,
**không phải sửa code**.

## Chạy local

```bash
cd cfa-quiz-app
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Mở http://localhost:8501.

## Cấu trúc

```
streamlit_app.py     # entrypoint + router
core/                # engine: content (quét đề), progress (localStorage), quiz, ui
views/               # màn hình: home / subject / quiz / result / review
content/             # ★ DỮ LIỆU — mỗi folder = 1 môn, mỗi *.json = 1 đề
  <môn>/_subject.json    # tên, icon, %weight, mô tả của môn
  <môn>/<đề>.json        # 1 đề: {name, group, questions:[...]}
tools/               # xlsx_to_json (Excel→JSON), validate, make_template, migrate_equity
schema/exam.schema.json
docs/ADD_EXAM.md     # hướng dẫn thêm đề (đọc cái này khi thêm nội dung)
```

Cách app đọc dữ liệu: mỗi thư mục trong `content/` là một **môn** (metadata ở
`_subject.json`), mỗi file `*.json` còn lại là một **đề**. File JSON lỗi sẽ bị
bỏ qua và liệt kê ở mục *"⚠️ vấn đề dữ liệu"* trong sidebar, không làm sập app.

## Thêm đề mới (tóm tắt)

```bash
# 1. Điền câu hỏi vào tools/template.xlsx (mỗi sheet/exam_id = 1 đề)
# 2. Convert sang JSON:
python tools/xlsx_to_json.py duong_dan/de_moi.xlsx --subject economics
# 3. Kiểm tra hợp lệ:
python tools/validate.py
# 4. Commit & push -> Streamlit Cloud tự deploy
git add content/ && git commit -m "Add economics exams" && git push
```

Chi tiết từng bước (kèm mô tả cột) xem **[docs/ADD_EXAM.md](docs/ADD_EXAM.md)**.

## Deploy lên Streamlit Community Cloud

1. Đẩy thư mục `cfa-quiz-app/` lên GitHub (PDF gốc **không** được commit — đã
   để trong `.gitignore`).
2. Vào https://share.streamlit.io → **New app** → chọn repo/branch → *Main file*
   = `streamlit_app.py` → **Deploy**.
3. Mỗi lần push thay đổi `content/`, Cloud tự build lại và đề mới xuất hiện.

## Lưu tiến độ

Tiến độ (đã làm đề nào, câu sai…) lưu trong **localStorage của trình duyệt** —
riêng từng máy, không cần backend, còn nguyên sau khi refresh. Sidebar có
**Tải / Nạp tiến độ** (file JSON) để sao lưu hoặc chuyển sang máy khác, và nút
**Xoá toàn bộ tiến độ**.

> Lưu ý: localStorage gắn với từng trình duyệt/thiết bị; xoá site data sẽ mất
> tiến độ. Nếu sau này cần đồng bộ đa thiết bị / theo tài khoản, có thể nâng cấp
> sang đăng nhập + database (xem mục "Hướng phát triển").

## Hướng phát triển (tùy chọn, sau này)

- GitHub Action chạy `tools/validate.py` mỗi pull request để chặn data lỗi.
- Tóm tắt tiến độ theo môn / "học tiếp đề đang dở" ở trang chủ.
- Tìm kiếm & lọc đề; gắn LOS/độ khó qua `tags`.
- Đăng nhập + đồng bộ tiến độ qua cloud (Supabase / Google Sheet).
