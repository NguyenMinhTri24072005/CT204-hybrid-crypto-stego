# Kế hoạch Thực hiện Chi tiết & Phân công Vai trò (Project Execution Plan)

Tài liệu này là **bảng điều khiển trung tâm (Master Tracker)** dành cho bạn (người chủ trì đồ án môn CT204) để nắm rõ:
1. Dự án hiện đang ở đâu, cái gì đã xong, cái gì chưa làm.
2. Phân chia công việc tối ưu giữa **Bạn**, **Claude Code (Opus)** và **Antigravity (Gemini 4 Neon / Carbon)** dựa trên bộ đặc tả đã khóa chặt mọi điểm mù tại [01_TECHNICAL_SPEC.md](./01_TECHNICAL_SPEC.md) và [03_TECHNICAL_BLIND_SPOTS_AND_DECISIONS.md](./03_TECHNICAL_BLIND_SPOTS_AND_DECISIONS.md).
3. Từng bước thực hiện, lệnh chạy kiểm tra và điểm chốt Git commit từ nay đến khi hoàn tất báo cáo.

---

## 1. Bảng Theo dõi Trạng thái Dự án Hiện tại (Project Dashboard)

*Cập nhật: 27/11/2026 — Đã xong Giai đoạn 1 và hoàn tất chốt 10 Quyết định Thiết kế Kỹ thuật (`BM-01` → `BM-10`).*

| Giai đoạn | Hạng mục chính | Trạng thái | Người thực hiện chính | Người Review / Nghiệm thu | Git Commit |
|---|---|---|---|---|---|
| **Khởi tạo & Thiết kế** | Quét bài báo `Docs/145987.pdf`, tạo `.venv` Python 3.12.8, `CLAUDE.md`, `.antigravity/rules.md`, bộ `Plans/` (Spec + Execution Plan + 10 Điểm mù ADR) | ✅ **Hoàn thành** | Bạn + Claude + Gemini | Bạn | Chờ commit gộp cùng GĐ1 |
| **Giai đoạn 1** | Khung cấu hình & môi trường: `SOURCES/.gitignore`, `pytest.ini`, `configs/default.yaml`, `src/config.py`, `scripts/__init__.py`, `.gitkeep` | ✅ **Hoàn thành** *(đã test đọc YAML)* | **Claude Code (Opus)** | **Gemini** (đã kiểm tra) + **Bạn** commit | ⏳ Chờ bạn `git commit` chốt GĐ1 |
| **Giai đoạn 2** | Tầng Mã hóa (`src/crypto/base.py`, `des3_cipher.py`, `aes_cipher.py`, `chaotic_cipher.py`, `__init__.py`) + `tests/test_crypto.py` theo `BM-03, BM-04, BM-05, BM-10` | 🔜 **Sắp làm ngay** | **Claude Code (Opus)** *hoặc* **Gemini** | Agent còn lại review + chạy `pytest` | Chưa |
| **Giai đoạn 3** | Tầng Giấu tin LSB vector hóa (`src/stego/lsb.py` với Header 16B & auto scale-up) + `src/pipeline.py` + `tests/test_lsb.py` & `tests/test_pipeline.py` theo `BM-02, BM-06, BM-07` | ⏳ Chờ GĐ2 | **Claude Code (Opus)** | **Gemini** kiểm tra edge-cases & `MSE == 0` | Chưa |
| **Giai đoạn 4** | Tầng Metrics kép (`src/metrics/visual.py`, `security.py`) + Scripts (`run_single.py`, `run_benchmark.py`) + `tests/test_metrics.py` theo `BM-01, BM-08, BM-09, BM-10` | ⏳ Chờ GĐ3 | **Gemini (Neon/Carbon)** *hoặc* **Claude** | Agent còn lại review công thức toán học | Chưa |
| **Giai đoạn 5** | Chuẩn bị Dataset Linnaeus 5 (8,000 ảnh) & `secret.png` (`246×300`), chạy 2 kịch bản Benchmark (Bảng 2 `156×156` & Gốc `246×300`), làm `visualize_results.ipynb` & viết Báo cáo CT204 | ⏳ Chờ GĐ4 | **Bạn** (data & chạy batch) + **Gemini** (Notebook & phân tích học thuật) | **Bạn** duyệt kết quả cuối | Chưa |

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

### Bước 0: Chốt Git cho Giai đoạn 1 & Bộ Hồ sơ `Plans/` *(BẠN làm ngay bây giờ — 2 phút)*

```powershell
# Chạy tại thư mục gốc Project/
git status
git add .antigravity/ CLAUDE.md Plans/ SOURCES/
git commit -m "chore(phase1): setup project skeleton, config loader, technical specs, and ADRs"
```

---

### Bước 1: Triển khai Giai đoạn 2 — Tầng Mã hóa `src/crypto/`

