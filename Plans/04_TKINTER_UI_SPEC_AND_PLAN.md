# Đặc tả Kỹ thuật & Kế hoạch Triển khai Ứng dụng Desktop Tkinter (`Giai đoạn 6`)

Tài liệu này là **Đặc tả Kỹ thuật Chuẩn (Single Source of Truth)** và **Kế hoạch Thực thi** cho việc xây dựng giao diện người dùng Desktop chạy **Offline 100%** bằng `tkinter` / `tkinter.ttk` (Giai đoạn 6A) và lộ trình đóng gói thành file thực thi Windows `.exe` độc lập bằng `PyInstaller` (Giai đoạn 6B) cho đồ án môn **CT204 — An toàn Thông tin**.

---

## 1. Mục tiêu & Nguyên tắc Thiết kế Bắt buộc

1. **Offline 100% & Không phát sinh thư viện UI bên thứ ba:**
   - Sử dụng trực tiếp `tkinter` + `tkinter.ttk` (có sẵn trong Python 3.12, Tk 8.6), kết hợp `Pillow` (`PIL.Image`, `PIL.ImageTk` — đã có sẵn trong `.venv`) để hiển thị ảnh chất lượng cao và `matplotlib.backends.backend_tkagg.FigureCanvasTkAgg` để nhúng biểu đồ tương tác.
   - Không yêu cầu kết nối mạng, không chạy local web server, không cài thêm framework ngoài (`streamlit`, `gradio`, `customtkinter`, `PyQt`...).
2. **Bảo toàn tuyệt đối Tầng Lõi (Zero Core Modification):**
   - **KHÔNG sửa đổi** bất kỳ file nào thuộc Giai đoạn 1 → 4 (`src/config.py`, `src/crypto/*`, `src/stego/*`, `src/metrics/*`, `src/pipeline.py`, `scripts/*`).
   - Toàn bộ **275 unit tests hiện hữu** phải tiếp tục `PASSED 100%`.
   - Mọi module giao diện nằm cô lập trong package mới `SOURCES/src/ui/` và entry point `SOURCES/app.py`.
3. **Kiến trúc Sẵn sàng Đóng gói `.exe` ngay từ đầu (PyInstaller-Ready):**
   - Mọi truy cập tài nguyên (`configs/default.yaml`, `data/sample/*`, `results/*.csv`) bắt buộc đi qua lớp phân giải đường dẫn `src/ui/resources.py` có hỗ trợ `sys.frozen` và `sys._MEIPASS`.
   - Cấu hình trước biến môi trường bộ nhớ đệm `NUMBA_CACHE_DIR` vào thư mục tạm của hệ điều hành khi chạy ở chế độ đóng gói (`frozen`) trước khi import `src.crypto`.
   - Tuyệt đối không ghi file tạm vào thư mục mã nguồn hay thư mục cài đặt `.exe`; chỉ ghi file khi người dùng chủ động bấm nút Xuất/Lưu qua `filedialog`.
4. **Không treo giao diện (Non-Blocking UI) & Tương thích Máy chiếu:**
   - Các tác vụ tốn thời gian (biên dịch Numba lần đầu, chạy pipeline 3 thuật toán đồng thời, nạp `benchmark_results.csv` 24.000 dòng) phải chạy trên luồng nền (`threading.Thread(daemon=True)`) và giao tiếp về luồng chính qua `queue.Queue` + `widget.after()`.
   - **Quy tắc vàng Tcl/Tk:** Luồng nền chỉ xử lý mảng `numpy` / `pandas` / mật mã; **mọi thao tác cập nhật `tk.Widget`, `ImageTk.PhotoImage` và `canvas.draw_idle()` bắt buộc thực hiện trên Main Thread**.
   - Bố cục hỗ trợ màn hình độ phân giải thấp của máy chiếu hội đồng bảo vệ (`1366×768` trở lên) nhờ vùng cuộn dọc `ScrollableFrame` có hỗ trợ con lăn chuột (`<MouseWheel>`) và bật High-DPI Awareness trên Windows.

---

## 2. Cấu trúc Mã nguồn Giao diện (`SOURCES/`)

