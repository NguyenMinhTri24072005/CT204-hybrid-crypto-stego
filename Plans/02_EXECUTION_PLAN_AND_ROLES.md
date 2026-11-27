# Kế hoạch Thực hiện Chi tiết & Phân công Vai trò (Project Execution Plan)

Tài liệu này là **bảng điều khiển trung tâm (Master Tracker)** dành cho bạn (người chủ trì đồ án môn CT204) để nắm rõ:
1. Dự án hiện đang ở đâu, cái gì đã xong, cái gì chưa làm.
2. Phân chia công việc tối ưu giữa **Bạn**, **Claude Code (Opus)** và **Antigravity (Gemini 4 Neon / Carbon)** dựa trên bộ đặc tả đã khóa chặt mọi điểm mù tại [01_TECHNICAL_SPEC.md](./01_TECHNICAL_SPEC.md) và [03_TECHNICAL_BLIND_SPOTS_AND_DECISIONS.md](./03_TECHNICAL_BLIND_SPOTS_AND_DECISIONS.md).
3. Từng bước thực hiện, lệnh chạy kiểm tra và điểm chốt Git commit từ nay đến khi hoàn tất báo cáo.

---

## 1. Bảng Theo dõi Trạng thái Dự án Hiện tại (Project Dashboard)

*Cập nhật: 27/11/2026 — Đã hoàn thành toàn bộ Code (GĐ1 → GĐ4) và Chạy xong Thực nghiệm 8,000 ảnh Linnaeus 5 (`24,000/24,000` khôi phục chính xác `MSE == 0`). Chỉ còn bước hoàn thiện Notebook trực quan hóa & README/Báo cáo CT204.*

| Giai đoạn | Hạng mục chính | Trạng thái | Người thực hiện chính | Người Review / Nghiệm thu | Git Commit |
|---|---|---|---|---|---|
| **Khởi tạo & Thiết kế** | Quét bài báo `Docs/145987.pdf`, tạo `.venv` Python 3.12.8, `CLAUDE.md`, `.antigravity/rules.md`, bộ `Plans/` (Spec + Execution Plan + 10 Điểm mù ADR) | ✅ **Hoàn thành** | Bạn + Claude + Gemini | Bạn | `5d04422` |
| **Giai đoạn 1** | Khung cấu hình & môi trường: `SOURCES/.gitignore`, `pytest.ini`, `configs/default.yaml`, `src/config.py`, `scripts/__init__.py`, `.gitkeep` | ✅ **Hoàn thành** | **Claude Code (Opus)** | **Gemini** (pass) + **Bạn** | `5d04422` |
| **Chuẩn bị Data** | Tải đủ Linnaeus 5 (`train=6000`, `test=2000` = **8,000 ảnh**), tạo `secret.png` (`246×300` uint8) & `cover.jpg` (`256×256×3`) | ✅ **Hoàn thành** | **Bạn** | **Gemini** (đã kiểm chứng đủ 8,000 ảnh & kích thước) | `bc009e1` |
| **Giai đoạn 2** | Tầng Mã hóa (`src/crypto/base.py`, `des3_cipher.py`, `aes_cipher.py`, `chaotic_cipher.py`, `__init__.py`) + `tests/test_crypto.py` theo `BM-03, BM-04, BM-05, BM-10` | ✅ **Hoàn thành & Đã Audit** *(`126/126 PASSED`)* | **Claude Code (Opus)** | **Gemini** (pass) + **Bạn** | `08c2b15` |
| **Giai đoạn 3** | Tầng Giấu tin LSB vector hóa (`src/stego/lsb.py` với Header 16B & auto scale-up) + `src/pipeline.py` + `tests/test_lsb.py` & `tests/test_pipeline.py` theo `BM-02, BM-06, BM-07` | ✅ **Hoàn thành & Đã Audit** *(`236/236 PASSED`)* | **Claude Code (Opus)** | **Gemini** (pass) + **Bạn** | `30ce5ac` |
| **Giai đoạn 4** | Tầng Metrics kép (`src/metrics/visual.py`, `security.py`, `__init__.py`) + tích hợp `pipeline.py` + Scripts (`run_single.py`, `run_benchmark.py`) + `tests/test_metrics.py` theo `BM-01, BM-08, BM-09, BM-10` | ✅ **Hoàn thành & Đã Audit** *(`275/275 PASSED`)* | **Gemini (Carbon)** | **Claude Code (Opus)** (audit pass) + **Gemini** (SSIM Gaussian `σ=1.5`) | `93c72e1` |
| **Giai đoạn 5A (Thực nghiệm)** | Chạy `run_single` (Hình 4–5) & `run_benchmark` trên **8,000 ảnh Linnaeus 5** (`24,000` lượt chạy, khôi phục `100%`) | ✅ **Hoàn thành** | **Bạn** | **Gemini** (đã kiểm chứng & đối chiếu Bảng 2) | Mở chặn trong `.gitignore` để push lên GitHub |
| **Giai đoạn 5B (Notebook & Đóng gói)** | Viết & thực thi `SOURCES/notebooks/visualize_results.ipynb` (nạp dữ liệu từ GitHub clone, 11 biểu đồ đa chiều & bảng tổng hợp) | ✅ **Hoàn thành** | **Gemini (Carbon)** | **Bạn** kiểm tra, `git push` & viết báo cáo CT204 | ⏳ Sẵn sàng `git commit` & `git push` |

