# Thư mục Quản lý Kế hoạch & Đặc tả Kỹ thuật (`Plans/`)

Thư mục này nằm độc lập bên ngoài `SOURCES/` để lưu trữ toàn bộ **Đặc tả kỹ thuật chuẩn (Single Technical Spec)**, **Hồ sơ xử lý các điểm mù của bài báo (ADR)** và **Kế hoạch điều phối thực hiện dự án** giữa **Bạn (Chủ dự án)**, **Claude Code (Opus)** và **Antigravity (Gemini 4 Neon / Carbon)**.

## Danh mục tài liệu

| STT | Tài liệu | Mục đích sử dụng |
|---|---|---|
| 1 | [01_TECHNICAL_SPEC.md](./01_TECHNICAL_SPEC.md) | **Đặc tả Kỹ thuật Toàn diện (Giai đoạn 1 → 4):** Kiến trúc hệ thống, hợp đồng cấu hình khớp với `SOURCES/configs/default.yaml`, chữ ký class/hàm từng module, giao thức nhị phân LSB Header 16-byte, công thức toán học các độ đo và toàn bộ quy ước kỹ thuật đã chốt. Dùng làm chuẩn duy nhất khi code và review. |
| 2 | [02_EXECUTION_PLAN_AND_ROLES.md](./02_EXECUTION_PLAN_AND_ROLES.md) | **Kế hoạch Thực hiện Chi tiết & Phân công Vai trò:** Bảng theo dõi tiến độ dự án hiện tại (GĐ1 đã hoàn thành bởi Claude Code), ma trận phân việc tối ưu theo thế mạnh từng tác nhân (**Bạn** vs. **Claude Opus** vs. **Gemini Neon/Carbon**), checklist nghiệm thu từng giai đoạn, chuẩn bị dữ liệu và prompt điều phối. |
| 3 | [03_TECHNICAL_BLIND_SPOTS_AND_DECISIONS.md](./03_TECHNICAL_BLIND_SPOTS_AND_DECISIONS.md) | **Hồ sơ 10 Điểm mù Kỹ thuật & Quyết định Thiết kế (ADR):** Liệt kê 10 điểm bài báo gốc bỏ ngỏ hoặc mâu thuẫn nội tại, bằng chứng suy luận ngược từ PDF/Histogram/Table 2, phân tích các phương án đề xuất, phương án tốt nhất được chọn và lý do lựa chọn. Rất hữu ích khi viết phần Phương pháp & Bàn luận của báo cáo CT204. |
| 4 | [04_TKINTER_UI_SPEC_AND_PLAN.md](./04_TKINTER_UI_SPEC_AND_PLAN.md) | **Đặc tả Kỹ thuật & Kế hoạch Ứng dụng Desktop Tkinter + Đóng gói `.exe` (Giai đoạn 6):** Kiến trúc giao diện `tkinter`/`ttk` chạy Offline 100%, tách biệt hoàn toàn khỏi lõi `src/`, hợp đồng 2 chế độ khóa (Seed chuẩn & Passphrase), 4 Tab chức năng (kèm Phòng thí nghiệm Tấn công/Toàn vẹn), kiểm thử tự động và thiết kế đóng gói `.exe` bằng PyInstaller. |

## Cấu trúc tổng thể Repository hiện tại

```text
Project/                                              # Git repository root
├── .antigravity/rules.md                             # Quy tắc ràng buộc cho Antigravity (Gemini)
├── CLAUDE.md                                         # Quy tắc hướng dẫn cho Claude Code (Opus)
├── Docs/
│   ├── 145987.pdf                                    # Bài báo gốc ICITSC 2025
│   ├── 145987.md                                     # Bản đặc tả Markdown rút gọn của bài báo
│   └── 145987_assets/                                # Hình trích xuất từ bài báo (Figures 1–5)
├── Plans/                                            # Hồ sơ quản lý dự án, Spec & ADR
│   ├── README.md                                     # Mục lục hướng dẫn đọc nhanh
│   ├── 01_TECHNICAL_SPEC.md                          # Đặc tả kỹ thuật chi tiết GĐ1–GĐ4
│   ├── 02_EXECUTION_PLAN_AND_ROLES.md                # Lộ trình, tiến độ & phân công Người / Claude / Gemini
│   ├── 03_TECHNICAL_BLIND_SPOTS_AND_DECISIONS.md     # 10 điểm mù bài báo, các đề xuất & lý do chốt thiết kế
│   └── 04_TKINTER_UI_SPEC_AND_PLAN.md                # Đặc tả ứng dụng Desktop Tkinter Offline & kế hoạch đóng gói .exe
└── SOURCES/                                          # Thư mục mã nguồn Python 3.12 + .venv
    ├── .venv/                                        # Virtual environment cục bộ (Python 3.12.8)
    ├── app.py                                        # [GĐ6A] Entry point ứng dụng Desktop Tkinter Offline
    ├── .gitignore                                    # [GĐ1 - Xong] Chặn .venv, dataset; cho phép CSV & single results
    ├── pytest.ini                                    # [GĐ1 - Xong] pythonpath = ., testpaths = tests
    ├── configs/default.yaml                          # [GĐ1 - Xong] Tham số chuẩn toàn hệ thống
    ├── src/config.py                                 # [GĐ1 - Xong] Hàm load_config()
    ├── src/{crypto,stego,metrics}/                   # [GĐ2–GĐ4 - Xong] Các tầng nghiệp vụ lõi
    ├── src/ui/                                       # [GĐ6A] Giao diện Desktop Tkinter (controller, widgets, 4 tabs)
    ├── scripts/                                      # [GĐ4 - Xong] run_single.py & run_benchmark.py
    ├── notebooks/visualize_results.ipynb             # [GĐ5B - Xong] Notebook phân tích & 11 biểu đồ thực nghiệm
    └── tests/                                        # [GĐ2–GĐ6] Unit tests & Integration tests
```