```text
SOURCES/
├── app.py                              # Entry point khởi chạy ứng dụng Desktop (cấu hình Numba/DPI + launch_app)
├── requirements.txt                    # Bổ sung khai báo tường minh Pillow>=10.3.0,<14.0.0 (đã cài sẵn trong .venv)
├── src/
│   └── ui/
│       ├── __init__.py                 # Export launch_app(), CT204App
│       ├── resources.py                # Phân giải đường dẫn Dev vs PyInstaller (_MEIPASS), load_ui_config()
│       ├── theme.py                    # Bảng màu học thuật sáng sủa, font Segoe UI, ttk.Style('clam'), High-DPI
│       ├── controller.py               # Tầng nghiệp vụ thuần Python (không phụ thuộc cửa sổ Tk, dễ unit-test):
│       │                               #   - build_ui_cipher() (chế độ Seed bài báo & chế độ Mật khẩu tùy chỉnh)
│       │                               #   - run_encrypt_workflow(), inspect_stego_header(), run_decrypt_workflow()
│       │                               #   - simulate_attack() (Wrong Key / JPEG Q=95 / Flip Header Bit / Gaussian Noise)
│       │                               #   - run_compare_workflow() (3DES + AES + Chaotic song song tuần tự)
│       │                               #   - load_benchmark_bundle() + hằng số tham chiếu Bảng 2 bài báo gốc
│       │                               #   - build_diff_heatmap() (|Cover - Stego| khuếch đại trực quan)
│       ├── worker.py                   # TaskRunner: chạy hàm nền qua Thread + Queue + root.after() an toàn
│       ├── widgets.py                  # Các thành phần UI tái sử dụng:
│       │                               #   - ScrollableFrame (Canvas + ttk.Scrollbar + MouseWheel binding)
│       │                               #   - ImagePreviewCard (hiển thị ảnh RGB/Gray giữ tỷ lệ + click đúp phóng to)
│       │                               #   - KpiBadgeRow & StyledTreeview (bảng chỉ số có màu xen kẽ)
│       │                               #   - MatplotlibCard (nhúng matplotlib.figure.Figure OOP qua FigureCanvasTkAgg)
│       ├── app_window.py               # Cửa sổ chính CT204App: Header banner, ttk.Notebook (4 Tabs), StatusBar
│       └── tabs/
│           ├── __init__.py
│           ├── tab_encrypt.py          # Tab 1: Mã hóa & Giấu tin (Encrypt & Embed)
│           ├── tab_decrypt.py          # Tab 2: Trích xuất, Giải mã & Phòng thí nghiệm Tấn công (Decrypt & Tamper Lab)
│           ├── tab_compare.py          # Tab 3: So sánh trực tiếp 3 Thuật toán & Tái hiện Hình 4–5 (Live Comparison)
│           └── tab_benchmark.py        # Tab 4: Dashboard 8,000 ảnh Linnaeus 5 & Đối chiếu Bảng 2 Bài báo
└── tests/
    └── test_ui_controller.py           # Unit tests cho resources, controller, chế độ mật khẩu, tamper lab & smoke test Tk
```

*(Giai đoạn 6B sau khi nghiệm thu UI sẽ bổ sung thêm `SOURCES/packaging/ct204_app.spec` và `SOURCES/packaging/build_exe.ps1`.)*

---

## 3. Đặc tả Chi tiết Tầng Nghiệp vụ UI (`resources.py` & `controller.py`)

### 3.1. Phân giải tài nguyên tương thích `.exe` (`src/ui/resources.py`)

```python
def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"))

def get_resource_root() -> Path:
    """Trả về Path(sys._MEIPASS) khi chạy từ .exe PyInstaller, ngược lại trả về thư mục SOURCES/."""

def get_default_export_dir() -> Path:
    """Khi frozen: Path(sys.executable).parent / 'exports'; khi dev: get_resource_root() / 'results' / 'ui_exports'."""

def load_ui_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Đọc configs/default.yaml từ get_resource_root() và chuẩn hóa lại paths.*, secret.path
    tương đối theo get_resource_root() để hoạt động giống hệt nhau ở cả chế độ dev và .exe."""
```

### 3.2. Hai Chế độ Quản lý Khóa Thống nhất cho cả 3 Thuật toán (`build_ui_cipher`)

Một điểm rất quan trọng khi demo môn An toàn thông tin: trong `configs/default.yaml`, `DES3` và `AES` dẫn xuất khóa từ `crypto.key_seed` (`2025`), trong khi `ChaoticCipher` dùng `x0=0.785398, r=3.999, ecc_seed=42`. Do đó `controller.py` phải hỗ trợ **2 chế độ khóa rõ ràng**:

1. **`key_mode = "paper_default"` (Mặc định — Khớp chuẩn Bài báo & CLI):**
   - Gọi trực tiếp `create_cipher(cipher_name, cfg, cache_chaotic_mask=cache_chaotic_mask)`.
   - Đảm bảo kết quả trên UI **trùng khớp 100% từng bit** với `scripts/run_single.py` (người dùng mở bất kỳ ảnh `results/single/*_stego.png` nào ở Tab 2 cũng giải mã ra ngay ảnh gốc `MSE == 0`).