---

## 2. Chiến lược Phân công Vai trò (Ai làm gì tốt nhất?)

Áp dụng mô hình **"1 bên Code chính — 1 bên Audit/Test chéo — Bạn giữ quyền Chốt Git & Dữ liệu"**:

### 👤 Vai trò 1: BẠN (Project Owner / System Integrator)
- **Quyền hạn duy nhất:** Quyết định chuyển giai đoạn, thực hiện `git add` / `git commit` / `git push` sau mỗi giai đoạn pass test.
- **Công việc trực tiếp:**
  1. Tải bộ dataset **Linnaeus 5 (`256×256`, 8,000 ảnh)** đặt vào `SOURCES/data/linnaeus5/{train,test}/{berry,bird,dog,flower,other}/` và tạo ảnh `secret.png` chuẩn `246×300`.
  2. Chạy nghiệm thu thực nghiệm 8,000 ảnh trên máy cá nhân với các kịch bản cấu hình đã định.
  3. Viết báo cáo môn học CT204 (tận dụng trực tiếp các phân tích trong [03_TECHNICAL_BLIND_SPOTS_AND_DECISIONS.md](./03_TECHNICAL_BLIND_SPOTS_AND_DECISIONS.md) cho chương Phương pháp & Thảo luận kết quả!).

### 🤖 Vai trò 2: CLAUDE CODE — OPUS (Core Algorithm Builder)
- **Thế mạnh:** Viết code thuật toán lõi gọn gàng, chặt chẽ ở mức thao tác bit/byte, tuân thủ đúng chữ ký hàm.
- **Nhiệm vụ phù hợp nhất:**
  - **Đã xong:** Giai đoạn 1 (`default.yaml`, `src/config.py`, `pytest.ini`, `SOURCES/.gitignore`).
  - **Tiếp theo:**
    - **Giai đoạn 2 (Core Crypto):** Cài đặt `src/crypto/*` và `tests/test_crypto.py` theo Mục 3.1 của `01_TECHNICAL_SPEC.md`.
    - **Giai đoạn 3 (Core LSB & Pipeline):** Cài đặt `src/stego/lsb.py` (Header 16-byte + NumPy bitwise vector hóa + auto scale-up trả về `cover_used_rgb`) và `src/pipeline.py` + `tests/test_lsb.py`, `tests/test_pipeline.py` theo Mục 3.2 của `01_TECHNICAL_SPEC.md`.

### 🚀 Vai trò 3: ANTIGRAVITY — GEMINI 4 NEON / CARBON (Architect, Auditor, Metrics & Analytics)
- **Thế mạnh:** Quét ngữ cảnh rộng, đối chiếu bài báo gốc, audit bắt lỗi biên (cross-agent review), chuẩn hóa công thức thống kê, trực quan hóa `matplotlib` chuẩn bài báo và xây dựng Notebook phân tích.
- **Nhiệm vụ phù hợp nhất:**
  - **Đã xong:** Thiết kế toàn bộ `Plans/` (`01_TECHNICAL_SPEC.md`, `02_EXECUTION_PLAN_AND_ROLES.md`, `03_TECHNICAL_BLIND_SPOTS_AND_DECISIONS.md`) và `.antigravity/rules.md`.
  - **Tiếp theo:**
    - **Audit sau GĐ2 & GĐ3:** Kiểm tra chéo code của Claude (tách miền khóa SHA-256, không rò rỉ CBC state, không vòng lặp pixel, bảo toàn Header khi `num_lsb=3`, khôi phục `MSE == 0`).
    - **Giai đoạn 4 (Metrics, Visualization & CLI Scripts):** Cài đặt `src/metrics/visual.py` (`MSE` chia $3HW$), `src/metrics/security.py` (đo kép `*_enc` & `*_stego`), `scripts/run_single.py` (vẽ Histogram gộp phẳng 3 kênh khớp Hình 4c & 5), `scripts/run_benchmark.py` + `tests/test_metrics.py`.
    - **Giai đoạn 5 (Notebook & Tổng hợp Học thuật):** Viết `SOURCES/notebooks/visualize_results.ipynb` và xuất bảng biểu đối chiếu MATLAB vs Python cho báo cáo.

