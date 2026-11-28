# Báo cáo CT204 — LaTeX

Báo cáo học phần An toàn và Bảo mật Thông tin (CT204): *Khung lai mật mã – giấu tin cho truyền ảnh an toàn*
(tái hiện bài báo Raut et al., ICITSC 2025).

## Biên dịch

Báo cáo **bắt buộc dùng XeLaTeX** (font hệ thống Times New Roman + tiếng Việt qua `polyglossia`);
tài liệu tham khảo dùng **BibTeX** (`unsrtnat`).

### TeXstudio
`main.tex` đã có magic comment `% !TeX TS-program = xelatex` nên TeXstudio tự chọn XeLaTeX.
Nếu không, vào *Options → Configure TeXstudio → Build*:
- *Default Compiler*: **XeLaTeX**
- *Default Bibliography Tool*: **BibTeX**

Trình tự biên dịch lần đầu: **F6** (XeLaTeX) → **F8** (BibTeX) → **F6** → **F6**.
Hoặc chọn *Build & View* (F5) nhiều lần.

### Dòng lệnh / VS Code (LaTeX Workshop)
Thư mục có sẵn `.latexmkrc` (XeLaTeX + BibTeX):
```powershell
latexmk main.tex
```

## Cấu trúc

| Tệp/thư mục | Nội dung |
|---|---|
| `main.tex` | Tệp chính, ghép các phần |
| `thongtin.tex` | **Thông tin cá nhân, tên đề tài, ngày tháng** — sửa ở đây |
| `preamble.tex` | Định dạng: lề, font, tiêu đề chương, bảng, mã nguồn, header/footer |
| `frontmatter/` | Bìa, nhận xét GV, lời cảm ơn, danh mục từ viết tắt |
| `chapters/` | Chương 1–4 (`chuong3.tex` + `chuong3_ketqua.tex`) và phụ lục |
| `references.bib` | Tài liệu tham khảo |
| `figures/` | `common/` (logo), `results/` (ảnh từ `SOURCES/results/single`), `generated/` (biểu đồ do script sinh), `ui/` (ảnh chụp giao diện), `paper/` (hình từ bài báo) |
| `tools/` | Script sinh lại hình và số liệu (chạy bằng venv của `SOURCES`) |

## Sinh lại hình và số liệu

Chạy từ thư mục `SOURCES` (không sửa mã nguồn lõi):
```powershell
.\.venv\Scripts\python.exe ..\Reports\My_reports\Latex\tools\make_figures.py
.\.venv\Scripts\python.exe ..\Reports\My_reports\Latex\tools\make_theory_figures.py
.\.venv\Scripts\python.exe ..\Reports\My_reports\Latex\tools\run_experiments.py
```
`run_experiments.py` ghi toàn bộ số liệu bổ sung (độ nhạy khóa, phân tích vi sai, tấn công biết bản rõ,
tamper lab, kiểm định χ²) vào `tools/out/experiments.json`; các bảng ở mục 3.7–3.8 lấy số từ đây.
Ảnh giao diện được chụp bằng `tools/shoot_ui.py`.