2. **`key_mode = "passphrase"` (Mật khẩu người dùng tự nhập — Phục vụ sử dụng thực tế & Demo Sai Khóa):**
   - Nhận chuỗi `passphrase: str` (không rỗng setelah `.strip()`, nếu rỗng ném `ValueError` thân thiện).
   - Băm `digest = hashlib.sha256(f"ct204-ui:{cipher_canonical}:{passphrase}".encode("utf-8")).digest()`, lấy `seed_int = int.from_bytes(digest[:8], "big")`:
     - **`3des`**: `iv = derive_bytes(seed_int, 8, "ui:3des:iv")`; thử `attempt = 0..63` với `key = derive_bytes(seed_int, 24, f"ui:3des:key:{attempt}")` khởi tạo `DES3Cipher(key, iv)` (tự động tránh khóa suy biến).
     - **`aes`**: `key = derive_bytes(seed_int, 16, "ui:aes:key")`, `iv = derive_bytes(seed_int, 16, "ui:aes:iv")` $\rightarrow$ `AESCipher(key, iv)`.
     - **`chaotic`**: dẫn xuất `ecc_seed = int(seed_int & 0x7FFFFFFF)` và dịch vi lượng an toàn `x0`:
       $$x_0 = 0.1 + 0.8 \times \frac{\text{int.from\_bytes}(\text{digest}[8:16], \text{"big"})}{2^{64}}$$
       giữ `r = float(cfg["crypto"]["chaotic"]["r"])` (`3.999`) $\rightarrow$ `ChaoticCipher(x0=x0, r=r, ecc_seed=ecc_seed, cache_mask=cache_chaotic_mask)`.
   - **Hệ quả bảo mật đạt được:** Chỉ cần nhập lệch **1 ký tự** mật khẩu, **cả 3 thuật toán (`3DES`, `AES`, `Chaotic`) đều thay đổi hoàn toàn luồng khóa**!

### 3.3. Hợp đồng Dữ liệu & Hàm Nghiệp vụ trong `src/ui/controller.py`

- **`compute_diff_heatmap(cover_used_rgb: np.ndarray, stego_rgb: np.ndarray, gain: float = 50.0) -> np.ndarray`**:
  - Tính `diff = np.abs(cover_used_rgb.astype(np.int16) - stego_rgb.astype(np.int16))` và nhân `gain` (mặc định `×50` hoặc `×85`), cắt ngưỡng `[0, 255]` kiểu `uint8` RGB để mắt thường nhìn thấy rõ các pixel mang tin LSB.
- **`inspect_stego_header(stego_rgb: np.ndarray) -> HeaderInspection`**:
  - Đọc 128 kênh đầu ở 1-LSB và phân tích cấu trúc 16-byte `>4sBBHHIH`:
  - Trả về dataclass `HeaderInspection(is_valid: bool, magic_raw: bytes, version: int | None, num_lsb: int | None, secret_shape: tuple[int, int] | None, ciphertext_len: int | None, crc_expected: int | None, crc_actual: int | None, error_message: str | None)`.
  - Không ném exception ra ngoài khi ảnh là ảnh thường hoặc bị hỏng CRC — thay vào đó trả `is_valid=False` kèm lý do cụ thể bằng tiếng Việt để Tab 2 hiển thị trực quan trạng thái Header.
- **`run_decrypt_workflow(...) -> DecryptWorkflowResult`**:
  - Thực hiện `extract(stego_rgb)` $\rightarrow$ `cipher.decrypt(ciphertext)` $\rightarrow$ `reshape(H_s, W_s)`.
  - **Xử lý sư phạm khi Sai Khóa trên Block Cipher (`AES` / `3DES`):**
    - Khi nhập sai mật khẩu, `pycryptodome` `unpad()` thường ném `ValueError("Padding is incorrect.")`.
    - `run_decrypt_workflow` bắt lỗi này, đánh dấu `success=False`, ghi rõ thông báo lỗi xác thực PKCS#7, **đồng thời** tạo một bản `raw_corrupted_preview: np.ndarray` (`H_s × W_s uint8`) bằng cách giải mã CBC thô không `unpad` (cắt `H_s * W_s` byte đầu qua `ciphertext_to_image_view`) để giao diện vẫn cho giảng viên thấy "ảnh nhiễu tuyết hoàn toàn do sai khóa" bên cạnh cảnh báo lỗi Padding!
  - Nếu có `reference_secret_gray` cùng kích thước với ảnh giải mã được, tính kèm `recovery_mse`, `recovery_psnr`, `bit_error_rate` và `is_exact = np.array_equal(...)`.