---

## 3. Lộ trình Thực thi Từng Bước Chi tiết (Step-by-Step Playbook)

### Bước 0: Chốt Git cho Giai đoạn 1 & Bộ Hồ sơ `Plans/` — ✅ ĐÃ HOÀN THÀNH (`5d04422`)

---

### Bước 1: Triển khai Giai đoạn 2 — Tầng Mã hóa `src/crypto/` — ✅ ĐÃ HOÀN THÀNH & AUDIT PASS

- **Người thực hiện chính:** **Claude Code (Opus)** — đã hoàn thành 6 file trong `SOURCES/src/crypto/*` và `SOURCES/tests/test_crypto.py`.
- **Kết quả Audit độc lập bởi Gemini (27/11/2026):**
  - Chạy lại `.\.venv\Scripts\pytest.exe tests/test_crypto.py -v`: **126/126 PASSED (2.84s)**.
  - Kiểm chứng thực tế trên `SOURCES/data/sample/secret.png` (`246×300`) & biên `NaN`: khôi phục chính xác 100%, chặn được `NaN` và khóa 3DES suy biến kể cả sau bước chỉnh bit parity.
  - Đo thử tốc độ median (100 lần chạy sau `warmup()` trên ảnh `246×300`): `3DES ≈ 3.84 ms` (sát `3.55 ms` bài báo), `AES ≈ 0.15 ms` (nhờ AES-NI), `Chaotic (cache=False) ≈ 0.43 ms`, `Chaotic (cache=True) ≈ 0.048 ms` (sát `0.036 ms` bài báo!).
  - **Phê duyệt 3 chi tiết cài đặt bổ sung của Claude:** (1) `seed_offset` trên Chaotic chỉ cộng vào `ecc_seed`, giữ nguyên `x0, r` chuẩn bài báo; (2) Kiểm tra chặt `key_bytes/iv_bytes` trong YAML (`24/8`, `16/16`); (3) Thuộc tính chỉ đọc `.key`, `.iv` (kiểu `bytes` bất biến) và `combined_mask(n)` (không sửa in-place mảng trả về).
- **Tiêu chí Nghiệm thu GĐ2 (Definition of Done):**
  - [x] Tách miền khóa bằng SHA-256 từ `crypto.key_seed: 2025` (16 byte đầu của khóa 3DES khác hoàn toàn khóa AES); hỗ trợ `seed_offset`.
  - [x] Gọi `encrypt()` nhiều lần trên cùng instance trả kết quả y hệt nhau; `ciphertext_to_image_view` cắt đúng `H_s * W_s` byte đầu không đệm `255` và trả về bản sao ghi được.
  - [x] `DES3Cipher` từ chối khóa suy biến (`K1 == K2` hoặc `K2 == K3`, kể cả sau `adjust_key_parity`).
  - [x] `ChaoticCipher` chạy đúng cả `cache_mask=False` (mặc định) và `cache_mask=True`, có `warmup()`, xử lý tốt `b""` và ảnh `246×300` / `303×384`.
  - [x] `.\.venv\Scripts\pytest.exe tests/test_crypto.py -v` đạt **100% PASSED** (`126/126`).
- **Chốt mốc:** ✅ Đã commit tại `08c2b15`.

---

### Bước 2: Triển khai Giai đoạn 3 — Tầng Giấu tin LSB & Pipeline khép kín — ✅ ĐÃ HOÀN THÀNH & AUDIT PASS