- **Người thực hiện chính:** **Claude Code (Opus)** *(hoặc giao Gemini nếu muốn làm ngay tại đây)*.
- **Phạm vi file:** `SOURCES/src/crypto/{base.py,des3_cipher.py,aes_cipher.py,chaotic_cipher.py,__init__.py}` và `SOURCES/tests/test_crypto.py`.
- **Prompt mẫu giao việc GĐ2:**
  > *"Hãy đọc kỹ `Plans/01_TECHNICAL_SPEC.md` (Mục 2 và Mục 3.1) và `Plans/03_TECHNICAL_BLIND_SPOTS_AND_DECISIONS.md` (`BM-03`, `BM-04`, `BM-05`, `BM-10`). Triển khai trọn vẹn Giai đoạn 2 (`src/crypto/*` và `tests/test_crypto.py`), bao gồm `derive_bytes` tách miền SHA-256, `ciphertext_to_image_view`, `DES3Cipher` (adjust_key_parity + chặn khóa suy biến), `AESCipher`, `ChaoticCipher` (`@numba.njit`, `clip(floor(x*256), 0, 255)` từ `x_1`, tùy chọn `cache_mask: bool = False`, hàm `warmup()`), và factory `create_cipher`. Chạy `.\.venv\Scripts\pytest.exe tests/test_crypto.py -v` từ `SOURCES/` cho đến khi pass 100%, không sửa các file của GĐ3–GĐ4."*
- **Tiêu chí Nghiệm thu GĐ2 (Definition of Done):**
  - [ ] Tách miền khóa bằng SHA-256 từ `crypto.key_seed: 2025` (16 byte đầu của khóa 3DES khác hoàn toàn khóa AES); hỗ trợ `seed_offset`.
  - [ ] Gọi `encrypt()` nhiều lần trên cùng instance trả kết quả y hệt nhau; `ciphertext_to_image_view` cắt đúng `H_s * W_s` byte đầu không đệm `255`.
  - [ ] `DES3Cipher` từ chối khóa suy biến (`b"\x01" * 24`).
  - [ ] `ChaoticCipher` chạy đúng cả `cache_mask=False` (mặc định) và `cache_mask=True`, có `warmup()`, xử lý tốt `b""` và ảnh `246×300` / `303×384`.
  - [ ] `.\.venv\Scripts\pytest.exe tests/test_crypto.py -v` đạt **100% PASSED**.
- **Chốt mốc:** Bạn chạy `git commit -m "feat(phase2): implement 3DES, AES, and Chaotic-ECC ciphers with unit tests"`.

---

### Bước 2: Triển khai Giai đoạn 3 — Tầng Giấu tin LSB & Pipeline khép kín

- **Người thực hiện chính:** **Claude Code (Opus)**.
- **Phạm vi file:** `SOURCES/src/stego/lsb.py`, `SOURCES/src/pipeline.py`, `SOURCES/tests/test_lsb.py`, `SOURCES/tests/test_pipeline.py`.
- **Prompt mẫu giao việc GĐ3:**
  > *"Hãy đọc kỹ Mục 3.2 của `Plans/01_TECHNICAL_SPEC.md` và các quyết định `BM-02`, `BM-06`, `BM-07` trong `Plans/03_TECHNICAL_BLIND_SPOTS_AND_DECISIONS.md`. Triển khai Giai đoạn 3 (`src/stego/lsb.py`, `src/pipeline.py`, `tests/test_lsb.py`, `tests/test_pipeline.py`): đóng gói Header 16-byte (`>4sBBHHIH`, magic `HCST` + CRC16) ở `1-LSB` tại `flat[0:128]`, nhúng Payload từ `flat[128:]` bằng phép toán bitwise NumPy vector hóa 100% không vòng lặp, tự động chọn `num_lsb` trong `{1,2,3}` và auto scale-up bằng `cv2.INTER_CUBIC` khi vượt 3-LSB (trả về cả `cover_used_rgb` trong `EmbedResult`), ép định dạng lossless `.png`. Chạy `.\.venv\Scripts\pytest.exe -v` pass 100%."*
- **Tiêu chí Nghiệm thu GĐ3 (Definition of Done):**
  - [ ] Không có vòng lặp Python duyệt pixel/bit trong `lsb.py`.
  - [ ] Tách tin độc lập 100% chỉ từ `stego_rgb`; phát hiện và ném `ValueError` khi đưa ảnh không giấu tin hoặc hỏng CRC16.
  - [ ] Trả về đúng `cover_used_rgb` cùng kích thước với `stego_rgb` kể cả khi ảnh cover được phóng đại (ví dụ với `coins` `246×300` phóng đại từ `256×256` lên `257×257`).
  - [ ] Lưu `.png` trên đĩa rồi đọc lại giải mã đạt **`MSE == 0`** (`np.array_equal(secret, recovered)`) với cả 3 thuật toán; cố tình lưu `.jpg` bị chặn bằng `ValueError`.