- **`simulate_tamper(stego_rgb: np.ndarray, mode: str) -> tuple[np.ndarray, str]`**:
  - Hỗ trợ 4 chế độ tấn công/phá hoại phục vụ demo trực tiếp ở Tab 2 (không ghi file rác ra đĩa, xử lý hoàn toàn trên RAM bằng `cv2.imencode`/`imdecode` và mảng NumPy):
    1. `"jpeg_q95"`: Nén JPEG chất lượng cao (`IMWRITE_JPEG_QUALITY = 95`) rồi giải mã lại sang RGB $\rightarrow$ làm hỏng LSB & chữ ký `HCST` / `CRC-16`.
    2. `"flip_header_bit"`: Đảo đúng 1 bit LSB tại `flat[16]` (nằm trong 14 byte đầu của Header) $\rightarrow$ `Magic = HCST` vẫn còn nhưng `CRC-16` báo lỗi `CRC16 mismatch` ngay lập tức.
    3. `"flip_payload_bits"`: Đảo 1% số bit LSB trong vùng payload (`flat[128:]`), giữ nguyên Header 16-byte $\rightarrow$ chứng minh Header qua cửa nhưng giải mã CBC sập khối hoặc ảnh khôi phục bị nhiễu.
    4. `"gaussian_noise"`: Cộng nhiễu Gaussian nhẹ `σ = 2.0` (`rng = np.random.default_rng(2025)`) vào ảnh Stego $\rightarrow$ phá vỡ hoàn toàn kênh giấu tin không bền vững (fragile LSB).
- **`load_benchmark_bundle(results_dir: Path | None = None) -> BenchmarkBundle`**:
  - Nạp `benchmark_summary_table2.csv` và (nếu có) `benchmark_results.csv` bằng `pandas`.
  - Đóng gói kèm hằng số `PAPER_TABLE2_REFERENCE` (số liệu Bảng 2 của Raut et al., ICITSC 2025 cho `3des`, `aes`, `chaotic`) để Tab 4 hiển thị bảng so sánh đối chiếu kể cả khi người dùng chỉ giữ file summary.

---

## 4. Đặc tả Giao diện & Bố cục Chi tiết 4 Tab (`src/ui/`)

### 4.1. Khung Cửa sổ Chính & Phong cách Thẩm mỹ (`theme.py`, `app_window.py`)
- **Tiêu đề cửa sổ:** `"CT204 — Hybrid Crypto-Steganography Framework (3DES · AES · Chaotic + Multi-LSB)"`
- **Kích thước:** Mặc định `1360×840`, tối thiểu `minsize(1060, 680)`, căn giữa màn hình khi mở.
- **Theme & Bảng màu (`ttk.Style` nền `'clam'`, giao diện sáng học thuật sạch sẽ, tương phản cao khi chiếu máy chiếu):**
  - Nền chính: `#F4F6F9` | Nền thẻ (Card): `#FFFFFF` | Viền mảnh: `#D8E0EA`
  - Màu nhấn chính (Primary Accent): `#1E3A5F` (Navy) & `#2563EB` (Royal Blue)
  - Trạng thái Đạt / Toàn vẹn (`MSE == 0`, `CRC OK`): `#15803D` (Xanh lá đậm)
  - Trạng thái Cảnh báo / Lỗi tấn công (`CRC Mismatch`, `Wrong Key`): `#B91C1C` (Đỏ đậm)
  - Font chữ: `("Segoe UI", 10)` cho nội dung, `("Segoe UI", 10, "bold")` cho tiêu đề thẻ, `("Consolas", 10)` cho số liệu kỹ thuật và trường Hex/CRC.
- **Thanh Trạng thái (Bottom Status Bar):**
  - Bên trái: thông điệp trạng thái hiện tại (ví dụ: `"Sẵn sàng — Đã nạp cấu hình configs/default.yaml"` hoặc `"Đang mã hóa và nhúng tin bằng Chaotic..."`).
  - Bên phải: `ttk.Progressbar(mode="indeterminate")` tự chạy khi có tác vụ nền và dừng khi hoàn tất.
- **Quy ước bắt buộc khi vẽ Matplotlib trong Tkinter (`widgets.py`):**
  - **KHÔNG** dùng `import matplotlib.pyplot as plt` hay `matplotlib.use("Agg")` bên trong `src/ui/`.
  - Luôn khởi tạo trực tiếp `from matplotlib.figure import Figure` (`fig = Figure(figsize=..., dpi=100)`) và gắn vào `FigureCanvasTkAgg(fig, master=frame)` để tránh rò rỉ bộ nhớ và xung đột backend toàn cục.

---

### 4.2. Tab 1 — Mã hóa & Giấu tin (`tab_encrypt.py`)