- **Người thực hiện chính:** **Claude Code (Opus)** — đã hoàn thành `src/stego/lsb.py`, `src/stego/__init__.py`, `src/pipeline.py`, `tests/test_lsb.py`, `tests/test_pipeline.py`.
- **Kết quả Audit độc lập bởi Gemini (27/11/2026):**
  - Chạy lại toàn bộ `.\.venv\Scripts\pytest.exe -v`: **236/236 PASSED (4.40s)** (126 test GĐ2 + 110 test GĐ3).
  - Kiểm tra AST xác nhận 0 vòng lặp Python (`for`/`while`/comprehension) trong `lsb.py`, không tràn số `uint8` kể cả ở `k = 8`.
  - Dùng `np.fromfile` + `cv2.imdecode` / `cv2.imencode` + `buf.tofile` giúp an toàn 100% với đường dẫn tiếng Việt và dấu cách trên Windows.
  - Kiểm chứng thực tế trên cặp ảnh mẫu thật (`cover.jpg` + `secret.png`):
    - Cỡ gốc `246×300`: tự động chọn `num_lsb = 3`, scale-up từ `256×256` lên đúng `(257, 257, 3)`, `MSE ≈ 10.45, PSNR ≈ 37.94 dB`, khôi phục `MSE == 0`.
    - Cỡ Bảng 2 `156×156`: tự động chọn `num_lsb = 1`, giữ nguyên `(256, 256, 3)`, đạt **`MSE ≈ 0.495, PSNR ≈ 51.18 dB`** (khớp lý thuyết và sát sạt Bảng 2!), khôi phục `MSE == 0`.
  - **Phê duyệt 2 quyết định bổ sung của Claude:** (1) `run_from_config` chuẩn hóa ảnh cover đầu vào khác cỡ về `stego.cover_size` (`256×256`) bằng `INTER_AREA` (ảnh Linnaeus 5 giữ nguyên không chạm); (2) Định dạng Header hỗ trợ `num_lsb ∈ 1..8`, còn chính sách nhúng giới hạn bởi `stego.max_lsb = 3`.
- **Tiêu chí Nghiệm thu GĐ3 (Definition of Done):**
  - [x] Không có vòng lặp Python duyệt pixel/bit trong `lsb.py` (đã có test AST tự động bảo vệ).
  - [x] Tách tin độc lập 100% chỉ từ `stego_rgb`; phát hiện và ném `ValueError` khi đưa ảnh không giấu tin, nén JPEG hoặc hỏng CRC16.
  - [x] Trả về đúng `cover_used_rgb` cùng kích thước với `stego_rgb` kể cả khi ảnh cover được phóng đại (`256×256` → `257×257`).
  - [x] Lưu `.png` trên đĩa rồi đọc lại giải mã đạt **`MSE == 0`** (`np.array_equal(secret, recovered)`) với cả 3 thuật toán; cố tình lưu `.jpg` bị chặn bằng `ValueError`.
- **Chốt mốc:** ✅ Đã commit tại `30ce5ac`.

---

### Bước 3: Chuẩn bị Ảnh Mẫu `246×300` & Dataset Linnaeus 5 — ✅ ĐÃ HOÀN THÀNH (`bc009e1`)

- [x] `SOURCES/data/sample/secret.png`: đã xác nhận `(246, 300), uint8`.
- [x] `SOURCES/data/sample/cover.jpg`: đã có sẵn (`256×256×3`).
- [x] `SOURCES/data/linnaeus5/`: đã xác nhận đủ `train = 6,000`, `test = 2,000`, tổng **8,000 ảnh `.jpg`** và được `.gitignore` chặn an toàn.

---

### Bước 4: Triển khai Giai đoạn 4 — Tầng Metrics Kép, Hình vẽ Figures 4–5 & Benchmark Scripts — ✅ ĐÃ HOÀN THÀNH & AUDIT PASS (`93c72e1`)

- **Người thực hiện chính:** **Antigravity (Gemini 4 Carbon)** — cài đặt `src/metrics/{visual.py,security.py,__init__.py}`, tích hợp `src/pipeline.py`, `scripts/{run_single.py,run_benchmark.py}`, và `tests/test_metrics.py`.
- **Kết quả Audit chéo bởi Claude Code (Opus) & Hoàn thiện cuối:**
  - Claude xác nhận toàn bộ công thức toán học (Eq. 3–8) và hai nhóm chỉ số kép `*_enc` / `*_stego` chính xác; bổ sung tính sẵn mặt nạ trong `measure_enc_time(..., warmup=True)` khi `cache_mask=True`, chuẩn hóa tên file `benchmark_summary_table2.csv` + `fig5_comparison_grid.png` + `xlim(-0.5, 255.5)`, và thêm 15 test biên.
  - Gemini cập nhật `ssim()` sang cửa sổ Gaussian `11×11, σ = 1.5` (`gaussian_weights=True, sigma=1.5, use_sample_covariance=False`) khớp chuẩn Wang et al. (2004) / MATLAB `ssim` (`0.99855` vs `0.998494` của Bảng 2) và thêm unit test kiểm chứng $\rightarrow$ tổng **275/275 tests PASSED**.
