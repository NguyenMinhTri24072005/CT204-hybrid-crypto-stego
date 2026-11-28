# Khung lai Mật mã – Giấu tin cho Truyền ảnh An toàn

Đồ án học phần **CT204 – An toàn và Bảo mật Thông tin**, Trường CNTT&TT, Đại học Cần Thơ.

Dự án tái hiện bằng Python bài báo *"A Hybrid Crypto-Steganography Framework for Secure Image Transfer"* (Raut et al., ICITSC 2025). Bản gốc của bài báo được viết bằng MATLAB R2024a.

Quy trình gồm ba bước:
1. Mã hóa một ảnh bí mật xám bằng một trong ba thuật toán: **3DES**, **AES** hoặc **Chaotic + PRNG Masking**.
2. Giấu bản mã vào 1–3 bit thấp (LSB) của một ảnh phủ RGB 256×256.
3. Trích xuất, giải mã, khôi phục ảnh và đo các chỉ số để so với Bảng 2 của bài báo.

| | |
|---|---|
| Sinh viên | Nguyễn Minh Trí – B2308398 – K49, Khoa học máy tính |
| Giảng viên hướng dẫn | ThS. Phan Bích Chung |
| Ngôn ngữ / môi trường | Python 3.12 · Windows · Tkinter (chạy offline) |

---

## Điểm nổi bật