- **Cột Điều khiển bên trái (`width ~ 330px`):**
  1. **Ảnh Phủ (Cover RGB):**
     - Nút `📂 Chọn ảnh Cover...` (`.jpg/.jpeg/.png/.bmp`) và nút `🖼 Ảnh mẫu (cover.jpg)`.
     - Checkbox `Chuẩn hóa Cover về 256×256 (chuẩn bài báo)` *(mặc định: Bật)*.
  2. **Ảnh Bí mật (Secret Grayscale):**
     - Nút `📂 Chọn ảnh Secret...` và nút `🪙 Ảnh mẫu (coins 246×300)`.
     - Combobox **Chế độ kích thước Secret (`BM-01`):**
       - `Giữ nguyên gốc (246×300 — Hình 4 & 5 bài báo)`
       - `Chuẩn Bảng 2 1-LSB (Resize 156×156)`
       - `Tùy chỉnh (nhập H × W)`
  3. **Thuật toán & Khóa:**
     - Radio / Combobox chọn thuật toán: `3DES-192 (CBC)`, `AES-128 (CBC)`, `Chaotic (Logistic + ECC)`.
     - Chế độ khóa: `Chuẩn bài báo (Seed 2025)` hoặc `Mật khẩu tùy chỉnh (Passphrase)` (có ô nhập mật khẩu + nút 👁 Hiện/Ẩn).
     - Checkbox `Pre-cache mặt nạ Chaotic (BM-10)` *(mặc định: Bật khi chọn Chaotic)*.
  4. **Hành động:**
     - Nút chính **`▶ Mã hóa & Giấu tin`**
     - Nút **`💾 Lưu ảnh Stego (.png)...`** *(chỉ bật sau khi chạy xong; ép đuôi `.png` lossless)*
     - Nút **`➡ Chuyển sang Tab Giải mã`** *(gửi trực tiếp mảng `stego_rgb`, `secret_gray` gốc tham chiếu, tên thuật toán và cấu hình khóa sang Tab 2 rồi tự chuyển tab)*.

- **Vùng Kết quả bên phải (đặt trong `ScrollableFrame`):**
  1. **Hàng 4 Thẻ Ảnh (`ImagePreviewCard`, click đúp vào ảnh bất kỳ mở cửa sổ `Toplevel` phóng lớn):**
     - `1. Cover thực dùng` (ghi rõ `H×W`, hiện nhãn `Auto-scaled 256→257` nếu `was_scaled_up=True`)
     - `2. Secret gốc (Gray)` (`H_s×W_s`)
     - `3. Bản mã Ciphertext View` (`BM-05`)
     - `4. Ảnh Stego (.png)` kèm nút gạt `Xem ảnh Stego` ↔ `Xem Bản đồ Sai khác |Cover − Stego| × 50`
  2. **Hàng KPI & Bảng Chỉ số Kép (`BM-08`, `BM-09`):**
     - Dải KPI nhanh: `Số bit LSB: k` | `Kích thước bản mã: N bytes` | `MSE` | `PSNR (dB)` | `SSIM` | `EncTime` | `Kiểm chứng vòng kín: MSE = 0 ✅`.
     - Bảng `Treeview` đối chiếu 2 nhóm chỉ số bảo mật:
       - Nhóm **Bản mã (`Secret vs Encrypted`)**: `NPCR_enc (%)`, `UACI_enc (%)`, `Corr_enc`, `Entropy_enc (bits)`
       - Nhóm **Ảnh giấu tin (`Cover vs Stego`)**: `NPCR_stego (%)`, `UACI_stego (%)`, `Corr_stego`, `Entropy_stego (bits)`
  3. **Khung Biểu đồ Histogram 256-bin (3 cột ngang):**
     - `Cover Histogram` | `Encrypted Secret Histogram` | `Stego Histogram` (`xlim(-0.5, 255.5)`).

---

### 4.3. Tab 2 — Trích xuất, Giải mã & Phòng thí nghiệm Tấn công (`tab_decrypt.py`)