- **Tiêu chí Nghiệm thu GĐ4 (Definition of Done):**
  - [x] `MSE` chia cho $H \times W \times 3$ và `SSIM` dùng cửa sổ Gaussian `σ = 1.5` chuẩn MATLAB (`BM-09`).
  - [x] `security.py` xuất đầy đủ cả 2 nhóm `*_enc` và `*_stego` (`BM-08`), bấm giờ `EncTime` sau `cipher.warmup()` và precompute khi `cache_mask=True` (`BM-10`).
  - [x] `run_single.py` xuất đủ ảnh rời + `fig4_cover_secret_histograms.png` + `fig5_comparison_grid.png` (gộp phẳng `img_rgb.ravel()` 256 bins khớp Hình 4c & Hình 5).
  - [x] `run_benchmark.py` tách rời hoàn toàn khỏi `matplotlib`, xuất `benchmark_results.csv` và `benchmark_summary_table2.csv`.
- **Chốt mốc:** ✅ Đã commit tại `93c72e1`.

---

### Bước 5: Chạy Thực nghiệm Đầy đủ & Viết Báo cáo CT204 (Giai đoạn 5)

- [x] **Kịch bản A — Đã chạy `scripts.run_single` (`coins` `246×300` chuẩn MATLAB):** Xuất đủ 11 ảnh `.png`, `fig4_cover_secret_histograms.png`, `fig5_comparison_grid.png`, và `single_metrics.csv` tại `SOURCES/results/single/`.
- [x] **Kịch bản B — Đã chạy `scripts.run_benchmark` trên toàn bộ 8,000 ảnh Linnaeus 5 (`156×156`, 1-LSB, `--cache-chaotic-mask`):**
  - Tổng cộng **24,000 / 24,000 lượt chạy khôi phục nguyên bản 100% (`MSE == 0`)**.
  - Kết quả trung bình ghi tại `SOURCES/results/benchmark_summary_table2.csv`:
    - `Avg. MSE`: `0.49560` (3DES) / `0.49577` (AES) / `0.49544` (Chaotic) — khớp bài báo (`~0.4998`).
    - `Avg. PSNR`: `51.179 dB` (3DES) / `51.178 dB` (AES) / `51.181 dB` (Chaotic) — lệch bài báo chỉ `+0.025 dB`.
    - `Avg. SSIM`: `0.99686` ở cả 3 thuật toán — sát `0.9981–0.9985` của bài báo.
    - `Avg. EncTime`: `1.30e-3 s` (3DES) > `1.11e-4 s` (AES) > `3.13e-5 s` (Chaotic, khớp `3.62e-5 s` bài báo!).
    - `NPCR_enc`: `99.65% / 99.58% / 99.56%` (khớp `99.59%–99.64%` bài báo).
    - `UACI_enc`: `30.33% / 30.35% / 30.51%` (khớp `30.81%–30.96%` bài báo và giữ đúng thứ tự `3DES < AES < Chaotic`).
    - `Corr_enc`: `+0.0062 / -0.0014 / -0.0134` (khớp đúng dấu và độ lớn `+0.0003 / -0.0041 / -0.0098` của bài báo!).
    - `Entropy`: `7.992–7.993` trên bản mã (`entropy_enc`) và `7.466` trên ảnh giấu tin (`entropy_stego`).
- [x] **Bước hoàn thiện cuối (Giai đoạn 5B):** Đã viết và chạy sẵn toàn bộ 11 biểu đồ chuyên sâu + bảng đối chiếu trong `SOURCES/notebooks/visualize_results.ipynb` (tự động `git clone https://github.com/NguyenMinhTri24072005/CT204-hybrid-crypto-stego.git` để nạp dữ liệu), đồng thời cập nhật `SOURCES/.gitignore` cho phép đẩy `benchmark_results.csv`, `benchmark_summary_table2.csv` và `results/single/*` lên GitHub.