- **Chốt mốc:** Bạn chạy `git commit -m "feat(phase3): implement vectorized LSB steganography with 16B header and pipeline"`.

---

### Bước 3: Chuẩn bị Ảnh Mẫu `246×300` & Dataset Linnaeus 5 *(BẠN thực hiện trước GĐ4)*

1. **Tạo ảnh bí mật `SOURCES/data/sample/secret.png` đúng chuẩn `coins.png` `246×300` của MATLAB (`BM-01`):**
   ```powershell
   cd SOURCES
   .\.venv\Scripts\python.exe -c "import cv2; from skimage import data; s = cv2.resize(data.coins(), (300, 246), interpolation=cv2.INTER_AREA); cv2.imwrite('data/sample/secret.png', s); print('Saved:', s.shape, s.dtype)"
   ```
   *(Lưu ý trong `cv2.resize(img, (width, height))`, truyền `(300, 246)` sẽ tạo mảng `shape == (246, 300)` đúng `73,800` bytes!)*
2. **Giải nén Dataset Linnaeus 5 (`256×256`, 8,000 ảnh):**
   - Đặt vào `SOURCES/data/linnaeus5/train/{berry,bird,dog,flower,other}/*.jpg` (6,000 ảnh) và `SOURCES/data/linnaeus5/test/{berry,bird,dog,flower,other}/*.jpg` (2,000 ảnh).
   - Copy 1 ảnh quả mâm xôi từ `train/berry/` sang `SOURCES/data/sample/cover.jpg` để làm ảnh mẫu cố định cho Hình 4–5.

---

### Bước 4: Triển khai Giai đoạn 4 — Tầng Metrics Kép, Hình vẽ Figures 4–5 & Benchmark Scripts

- **Người thực hiện chính:** **Antigravity (Gemini 4 Neon / Carbon)**.
- **Phạm vi file:** `SOURCES/src/metrics/{visual.py,security.py}`, tích hợp metrics vào `SOURCES/src/pipeline.py`, `SOURCES/scripts/{run_single.py,run_benchmark.py}`, và `SOURCES/tests/test_metrics.py`.
- **Tiêu chí Nghiệm thu GĐ4 (Definition of Done):**
  - [ ] `MSE` chia cho $H \times W \times 3$ (`BM-09`); kiểm chứng trên 1-LSB ngẫu nhiên cho `MSE ≈ 0.50`, `PSNR ≈ 51.14 dB`.
  - [ ] `security.py` xuất đầy đủ cả 2 nhóm `*_enc` và `*_stego` (`BM-08`), bấm giờ `EncTime` sau `cipher.warmup()` (`BM-10`).
  - [ ] `run_single.py` vẽ Histogram ảnh màu gộp phẳng `img_rgb.ravel()` (256 bins) khớp giao diện Hình 4c & Hình 5 (`BM-10`).
  - [ ] `run_benchmark.py` hỗ trợ `--limit`, `--secret-size`, `--vary-key-per-image`, `--cache-chaotic-mask`, xuất cả `benchmark_results.csv` và `benchmark_summary_table2.csv`.
- **Chốt mốc:** Bạn chạy `git commit -m "feat(phase4): implement dual metrics, paper figure plots, and benchmark CLI"`.

---

### Bước 5: Chạy Thực nghiệm Đầy đủ & Viết Báo cáo CT204 (Giai đoạn 5)

Bạn chạy 2 lượt thực nghiệm trên tập Linnaeus 5 (8,000 ảnh) để có bộ số liệu hoàn hảo nhất cho báo cáo:
1. **Kịch bản A — Tái hiện chuẩn điều kiện 1-LSB của Bảng 2 (`BM-01`):**
   ```powershell
   cd SOURCES
   .\.venv\Scripts\python.exe -m scripts.run_benchmark --secret-size 156 156
   ```
   *(Thu được `MSE ≈ 0.495–0.500`, `PSNR ≈ 51.15 dB`, `SSIM ≈ 0.998`, `NPCR_enc ≈ 99.61%`, `UACI_enc ≈ 30.8%`, `Entropy_stego ≈ 7.05` & `Entropy_enc ≈ 7.998`.)*
2. **Kịch bản B — Chạy kích thước gốc `coins` `246×300` của MATLAB (Hình 4–5):**
   ```powershell
   .\.venv\Scripts\python.exe -m scripts.run_single
   ```
3. **Tổng hợp cùng Gemini:** Mở rộng `SOURCES/notebooks/visualize_results.ipynb` vẽ biểu đồ so sánh và xuất bảng số liệu chèn thẳng vào báo cáo môn CT204.