- **Cột Điều khiển bên trái:**
  1. **Nguồn ảnh Stego:**
     - Nút `📂 Mở ảnh Stego (.png)...` (mặc định mở vào `results/single/` nếu tồn tại).
     - Nút `📥 Lấy ảnh Stego vừa tạo từ Tab 1`.
     - *(Tùy chọn)* Nút `📂 Chọn ảnh Secret gốc để đối chiếu MSE/BER...` (nếu nhận từ Tab 1 thì tự động gắn sẵn).
  2. **Bảng Kiểm tra Nhanh Header 16-byte (`HCST` Live Inspector):**
     - Ngay khi nạp ảnh, hiển thị lập tức: `Magic`, `Version`, `num_lsb`, `Secret Shape (H×W)`, `Ciphertext (bytes)`, `CRC-16 (Expected vs Actual)` và trạng thái **`HỢP LỆ ✅`** hoặc **`LỖI TOÀN VẸN ❌`**.
  3. **Cấu hình Giải mã:**
     - Chọn thuật toán (`3DES / AES / Chaotic`) + Chế độ khóa (`Seed 2025` hoặc `Passphrase`).
     - Nút chính **`🔓 Trích xuất & Giải mã`** và nút **`💾 Lưu ảnh Secret khôi phục (.png)...`**.
  4. **Phòng thí nghiệm Tấn công & Độ bền (`Security & Tamper Demo Lab`):**
     - 4 nút mô phỏng 1-click trên bản sao của ảnh Stego đang nạp:
       - `🔑 Thử Giải mã Sai Khóa` (dùng khóa lệch để chứng minh tính bí mật)
       - `📷 Nén JPEG (Quality = 95)` (chứng minh nén có tổn hao phá hủy LSB & CRC-16)
       - `⚡ Đảo 1 Bit Header` (chứng minh CRC-16 phát hiện giả mạo metadata)
       - `🔊 Đảo Bit Payload / Nhiễu Kênh truyền` (chứng minh hiệu ứng thác đổ CBC / nhiễu ảnh)
     - Nút `↩ Khôi phục lại ảnh Stego gốc ban đầu` (reset trạng thái sạch).

- **Vùng Kết quả bên phải:**
  - Hiển thị cạnh nhau: `Ảnh Stego đang kiểm tra` | `Ảnh Secret khôi phục (hoặc Bản xem trước nhiễu thô khi sai khóa)` | `Ảnh Secret gốc đối chiếu (nếu có)`.
  - Hộp kết luận nổi bật (Banner màu xanh khi khôi phục hoàn hảo `MSE = 0.000000, BER = 0.00%`; Banner màu đỏ giải thích rõ nguyên nhân kỹ thuật khi bị tấn công: lỗi `HCST magic`, lỗi `CRC-16 mismatch`, hay lỗi `PKCS#7 Padding / Wrong Key`).

---

### 4.4. Tab 3 — So sánh Trực tiếp 3 Thuật toán (`tab_compare.py`)

- **Thanh điều khiển trên cùng:**
  - Chọn nguồn Cover/Secret (dùng cặp đang chọn ở Tab 1 hoặc cặp mẫu `cover.jpg` + `secret.png`), chọn Preset kích thước Secret (`246×300 Hình 5` vs `156×156 Bảng 2`), bật/tắt `Pre-cache Chaotic Mask`, nút **`⚡ Chạy So sánh cả 3 Thuật toán`**, và nút **`📤 Xuất bộ ảnh Hình 4, Hình 5 & CSV...`**.
- **Vùng hiển thị chính:**
  1. **Bảng So sánh Ngang (`3DES` vs `AES` vs `Chaotic`):**
     - Đầy đủ cột: `Thuật toán`, `num_lsb`, `Cover Used`, `MSE`, `PSNR (dB)`, `SSIM`, `EncTime (µs)`, `Tăng tốc so với 3DES (×)`, `NPCR_enc (%)`, `UACI_enc (%)`, `Corr_enc`, `Entropy_stego`, `Entropy_enc`, `Khôi phục (MSE=0)`.
  2. **Chế độ xem trực quan (chuyển bằng Radio/Sub-tabs):**
     - **Chế độ A — Tái hiện Hình 5 Bài báo (Lưới 3×3):** Cột = `3DES / AES / Chaotic`; Hàng 1 = Ảnh mã hóa, Hàng 2 = Histogram bản mã, Hàng 3 = Histogram ảnh Stego.
     - **Chế độ B — Tốc độ Mã hóa & Ảnh Khôi phục:** Biểu đồ cột ngang `EncTime` (thang đo logarit + nhãn `µs` và hệ số `× faster`) đặt cạnh 3 ảnh Secret khôi phục.

---

### 4.5. Tab 4 — Dashboard Thực nghiệm 8.000 Ảnh Linnaeus 5 (`tab_benchmark.py`)