- **Ba thuật toán chung một giao diện** (Strategy pattern, `BaseCipher`):
  - 3DES-192 CBC (EDE);
  - AES-128 CBC (PKCS#7);
  - ánh xạ logistic hỗn loạn (`x0 = 0.785398`, `r = 3.999`) XOR với mặt nạ PRNG mô phỏng ECC, biên dịch bằng Numba.
- **Giấu tin LSB đa bit, vector hóa hoàn toàn bằng NumPy:**
  - tự chọn số bit `k ∈ {1, 2, 3}` nhỏ nhất đủ chứa dữ liệu;
  - nếu 3 bit vẫn không đủ thì phóng to ảnh phủ (INTER_CUBIC).
- **Header 16 byte có CRC**, luôn nhúng ở 1 LSB. Khi giải chỉ cần ảnh stego và khóa; khóa không bao giờ nằm trong ảnh.
- **Đo theo hai mục tiêu** (bí mật ↔ bản mã và phủ ↔ stego), vì bài báo không nói rõ đo trên ảnh nào.
- **Benchmark trên toàn bộ 8.000 ảnh Linnaeus 5 × 3 thuật toán**, tức 24.000 lượt chạy, khôi phục đúng 100%.
- **Ứng dụng desktop 4 tab**:
  - mã hóa;
  - giải mã kèm *Tamper Lab* (sửa ảnh, đổi khóa);
  - so sánh 3 thuật toán;
  - dashboard 8.000 ảnh.

  Ứng dụng đóng gói được thành `.exe` chạy không cần cài Python.
- **347 bài kiểm thử** pytest.

---

## Cấu trúc thư mục

```text
Project/                         ← gốc repository git
├── README.md                    ← tệp này
├── CLAUDE.md                    ← hướng dẫn cho tác nhân AI
├── Docs/                        ← bài báo gốc (145987.pdf) + bản markdown + hình trích xuất
├── Plans/                       ← đặc tả kỹ thuật, kế hoạch, 10 "điểm mù" của bài báo (ADR), đặc tả UI
├── Reports/
│   ├── Refers/                  ← báo cáo mẫu của giảng viên
│   └── My_reports/
│       ├── Latex/               ← báo cáo LaTeX (main.tex → main.pdf), xem README riêng
│       └── Slide/               ← slide thuyết trình (.pptx)
└── SOURCES/                     ← toàn bộ mã nguồn Python (xem SOURCES/README.md)
    ├── app.py                   ← ứng dụng desktop Tkinter
    ├── configs/default.yaml     ← nguồn tham số duy nhất
    ├── src/                     ← crypto/, stego/, metrics/, pipeline.py, ui/
    ├── scripts/                 ← run_single.py, run_benchmark.py
    ├── tests/                   ← 347 bài kiểm thử
    ├── notebooks/               ← visualize_results.ipynb
    ├── packaging/               ← ct204_app.spec (PyInstaller)
    ├── data/                    ← sample/ (ảnh mẫu), linnaeus5/ (tự tải, không commit)
    └── results/                 ← CSV benchmark + ảnh demo
```

---

## Bắt đầu nhanh (Windows, PowerShell)

Mọi lệnh đều chạy trong thư mục `SOURCES/` và dùng môi trường ảo `.venv`. Không dùng `python` của hệ thống.

**1. Tạo môi trường ảo** (Python 3.12) và cài thư viện:

```powershell
cd SOURCES
```
```powershell
py -3.12 -m venv .venv
```
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Nếu dùng `pyenv-win` thay cho `py` launcher, chạy `python -m venv .venv`: tệp `.python-version` đã chọn sẵn Python 3.12.8.

**2. Chạy kiểm thử:**

```powershell
.\.venv\Scripts\pytest.exe -q
```

**3. Chạy demo một cặp ảnh** (ảnh, histogram và `single_metrics.csv` được ghi vào `results/single/`):

```powershell
.\.venv\Scripts\python.exe -m scripts.run_single
```

**4. Mở ứng dụng desktop:**

```powershell
.\.venv\Scripts\python.exe app.py
```

Nếu thiếu `data/sample/secret.png`, chương trình tự tạo ảnh *coins* 246×300 (giống `coins.png` của MATLAB) từ `skimage.data.coins()`.

---

## Bộ dữ liệu Linnaeus 5 (cho benchmark)

Tải tại <http://chaladze.com/l5/> (bản 256×256). Giải nén vào `SOURCES/data/linnaeus5/` theo cấu trúc sau:

```text
data/linnaeus5/
├── train/{berry,bird,dog,flower,other}/   ← 1.200 ảnh mỗi lớp
└── test/{berry,bird,dog,flower,other}/    ← 400 ảnh mỗi lớp
```

Thư mục này đã được `.gitignore` bỏ qua. Lệnh tái hiện Bảng 2 (ảnh bí mật 156×156, lấp ≈ 99% sức chứa 1-LSB):

```powershell
.\.venv\Scripts\python.exe -m scripts.run_benchmark --secret-size 156 156 --cache-chaotic-mask
```

Kết quả được ghi vào `results/benchmark_results.csv` (từng ảnh) và `results/benchmark_summary_table2.csv` (trung bình). Các tùy chọn khác như `--limit`, `--vary-key-per-image`, `--out-dir` và `--quiet` được liệt kê trong [SOURCES/README.md](SOURCES/README.md).

---

## Kết quả chính (8.000 ảnh, 1-LSB)

| Chỉ số | Bài báo (3DES / AES / Chaotic) | Dự án này (3DES / AES / Chaotic) |
|---|---|---|
| MSE | ≈ 0,50 | 0,4956 / 0,4958 / 0,4954 |
| PSNR (dB) | ≈ 51,15 | 51,18 / 51,18 / 51,18 |
| SSIM | ≈ 0,998 | 0,9969 (cả ba) |
| EncTime (s) | 3,55e-3 / 6,0e-4 / 3,6e-5 | 1,30e-3 / 1,11e-4 / 3,13e-5 |
| NPCR (%) | ≈ 99,6 | 99,65 / 99,58 / 99,56 |
| UACI (%) | 30,8 – 31,0 | 30,33 / 30,35 / 30,51 |
| Hệ số tương quan | ≈ 0 | 0,006 / −0,001 / −0,013 |
| Entropy | 7,05 / 7,05 / 6,95 | bản mã: 7,993 · ảnh stego: 7,466 |

Tỷ lệ khôi phục chính xác là **100%** ở cả 24.000 lượt chạy (MSE giữa ảnh bí mật và ảnh khôi phục bằng 0).

Ghi chú:
- MSE ≈ 0,5 và PSNR ≈ 51,1 dB đúng bằng giá trị lý thuyết khi nhúng 1-LSB một chuỗi bit ngẫu nhiên lấp đầy ảnh phủ.
- Entropy ≈ 7,0 trong bài báo không khớp với bản mã (≈ 8). Báo cáo phân tích lệch này cùng các điểm khác ở Chương 3.
- Báo cáo còn có các thử nghiệm mở rộng:
  - độ nhạy khóa và độ nhạy bản rõ;
  - tấn công biết bản rõ lên Chaotic (khôi phục được hoàn toàn);
  - Tamper Lab;
  - phân tích giấu tin χ²: 99,84% ảnh stego bị phát hiện.

---

## Ứng dụng desktop và bản `.exe`

| Tab | Chức năng |
|---|---|
| 1. Mã hóa & Giấu tin | Chọn ảnh phủ, ảnh bí mật, thuật toán và chế độ khóa, rồi xuất ảnh stego PNG |
| 2. Giải mã & Tamper Lab | Trích xuất và giải mã; thử sửa pixel hoặc dùng sai khóa để xem hệ thống phát hiện |
| 3. So sánh 3 Thuật toán | Chạy cả ba thuật toán trên cùng một cặp ảnh và so chỉ số, histogram |
| 4. Dashboard 8.000 ảnh | Đọc CSV benchmark và vẽ biểu đồ |

Ứng dụng có hai chế độ khóa:
- **Seed chuẩn**: khóa sinh từ `configs/default.yaml`, cho kết quả trùng với script;
- **Passphrase**: khóa sinh từ SHA-256 của mật khẩu.

Ảnh stego chỉ lưu dạng PNG, vì JPEG phá hủy các bit LSB.

Đóng gói thành thư mục độc lập `dist/CT204_CryptoStego/`:

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
```
```powershell
.\.venv\Scripts\pyinstaller.exe packaging\ct204_app.spec
```

Để kiểm tra nhanh khả năng khởi động (dựng đủ 4 tab rồi tự thoát):

```powershell
.\.venv\Scripts\python.exe app.py --smoke
```

---

## Báo cáo

Báo cáo LaTeX nằm ở [`Reports/My_reports/Latex/`](Reports/My_reports/Latex/README.md) và được biên dịch bằng **XeLaTeX → BibTeX → XeLaTeX ×2**, kết quả là `main.pdf`.

Các script trong `Reports/My_reports/Latex/tools/` sinh lại toàn bộ hình và số liệu bổ sung của báo cáo từ CSV kết quả.

## Tài liệu liên quan

- [`Docs/145987.md`](Docs/145987.md) – nội dung bài báo gốc dạng markdown.
- [`Plans/README.md`](Plans/README.md) – mục lục đặc tả kỹ thuật, kế hoạch và các quyết định thiết kế.
- [`SOURCES/README.md`](SOURCES/README.md) – chi tiết mã nguồn, cấu hình, CLI và kiểm thử.

## Tham khảo

S. D. Raut, S. P. Ugale, D. M. Chandwadkar, "A Hybrid Crypto-Steganography Framework for Secure Image Transfer", *Proceedings of ICITSC 2025*, vol. 2, pp. 175–182, SCITEPRESS.
