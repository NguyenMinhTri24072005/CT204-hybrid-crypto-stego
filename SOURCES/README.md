# SOURCES – Mã nguồn Python

Đây là mã nguồn của đồ án CT204. Phần tổng quan và kết quả nằm ở [README gốc](../README.md).

Mọi lệnh dưới đây chạy **trong thư mục `SOURCES/`** bằng các tệp thực thi của `.venv` (Python 3.12, xem `.python-version`).

## Cài đặt

```powershell
py -3.12 -m venv .venv
```
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Các thư viện chính:
- `pycryptodome` (3DES, AES);
- `numpy`, `numba` (ánh xạ logistic biên dịch JIT);
- `opencv-python`, `scikit-image`, `scipy`;
- `pandas`, `matplotlib`, `PyYAML`, `Pillow`, `tqdm`, `pytest`.

## Kiến trúc

```text
secret (H×W uint8) → bytes → BaseCipher.encrypt → ciphertext
  → lsb.embed(cover, header + ciphertext) → stego (.png)
  → lsb.extract(stego) → header + ciphertext → BaseCipher.decrypt → reshape(H, W) → recovered
metrics: visual (cover ↔ stego) · security (secret ↔ encrypted, và trên stego)
```

| Đường dẫn | Vai trò |
|---|---|
| `configs/default.yaml` | Nguồn tham số duy nhất: seed khóa, `x0`, `r`, `ecc_seed`, kích thước khóa/IV, `max_lsb`, đường dẫn. Đọc qua `src.config.load_config()` |
| `src/crypto/base.py` | Lớp trừu tượng `BaseCipher` (`encrypt`/`decrypt`) và `derive_bytes(seed, length, label)`. Hàm này sinh khóa/IV tất định có tách miền theo `SHA-256(f"{seed}:{label}")` |
| `src/crypto/des3_cipher.py` | 3DES-192, CBC, EDE, PKCS#7 (khóa 24 B, IV 8 B, dùng `DES3.adjust_key_parity`) |
| `src/crypto/aes_cipher.py` | AES-128, CBC, PKCS#7 (khóa 16 B, IV 16 B) |
| `src/crypto/chaotic_cipher.py` | `enc = S ⊕ chaos_mask ⊕ ecc_mask`. `chaos_mask[n] = clip(floor(x·256), 0, 255)` với ánh xạ logistic chạy bằng `@numba.njit`. `ecc_mask = default_rng(ecc_seed)`. Mã hóa và giải mã là cùng một phép XOR |
| `src/stego/lsb.py` | `embed` / `extract` LSB đa bit, vector hóa bằng `np.unpackbits`/`packbits`, tự chọn `num_lsb` và phóng to ảnh phủ khi cần |
| `src/pipeline.py` | `hide`, `reveal`, `run_pipeline`, `run_from_config`; đọc/ghi ảnh (`save_stego_png` chỉ cho phép PNG) |
| `src/metrics/visual.py` | MSE, PSNR, SSIM (Gaussian σ = 1,5 kiểu MATLAB) |
| `src/metrics/security.py` | `measure_enc_time`, NPCR, UACI, entropy, hệ số tương quan, tương quan điểm ảnh kề nhau, `compute_dual_security_metrics` |
| `src/ui/` | Ứng dụng Tkinter: `controller.py` không phụ thuộc Tk nên kiểm thử được; còn có `app_window.py`, `tabs/`, `widgets.py`, `worker.py` (luồng nền), `plots.py`, `theme.py` |
| `scripts/run_single.py` | Chạy một cặp ảnh qua 3 thuật toán, xuất ảnh và histogram (Hình 4–5 của bài báo) |
| `scripts/run_benchmark.py` | Chạy hàng loạt trên Linnaeus 5, xuất CSV (Bảng 2 của bài báo) |
| `notebooks/visualize_results.ipynb` | Phân tích và vẽ biểu đồ từ CSV benchmark |
| `packaging/ct204_app.spec` | Cấu hình PyInstaller (chế độ onedir) |

### Header giấu tin (16 byte, luôn nhúng ở 1 LSB)

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| magic | 4 B | `HCST` |
| version | 1 B | `1` |
| num_lsb | 1 B | 1–3 |
| H, W | 2 B + 2 B | kích thước ảnh bí mật |
| ciphertext_len | 4 B | độ dài bản mã |
| crc | 2 B | 16 bit thấp của CRC32 trên 14 byte đầu |

Định dạng `struct` là `">4sBBHHIH"`. Bản mã được nhúng ngay sau header với `num_lsb` bit trên mỗi kênh màu, nên khi trích xuất chỉ cần ảnh stego và bộ giải mã.

## Dòng lệnh

### `scripts.run_single`