- **Hoạt động Offline 100%** từ `results/benchmark_summary_table2.csv` và `results/benchmark_results.csv` (tự động nạp khi mở tab lần đầu bằng worker thread, có nút `📂 Nạp file CSV khác...`).
- **Các thành phần hiển thị:**
  1. **Dải Thẻ Tổng quan Thực nghiệm:** `Tổng số ảnh: 8,000` | `Tổng lượt mã hóa-giải mã: 24,000` | `Khôi phục chính xác (MSE=0): 100.00%` | `Cấu hình: 156×156 (1-LSB)`.
  2. **Bảng Đối chiếu Học thuật (Python Reproduction vs. MATLAB Paper Table 2):**
     - Hiển thị song song kết quả trung bình của ta và con số công bố trong Bảng 2 bài báo gốc cho từng thuật toán (`MSE`, `PSNR`, `SSIM`, `EncTime`, `NPCR`, `UACI`, `Correlation`, `Entropy Stego`, `Entropy Cipher`), kèm cột chênh lệch `Δ`.
  3. **Bộ lọc & Biểu đồ Tương tác (`FigureCanvasTkAgg`):**
     - Bộ lọc: `Tập dữ liệu` (`Tất cả / train / test`), `Lớp ảnh Linnaeus 5` (`Tất cả / berry / bird / dog / flower / other`), và `Loại biểu đồ`:
       1. *Đối chiếu Bài báo vs Thực nghiệm (PSNR, NPCR, UACI, EncTime log-scale)*
       2. *Phân bố PSNR / SSIM / Entropy Stego theo 5 lớp ảnh Linnaeus 5*
       3. *Phân bố thời gian mã hóa EncTime (µs) của 3 thuật toán trên tập dữ liệu*

---

## 5. Đặc tả Kiểm thử Tự động (`SOURCES/tests/test_ui_controller.py`)

Bổ sung file test mới chạy chung trong `.\.venv\Scripts\pytest.exe -q`:

1. **Test phân giải đường dẫn (`resources.py`):**
   - Kiểm tra `get_resource_root()` ở chế độ thường và giả lập `monkeypatch` thuộc tính `sys.frozen = True`, `sys._MEIPASS = tmp_path` để chắc chắn cơ chế đóng gói `.exe` đọc đúng config/sample/CSV.
2. **Test quản lý khóa (`build_ui_cipher`):**
   - Chế độ `"paper_default"` tạo ra bản mã trùng khít 100% với `create_cipher` chuẩn.
   - Chế độ `"passphrase"` mã hóa – giải mã khôi phục `MSE == 0` trên cả `3des`, `aes`, `chaotic`; đổi 1 ký tự mật khẩu khiến cả 3 thuật toán thất bại giải mã hoặc ra ảnh khác hẳn (`MSE > 1000`), và với `3des`/`aes` trả về `raw_corrupted_preview` hợp lệ đúng kích thước.
3. **Test Inspector Header 16-byte & 4 kịch bản Tamper Lab:**
   - Ảnh Stego sạch $\rightarrow$ `HeaderInspection.is_valid is True`, đúng `num_lsb`, `secret_shape`, `ciphertext_len`.
   - Ảnh RGB ngẫu nhiên không giấu tin $\rightarrow$ `is_valid is False` (sai magic `HCST`).
   - `"flip_header_bit"` $\rightarrow$ `is_valid is False` và báo lỗi `CRC`.
   - `"jpeg_q95"` $\rightarrow$ giải mã thất bại đúng như lý thuyết LSB.
   - `"flip_payload_bits"` & `"gaussian_noise"` $\rightarrow$ phát hiện lỗi giải mã hoặc `is_exact is False`.
4. **Test nạp dữ liệu Benchmark (`load_benchmark_bundle`):**
   - Đọc đúng `results/benchmark_summary_table2.csv`, đủ 3 hàng (`3des`, `aes`, `chaotic`) và khớp khóa với `PAPER_TABLE2_REFERENCE`.
5. **Smoke test khởi tạo cửa sổ `CT204App`:**
   - Khởi tạo `root = tk.Tk(); root.withdraw()`, dựng `CT204App(root)`, gọi `root.update_idletasks()`, sau đó `root.destroy()` sạch sẽ (bọc `pytest.skip` nếu chạy trên môi trường headless Linux không có Tcl/Tk display, nhưng trên Windows `.venv` phải chạy thật và PASS).

---

## 6. Kế hoạch Đóng gói `.exe` Độc lập bằng PyInstaller (`Giai đoạn 6B` — Sau khi nghiệm thu UI)

Để sau này chuyển sang `.exe` nộp kèm đồ án trơn tru không phát sinh lỗi ẩn, quy trình đóng gói chuẩn ở Giai đoạn 6B được thiết kế sẵn như sau:

### 6.1. Xử lý đặc thù `Numba` + `PyInstaller` trong `SOURCES/app.py`
Ngay ở đầu `SOURCES/app.py` (**trước khi** import `src.ui` hay `src.crypto`):
```python
import os
import sys
import tempfile
from pathlib import Path

if getattr(sys, "frozen", False):
    cache_dir = Path(tempfile.gettempdir()) / "ct204_hybrid_crypto_stego_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("NUMBA_CACHE_DIR", str(cache_dir))
```
Và trong file cấu hình `ct204_app.spec` của PyInstaller (6.x+), đặt `module_collection_mode={"src": "pyz+py"}` để `src/crypto/chaotic_cipher.py` luôn có mặt dưới dạng `.py` cho trình biên dịch `@numba.njit(cache=True)`.