```powershell
.\.venv\Scripts\python.exe -m scripts.run_single
```

| Tùy chọn | Ý nghĩa |
|---|---|
| `--config PATH` | Tệp YAML khác thay cho `configs/default.yaml` |
| `--cover PATH` / `--secret PATH` | Thay ảnh phủ RGB / ảnh bí mật xám |
| `--secret-size H W` | Resize ảnh bí mật (ví dụ `156 156` để dùng đúng 1-LSB như Bảng 2) |
| `--out-dir PATH` | Thư mục kết quả (mặc định `results/single`) |
| `--cache-chaotic-mask` | Sinh sẵn mặt nạ chaotic trước khi đo thời gian |
| `--quiet` | Không in bảng tóm tắt |

Mặc định chương trình dùng `data/sample/cover.jpg` và ảnh *coins* 246×300. Kết quả là 3 thuật toán đều dùng 3-LSB, ảnh phủ được phóng lên 257×257, và tất cả đều khôi phục chính xác.

### `scripts.run_benchmark`

```powershell
.\.venv\Scripts\python.exe -m scripts.run_benchmark --secret-size 156 156 --cache-chaotic-mask
```

| Tùy chọn | Ý nghĩa |
|---|---|
| `--data-dir PATH` | Thư mục gốc Linnaeus 5 (mặc định `data/linnaeus5`) |
| `--secret PATH`, `--secret-size H W` | Ảnh bí mật và kích thước |
| `--limit N` | Chỉ chạy N ảnh phủ đầu tiên, dùng để thử nhanh |
| `--vary-key-per-image` | Mỗi ảnh dùng một khóa/IV/seed riêng (seed + chỉ số ảnh) |
| `--cache-chaotic-mask` | Không tính thời gian sinh mặt nạ vào EncTime của Chaotic |
| `--out-dir PATH`, `--csv-name NAME` | Nơi lưu và tên CSV chi tiết |
| `--config PATH`, `--quiet` | Như trên |

Chương trình xuất hai tệp:
- `results/benchmark_results.csv`: mỗi dòng là một cặp ảnh × thuật toán;
- `results/benchmark_summary_table2.csv`: giá trị trung bình và độ lệch chuẩn theo từng thuật toán.

Ví dụ chạy thử 50 ảnh:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_benchmark --limit 50 --secret-size 156 156
```

### Ứng dụng desktop

```powershell
.\.venv\Scripts\python.exe app.py
```
```powershell
.\.venv\Scripts\python.exe app.py --smoke
```

`--smoke` dựng đủ 4 tab rồi tự thoát, dùng để kiểm tra khởi động.

### Đóng gói `.exe`

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
```
```powershell
.\.venv\Scripts\pyinstaller.exe packaging\ct204_app.spec
```

Kết quả nằm ở `dist/CT204_CryptoStego/CT204_CryptoStego.exe`. Bản đóng gói có kèm cấu hình, ảnh mẫu và CSV kết quả, nhưng không kèm 8.000 ảnh Linnaeus 5. Cache Numba được đặt trong thư mục tạm của hệ điều hành.

## Kiểm thử

```powershell
.\.venv\Scripts\pytest.exe -q
```
```powershell
.\.venv\Scripts\pytest.exe tests/test_crypto.py -q
```

| Tệp | Nội dung |
|---|---|
| `tests/test_crypto.py` | Mã hóa rồi giải mã khôi phục đúng, kích thước khóa/IV, padding, tính tất định |
| `tests/test_lsb.py` | Nhúng/trích xuất, header và CRC, chọn `num_lsb`, phóng to ảnh phủ |
| `tests/test_metrics.py` | Các công thức MSE/PSNR/SSIM/NPCR/UACI/entropy/tương quan |
| `tests/test_pipeline.py` | Đầu cuối: ảnh khôi phục trùng khớp, MSE = 0 |
| `tests/test_ui_controller.py` | Controller của UI: chế độ khóa, Tamper Lab, so sánh, dashboard |

Tổng cộng có 347 bài kiểm thử, chạy mất khoảng 40 giây.

## Lưu ý

- **Không hard-code tham số.** Mọi giá trị đều lấy từ `configs/default.yaml`.
- **Khóa sinh tất định từ `crypto.key_seed`** nên các lần chạy cho kết quả lặp lại được. Khóa không bao giờ được lưu trong ảnh stego.
- **Đo EncTime chỉ tính `cipher.encrypt`**, dùng `time.perf_counter()`. Thuật toán Chaotic được chạy khởi động một lần trước để loại thời gian biên dịch JIT.
- **Bỏ qua khi commit:** `data/linnaeus5/` và các kết quả chạy tùy ý được bỏ qua qua `SOURCES/.gitignore`. Chỉ hai CSV chính thức và `results/single/` được commit.