### 6.2. Tài nguyên nhúng kèm gói `.exe` (`datas` trong PyInstaller)
Chỉ nhúng những file gọn nhẹ cần thiết (tổng dung lượng dữ liệu < 15 MB, **không** nhúng 8.000 ảnh gốc Linnaeus 5):
- `configs/default.yaml` $\rightarrow$ `configs/`
- `data/sample/cover.jpg`, `data/sample/secret.png` $\rightarrow$ `data/sample/`
- `results/benchmark_summary_table2.csv`, `results/benchmark_results.csv` $\rightarrow$ `results/`
- `results/single/*.png`, `results/single/single_metrics.csv` $\rightarrow$ `results/single/`

### 6.3. Hai phương án xuất bản `.exe`
1. **Phương án Khuyên dùng khi Nộp Đồ án & Bảo vệ (`--onedir --windowed`):**
   - Xuất ra thư mục `dist/CT204_CryptoStego/CT204_CryptoStego.exe` (nén `.zip` đính kèm đồ án).
   - **Ưu điểm lớn:** Bấm đúp mở cửa sổ lên ngay trong **~1–2 giây** (không tốn thời gian giải nén `Numba + OpenCV + SciPy + Matplotlib` vào `%TEMP%` mỗi lần mở).
2. **Phương án 1 File Duy nhất (`--onefile --windowed`):**
   - Xuất ra 1 file độc lập `dist/CT204_CryptoStego_Single.exe` (~150–220 MB), tiện chép USB chạy nhanh (thời gian khởi động lần mở ~5–8 giây).

---

## 7. Phân công Thực hiện & Tiêu chí Nghiệm thu (Definition of Done)

| Bước | Nội dung công việc | Người thực hiện | Người nghiệm thu |
|---|---|---|---|
| **GĐ 6A — Code UI** | Cài đặt `SOURCES/app.py`, toàn bộ `SOURCES/src/ui/*`, cập nhật `requirements.txt` (thêm `Pillow`) và viết `SOURCES/tests/test_ui_controller.py` | **Claude Code (Opus)** | **Gemini** (Audit code + chạy full `pytest` + kiểm tra chạy thử app) & **Bạn** |
| **GĐ 6B — Đóng gói `.exe`** | Cài `pyinstaller` vào `.venv` (hoặc môi trường build), tạo `SOURCES/packaging/ct204_app.spec` + `build_exe.ps1`, xuất `.exe` và kiểm thử chạy độc lập ngoài `.venv` | **Claude Code** hoặc **Gemini** + **Bạn** | **Bạn** chạy thử file `.exe` thực tế trên Windows |

### Checklist Nghiệm thu Giai đoạn 6A (dành cho Claude Code & Gemini Audit):
- [x] `git diff src/config.py src/crypto src/stego src/metrics src/pipeline.py scripts` **trống hoàn toàn (0 dòng thay đổi trên code lõi)**.
- [x] Chạy `.\.venv\Scripts\pytest.exe -v` từ `SOURCES/` đạt **100% PASSED** (toàn bộ 275 test cũ + 72 test mới trong `tests/test_ui_controller.py` = **347/347 PASSED**).
- [x] Chạy `.\.venv\Scripts\python.exe app.py` từ `SOURCES/` mở lên giao diện sạch đẹp (~5.5s), tiếng Việt hiển thị rõ nét, đủ 4 Tab hoạt động trơn tru không văng lỗi console.
- [x] Tab 1 mã hóa – nhúng tin – lưu `.png` và chuyển sang Tab 2 giải mã đạt `MSE == 0` cho cả 3 thuật toán ở cả 2 chế độ khóa (`Seed 2025` và `Passphrase`).
- [x] Tab 2 demo đủ 5 nút kịch bản tấn công độc lập (`Sai khóa`, `Nén JPEG Q=95`, `Đảo 1 bit Header tại flat[87]`, `Đảo 1% bit Payload`, `Nhiễu Gaussian σ=2`) và nút Reset hoạt động đúng theo mọi thứ tự bấm.
- [x] Tab 3 vẽ đúng lưới Hình 5 bài báo & bảng so sánh 3 thuật toán không làm treo cửa sổ; xuất bộ ảnh trên worker thread bằng `FigureCanvasAgg` an toàn.
- [x] Tab 4 đọc offline thành công CSV 8.000 ảnh, hiển thị bảng đối chiếu Bảng 2 bài báo và lọc biểu đồ mượt theo lớp ảnh Linnaeus 5.
