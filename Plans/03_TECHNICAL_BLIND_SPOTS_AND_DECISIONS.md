# Hồ sơ Điểm mù Kỹ thuật của Bài báo Gốc & Quyết định Thiết kế (ADR)

**Dự án:** Tái hiện bài báo *"A Hybrid Crypto-Steganography Framework for Secure Image Transfer"* (ICITSC 2025, trang 175–182) từ MATLAB R2024a sang Python 3.12.  
**Mục đích tài liệu:** Ghi nhận đầy đủ **10 điểm mù kỹ thuật (Technical Blind Spots)** mà bài báo gốc bỏ ngỏ hoặc mâu thuẫn nội tại, phân tích các phương án giải quyết, **chốt 1 phương án tối ưu nhất cho mỗi điểm mù** kèm lý do khoa học/kỹ thuật, làm căn cứ thiết kế chính thức cho [01_TECHNICAL_SPEC.md](./01_TECHNICAL_SPEC.md) và [02_EXECUTION_PLAN_AND_ROLES.md](./02_EXECUTION_PLAN_AND_ROLES.md).

---

## Bảng Tóm tắt Nhanh 10 Quyết định Thiết kế Đã Chốt

| Mã | Điểm mù kỹ thuật trong bài báo | Phương án được chọn (Best Proposal) | Tác động tới Giai đoạn |
|---|---|---|---|
| **BM-01** | Kích thước ảnh `coins` không công bố; mâu thuẫn giữa Hình 5 và `MSE ≈ 0.50` ở Bảng 2 | Chuẩn hóa `data/sample/secret.png` về `246×300` (chuẩn `coins.png` MATLAB) + hỗ trợ `secret.resize: [156, 156]` (khớp 1-LSB Bảng 2) | GĐ3, GĐ4, GĐ5 |
| **BM-02** | Thứ tự trải phẳng byte ảnh (`Column-major` Planar MATLAB vs `Row-major` NumPy) | Chuẩn hóa `Row-major` (C-contiguous) & Pixel-interleaved RGB `(H, W, 3)` xuyên suốt | GĐ2, GĐ3 |
| **BM-03** | Không công bố giá trị Key/IV/Seed và quy ước khóa qua 8,000 ảnh | Sinh khóa tất định tách miền `SHA-256(f"{seed}:{cipher}:{role}")`; mặc định khóa cố định + thêm cờ `--vary-key-per-image` cho benchmark | GĐ2, GĐ4 |
| **BM-04** | Không nêu công thức ép $x_n \in (0,1)$ sang `uint8`; "ECC Mask" không có đường cong Elliptic | Dùng `clip(int(floor(x * 256.0)), 0, 255)` trên `float64` từ $x_1 \dots x_N$ + `default_rng(ecc_seed).integers(0, 256, dtype=uint8)` | GĐ2 |
| **BM-05** | Không nêu chuẩn Padding cụ thể; bản mã sau pad dài hơn $H_s \times W_s$ không reshape được | Dùng **PKCS#7** đầy đủ khi nhúng/giải mã; cắt `ciphertext[:H_s*W_s]` **chỉ** khi dựng ảnh minh họa & tính NPCR/UACI | GĐ2, GĐ3, GĐ4 |
| **BM-06** | Không có cơ chế truyền Metadata (`num_lsb`, kích thước ảnh, độ dài mã) sang phía nhận | Thiết kế **Header nhị phân cố định 16-byte (128 bit)** có `magic="HCST"` + `CRC16` ở `1-LSB` tại `flat[0:128]`; Payload từ `flat[128:]` | GĐ3 |
| **BM-07** | Không nêu công thức phóng đại Cover khi tràn 3-LSB và ảnh gốc đối chiếu tính MSE | Tăng `num_lsb` `1 → 2 → 3` trước; nếu tràn 3-LSB thì giữ `num_lsb=3`, phóng đại đẳng hướng bằng `cv2.INTER_CUBIC`; tính MSE giữa `cover_used` và `stego` | GĐ3, GĐ4 |
| **BM-08** | Mâu thuẫn đối tượng đo `Entropy`, `NPCR`, `UACI`, `Correlation` (Encrypted vs Stego) ở Bảng 2 | Tính và xuất **song song cả 2 nhóm độ đo** (`*_enc` và `*_stego`) kèm bảng ghép "Table 2 Aligned View" | GĐ4, GĐ5 |
| **BM-09** | Mẫu số `MSE` ghi $M \times N$ cho ảnh màu; `Correlation` mô tả 2 kiểu khác nhau | `MSE` chia cho $H \times W \times 3$ (khớp `immse` MATLAB); cài cả `cross_correlation` (trung bình 3 kênh RGB / 2D) lẫn `adjacent_pixel_correlation` | GĐ4 |
| **BM-10** | Cách vẽ Histogram ảnh màu RGB (Hình 4c & 5) và phạm vi đo `EncTime` của Chaotic | Vẽ Histogram RGB gộp phẳng `img_rgb.ravel()` (256 bins); `ChaoticCipher` mặc định `cache_mask=False` (sau `warmup()`) nhưng hỗ trợ tùy chọn `cache_mask=True` | GĐ2, GĐ4 |

---

## Chi tiết Phân tích Từng Điểm mù, Đề xuất & Lý do Lựa chọn

### BM-01: Kích thước thực của ảnh bí mật (`coins`) và nghịch lý sức chứa 1-LSB vs 3-LSB

- **Điểm mù & Bằng chứng từ bài báo:**
  - Mục 5 (trang 180) chỉ ghi *"Secret Image, a grayscale picture of coins"*, không công bố kích thước `(H, W)`. Trong Python `skimage.data.coins()` có kích thước `303 × 384 = 116,352 B`, còn `coins.png` có sẵn của MATLAB có kích thước `246 × 300 = 73,800 B`.
  - **Bằng chứng từ Hình 5:** Trục tung của `Histogram of Encrypted Secret` cao đồng đều `~288` pixel/mức xám $\Rightarrow 288.28 \times 256 = \mathbf{73,800\text{ B}}$ (chứng minh tác giả dùng `coins.png` `246×300` của MATLAB). Do `73,808 B` (sau PKCS7) vượt nhẹ trần 3-LSB của ảnh `256×256×3` (`73,728 B`), ảnh cover ở Hình 5 đã bị phóng đại nhẹ (trục tung `Stego Histogram` tăng từ `~6,300` lên `~8,200`).
  - **Nghịch lý với Bảng 2:** Nếu nhúng ở 3-LSB thì sai số kỳ vọng phải là $\text{MSE} \approx 10.5$ ($\text{PSNR} \approx 37.9\text{ dB}$). Ngược lại, Bảng 2 ghi nhận `Avg. MSE ≈ 0.5000`, `Avg. PSNR ≈ 51.15 dB` — đây chính xác là hằng số toán học của phép nhúng **1-LSB lấp đầy gần 100% kênh màu** ($\mathbb{E}[\Delta^2] = 0.5 \times 1^2 = 0.50 \Rightarrow 10\log_{10}(255^2/0.5) = 51.141\text{ dB}$, tương đương payload `~24,560 B` hay ảnh cỡ `156 × 156`).
- **Các phương án đề xuất:**
  1. *Phương án A:* Cố định cứng ảnh `skimage.data.coins()` gốc (`303×384`) cho mọi tác vụ $\rightarrow$ luôn tràn 3-LSB, ra `MSE ≈ 10.5`, không thể tái hiện được `MSE ≈ 0.50` của Bảng 2.
  2. *Phương án B:* Cố định cứng ảnh resize `156×156` cho mọi tác vụ $\rightarrow$ khớp Bảng 2 nhưng mất khả năng tái hiện đúng Hình 4–5 và không kiểm chứng được nhánh 2–3 LSB / scale-up trên dữ liệu thật.
  3. *Phương án C (Tối ưu):* Tạo file mẫu `SOURCES/data/sample/secret.png` ở kích thước **`246 × 300`** (resize từ `skimage.data.coins()` bằng `cv2.INTER_AREA` để khớp đúng `coins.png` của MATLAB), đồng thời hỗ trợ tham số `secret.resize` trong `default.yaml` và cờ CLI `--secret-size H W` ở `run_single.py` / `run_benchmark.py`.
- **Quyết định chọn:** **Phương án C.**
- **Tại sao chọn:** Cho phép tái hiện chính xác **cả hai phần thực nghiệm của bài báo**: dùng `246×300` (`resize: null`) khi chạy `run_single.py` để khớp trực quan Hình 4–5, và dùng `resize: [156, 156]` (`24,336 B`, chiếm `99.1%` sức chứa 1-LSB của `256×256×3`) khi chạy `run_benchmark.py` để tái hiện sát sạt `MSE ≈ 0.50, PSNR ≈ 51.15 dB` của Bảng 2.

---

### BM-02: Thứ tự trải phẳng byte ảnh (`Column-major` của MATLAB vs `Row-major` của Python/NumPy)

- **Điểm mù & Bằng chứng từ bài báo:**
  - Bài báo chỉ viết *"Convert secret image to bytes"* và *"Embed across R, G, B channels"*. MATLAB trải phẳng mảng `H × W × 3` theo cột (`Fortran order`) và đi hết toàn bộ kênh `R` rồi mới sang kênh `G`, kênh `B`; trong khi NumPy mặc định trải theo hàng (`C order`) và xen kẽ `[R, G, B]` tại từng pixel.
- **Các phương án đề xuất:**
  1. *Phương án A:* Ép `order="F"` và `.transpose(2, 0, 1)` ở mọi bước để mô phỏng bộ nhớ MATLAB $\rightarrow$ phát sinh nhiều bản sao mảng không liên tục (`non-contiguous copies`), giảm tốc độ khi chạy 24,000 lượt và dễ gây lỗi lệch trục.
  2. *Phương án B (Tối ưu):* Chuẩn hóa đồng nhất theo **`Row-major` (C-contiguous) & Pixel-interleaved RGB `(H, W, 3)`** chuẩn của NumPy ở cả chiều mã hóa/nhúng lẫn chiều tách/giải mã.
- **Quyết định chọn:** **Phương án B.**
- **Tại sao chọn:** Mọi độ đo đánh giá (MSE, PSNR, Entropy, NPCR, UACI) đều bất biến 100% đối với hoán vị thứ tự pixel/kênh khi bit nhúng là ngẫu nhiên đều, trong khi C-order cho phép dùng `np.frombuffer` zero-copy và đạt tốc độ cao nhất trên Python.

---

### BM-03: Cơ chế sinh Key/IV/Seed và Quy ước khóa qua 8,000 ảnh Benchmark

- **Điểm mù & Bằng chứng từ bài báo:**
  - Bài báo không công bố giá trị cụ thể của khóa 3DES (24B), khóa AES (16B), IV hay `seed` của ECC Mask; cũng không nêu rõ trong vòng lặp 8,000 ảnh thì dùng 1 bộ khóa cố định hay sinh khóa mới cho từng ảnh.
- **Các phương án đề xuất:**
  1. *Phương án A:* Sinh ngẫu nhiên bằng `os.urandom()` mỗi lần chạy $\rightarrow$ kết quả thay đổi mỗi lần chạy, vi phạm tính tái lập khoa học và khó viết unit test tất định.
  2. *Phương án B:* Khởi tạo `np.random.default_rng(key_seed)` trực tiếp trong từng lớp cipher $\rightarrow$ 16 byte đầu của khóa 3DES trùng hệt 16 byte khóa AES-128.
  3. *Phương án C (Tối ưu):* Sinh khóa tất định có **phân tách miền (domain separation)** qua hàm băm `SHA-256(f"{key_seed}:{cipher_name}:{role}")` làm hạt giống cho `np.random.default_rng`. Mặc định giữ khóa cố định theo `crypto.key_seed: 2025` và `ecc_seed: 42`; bổ sung thêm cờ tùy chọn `--vary-key-per-image` ở `run_benchmark.py` (cộng `image_index` vào seed) để khảo sát trung bình thống kê của NPCR/UACI qua 8,000 khóa khác nhau.
- **Quyết định chọn:** **Phương án C.**
- **Tại sao chọn:** Đảm bảo an toàn mật mã học (khóa 3DES, khóa AES và các IV hoàn toàn độc lập thống kê), tái lập 100% kết quả thực nghiệm mà không cần nhúng khóa vào ảnh stego, đồng thời hỗ trợ kiểm chứng cả kịch bản khóa tĩnh lẫn khóa động trên tập 8,000 ảnh.

---

### BM-04: Quy tắc lượng tử hóa số thực Logistic Map $x_n \in (0, 1)$ sang `uint8` & Bản chất "ECC Mask"

- **Điểm mù & Bằng chứng từ bài báo:**
  - Mục 4.3.1 chỉ ghi *"scaled to the range 0–255 to form the chaotic mask"*, không có công thức làm tròn. Trong MATLAB, `uint8(x * 255)` làm tròn `round`, khiến hai mức biên `0` và `255` chỉ có độ rộng khoảng bằng một nửa các mức `1..254`. Đồng thời, Mục 4.3.2 gọi là *"ECC Mask (Simulated)"* nhưng bản chất chỉ là mảng `uint8` sinh từ PRNG với seed cố định, hoàn toàn không có phép toán đường cong Elliptic.
- **Các phương án đề xuất:**
  1. *Phương án A:* Dùng `np.rint(x * 255.0)` mô phỏng hàm ép kiểu `uint8` của MATLAB $\rightarrow$ gây lệch phân phối tại 2 đầu mút `0` và `255`.
  2. *Phương án B:* Dùng phép trích xuất chữ số thập phân bậc cao `floor((x * 1e14) % 256)` $\rightarrow$ đi xa khỏi mô tả *"scaled to the range 0–255"* của bài báo.
  3. *Phương án C (Tối ưu):* Tính lặp $x_{n+1} = r \cdot x_n \cdot (1 - x_n)$ trên `float64` (lấy từ $x_1$ đến $x_N$, bỏ $x_0$), lượng tử hóa bằng **`clip(int(np.floor(x * 256.0)), 0, 255)`** bên trong `@numba.njit(cache=True)`, kết hợp `ecc_mask = np.random.default_rng(ecc_seed).integers(0, 256, size=N, dtype=np.uint8)`.
- **Quyết định chọn:** **Phương án C.**
- **Tại sao chọn:** Bám sát đúng mô tả *"scaled to 0–255"* của bài báo nhưng chia miền `[0, 1)` thành đúng 256 khoảng đều nhau `[k/256, (k+1)/256)`, không bị lệch biên, tốc độ biên dịch mã máy Numba cực cao và tất định tuyệt đối.

---

### BM-05: Chuẩn Padding của 3DES/AES và Cách khớp kích thước khi dựng "Encrypted Secret Image"

- **Điểm mù & Bằng chứng từ bài báo:**
  - Bảng 1 ghi `Padding: 8 bytes` (3DES) và `16 bytes` (AES) mà không ghi tên chuẩn. Sau khi thêm padding, `len(ciphertext) > H_s * W_s` nên không thể reshape trực tiếp về `(H_s, W_s)`. Trên thực tế, ở góc phải của [fig5_aes_encrypted_hist.jpeg](../Docs/145987_assets/fig5_aes_encrypted_hist.jpeg) xuất hiện một gai nhọn bất thường ở mức `255` (cao gấp đôi mức trung bình `~288` lên gần `600`), chứng tỏ tác giả đã chèn thêm hàng trăm byte đệm `255` để ép thành ma trận chữ nhật lớn hơn khi vẽ ảnh!
- **Các phương án đề xuất:**
  1. *Phương án A:* Dùng Zero-padding $\rightarrow$ làm hỏng byte `0x00` hợp lệ ở cuối ảnh bí mật khi giải mã (vi phạm yêu cầu khôi phục nguyên vẹn `MSE == 0`).
  2. *Phương án B:* Đệm thêm `255` cho đủ dòng mới khi dựng ảnh mã hóa $\rightarrow$ tạo gai giả tạo trên Histogram và làm sai lệch Entropy/UACI của bản mã.
  3. *Phương án C (Tối ưu):* Dùng chuẩn **PKCS#7** (`Crypto.Util.Padding`) và nhúng **đầy đủ 100% byte của `ciphertext`** vào ảnh stego để giải mã không suy hao; riêng khi dựng ảnh hiển thị 2D hoặc đo NPCR/UACI/Correlation với ảnh gốc `(H_s, W_s)`, cung cấp hàm chuẩn hóa `ciphertext_to_image_view(ciphertext, secret_shape)` cắt đúng `H_s * W_s` byte đầu (`ciphertext[:H_s * W_s]`).
- **Quyết định chọn:** **Phương án C.**
- **Tại sao chọn:** Khôi phục ảnh bí mật đạt `MSE = 0` trong mọi trường hợp biên (kể cả ảnh toàn màu đen `0x00` hay kích thước chia hết cho 8/16), đồng thời giữ cho Histogram và các chỉ số thống kê của ảnh mã hóa phản ánh trung thực phân phối của bản mã mà không sinh nhiễu giả tạo ở mức `255`.

---

### BM-06: Thiết kế Header cho phép Tách và Giải mã Độc lập (Blind Extraction)

- **Điểm mù & Bằng chứng từ bài báo:**
  - Bài báo hoàn toàn không nhắc tới việc lưu kích thước ảnh gốc `(H_s, W_s)`, độ dài bản mã `ciphertext_len` hay `num_lsb` ở đâu. Nếu truyền qua biến phụ trong bộ nhớ thì người nhận chỉ cầm file `stego.png` không thể giải mã được.
- **Các phương án đề xuất:**
  1. *Phương án A:* Truyền tham số bên ngoài vào hàm `extract(stego, num_lsb, length, shape)` $\rightarrow$ không đáp ứng yêu cầu giải mã độc lập 100%.
  2. *Phương án B:* Nhúng chuỗi phân cách kết thúc (`delimiter`) ở cuối bản mã $\rightarrow$ bản mã AES/3DES là nhị phân ngẫu nhiên nên có thể ngẫu nhiên trùng chuỗi phân cách, gây cắt cụt bản mã.
  3. *Phương án C (Tối ưu):* Thiết kế **Header nhị phân cố định 16 bytes (128 bits)** theo format Big-Endian `>4sBBHHIH` (`magic=b"HCST"`, `version=1`, `num_lsb`, `secret_h`, `secret_w`, `ciphertext_len`, `crc16`), luôn nhúng ở **`1-LSB` tại 128 giá trị kênh màu đầu tiên (`flat[0:128]`)**; toàn bộ vùng Payload nhúng tách biệt từ **`flat[128:]`** với `num_lsb ∈ {1, 2, 3}`.
- **Quyết định chọn:** **Phương án C.**
- **Tại sao chọn:** Giải mã độc lập 100% chỉ từ `(stego_png, cipher)`, không bao giờ xảy ra xung đột ghi đè giữa Payload (dù ở 2 hay 3 LSB) và Header (ở 1 LSB), có `magic` + `CRC16` phát hiện tức thì ảnh không giấu tin hoặc ảnh bị hỏng do nén JPEG, và chỉ tốn 128 bit (`0.065%` ảnh `256×256`).

---

### BM-07: Quy tắc chọn `num_lsb`, Phóng đại ảnh Cover (Auto Scale-up) & Ảnh đối chiếu tính MSE

- **Điểm mù & Bằng chứng từ bài báo:**
  - Mục 4.3.3 nêu *"If the bits needed exceed capacity, the cover image is resized (scaled up)"*, nhưng không chỉ rõ: sau khi phóng đại thì nhúng mấy LSB, phóng đại theo công thức nào, và khi tính MSE/PSNR thì lấy ảnh nào trừ cho ảnh `stego` (vì ảnh cover gốc `256×256` khác kích thước với ảnh `stego` đã phóng đại!).
- **Các phương án đề xuất:**
  1. *Phương án A:* Phóng đại ảnh cover ngay khi vượt 1-LSB $\rightarrow$ bỏ phí bậc 2-LSB và 3-LSB đã mô tả ở Mục 4.1 & 4.2.
  2. *Phương án B:* Khi tràn 3-LSB, phóng đại ảnh cover rồi hạ ngược về 1-LSB $\rightarrow$ kích thước ảnh phình to gấp ~3 lần diện tích cần thiết.
  3. *Phương án C (Tối ưu):* Ưu tiên chọn `num_lsb` nhỏ nhất trong `{1, 2, 3}` trên ảnh cover hiện tại; chỉ khi $B > (3 H_c W_c - 128) \times 3$ mới giữ `num_lsb = 3` và phóng đại đẳng hướng tối thiểu theo hệ số $s = \sqrt{(\lceil B/3 \rceil + 128) / (3 H_c W_c)}$ bằng nội suy `cv2.INTER_CUBIC`. Khi đo MSE/PSNR/SSIM, thực hiện giữa **`cover_used` (ảnh cover sau bước chuẩn hóa kích thước dùng để nhúng)** và **`stego_rgb`**.
- **Quyết định chọn:** **Phương án C.**
- **Tại sao chọn:** Khớp đúng lưu đồ thuật toán Mục 4.1–4.3, tối thiểu hóa mức thay đổi kích thước ảnh (ví dụ ảnh `coins` `246×300` chỉ làm ảnh cover tăng từ `256×256` lên `257×257`!), và đảm bảo phép đo độ méo do giấu tin (Cover vs. Stego) luôn hợp lệ toán học.

---

### BM-08: Mâu thuẫn Đối tượng Đo của `Entropy`, `NPCR`, `UACI`, `Correlation` trong Bảng 2

- **Điểm mù & Bằng chứng từ bài báo:**
  - Mục 4.4 định nghĩa NPCR, UACI, Entropy, CC giữa **Secret và Encrypted Secret**, nhưng Mục 4.2 bước 9 lại viết tính các chỉ số này **"for each stego image"**.
  - Kiểm chứng toán học trên Bảng 2: `NPCR ≈ 99.61%` ($255/256 = 99.609\%$), `UACI ≈ 30.8%` và `CC ≈ 0` chắc chắn đo trên **Secret vs. Encrypted**; trái lại `Avg. Entropy ≈ 7.047` (3DES/AES) và `6.953` (Chaotic) thấp hơn hẳn mức `~7.998` của bản mã khối chuẩn, trùng khớp với **Entropy của ảnh màu tự nhiên (Stego Image)**!
- **Các phương án đề xuất:**
  1. *Phương án A:* Chỉ xuất độ đo trên ảnh Encrypted $\rightarrow$ lệch cột `Entropy` so với Bảng 2.
  2. *Phương án B:* Chỉ xuất độ đo trên ảnh Stego $\rightarrow$ lệch cột `NPCR`, `UACI`, `Correlation` so với Bảng 2.
  3. *Phương án C (Tối ưu):* Cài đặt các hàm trong `src/metrics/security.py` độc lập đối tượng (nhận mảng `uint8` 2D/3D bất kỳ) và trong pipeline/CSV xuất **đầy đủ cả 2 nhóm cột** (`*_enc` đo trên Secret/Encrypted và `*_stego` đo trên Cover/Stego), kèm bảng tóm tắt ánh xạ trực tiếp sang Bảng 2.
- **Quyết định chọn:** **Phương án C.**
- **Tại sao chọn:** Minh bạch khoa học 100%, không gọt chân cho vừa giày mà cung cấp đầy đủ bằng chứng thực nghiệm giải thích trọn vẹn mọi con số trong Bảng 2 cho báo cáo môn CT204.

---

### BM-09: Mẫu số công thức `MSE` trên ảnh màu RGB và Định nghĩa `Correlation Coefficient`

- **Điểm mù & Bằng chứng từ bài báo:**
  - Eq. (3) viết mẫu số MSE là $M \times N$ (công thức sách giáo khoa cho ảnh xám), trong khi áp dụng cho ảnh màu RGB `256×256×3`. Nếu chia cho $M \times N$ thì nhúng 1-LSB sẽ ra `MSE = 1.50` thay vì `0.50` như Bảng 2!
  - Với `Correlation`: Mục 4.4.5 mô tả tương quan chéo giữa ảnh gốc và ảnh mã hóa, còn Mục 4.1 bước 6 & Mục 4.2 bước 9 viết *"mean RGB channel correlation"*.
- **Các phương án đề xuất:**
  1. *Phương án A:* Chia MSE cho $H \times W$ $\rightarrow$ sai lệch gấp 3 lần chuẩn `immse` của MATLAB và lệch hoàn toàn Bảng 2.
  2. *Phương án B (Tối ưu):*
     - Tính `MSE` bằng trung bình cộng bình phương sai số trên **toàn bộ phần tử mảng $H \times W \times C$** (`np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2)`).
     - Cài đặt `cross_correlation(img_a, img_b)` hỗ trợ cả ảnh 2D (tương quan phẳng Pearson) và ảnh 3D RGB (trung bình cộng tương quan Pearson của từng cặp kênh R, G, B), đồng thời cung cấp thêm `adjacent_pixel_correlation(img)` (ngang/dọc/chéo) cho phân tích mở rộng.
- **Quyết định chọn:** **Phương án B.**
- **Tại sao chọn:** Tương đương chính xác 100% với hàm `immse(A, B)` của MATLAB R2024a và bao phủ trọn vẹn cả hai cách diễn đạt về hệ số tương quan trong bài báo.

---

### BM-10: Quy ước vẽ Histogram ảnh màu RGB (Hình 4c & Hình 5) và Phạm vi đo `EncTime`

- **Điểm mù & Bằng chứng từ bài báo:**
  - **Về Histogram:** Ở Hình 4c, ảnh cover chỉ có `65,536` pixel nhưng đỉnh histogram cao trên `6,300` (tổng diện tích các cột bằng `196,608 = 256×256×3`) và hiển thị 1 khối màu duy nhất $\Rightarrow$ tác giả đã gộp phẳng cả 3 kênh `img(:)` để vẽ 1 histogram 256-bin chung.
  - **Về `EncTime`:** Bảng 2 ghi Chaotic đạt `3.62e-5 s` (`36.2 µs`). Trên thực tế, nếu mỗi lần gọi đều sinh lại từ đầu 73,800 phần tử Logistic Map + 73,800 số ngẫu nhiên PRNG thì ngay cả mã C/JIT cũng tốn `~100–250 µs`; con số `36 µs` cho thấy nhiều khả năng tác giả đã tạo sẵn mặt nạ ngoài vòng lặp rồi chỉ bấm giờ phép XOR, hoặc đo trên payload nhỏ hơn (`156×156`).
- **Các phương án đề xuất:**
  1. *Phương án A:* Vẽ 3 đường histogram R/G/B riêng và luôn cache cứng mặt nạ Chaotic ngầm bên trong `encrypt()` $\rightarrow$ hình vẽ khác giao diện bài báo và việc cache ngầm không công bằng với AES/3DES.
  2. *Phương án B (Tối ưu):*
     - Trong `run_single.py`, vẽ Histogram cho Cover và Stego bằng cách **trải phẳng gộp 3 kênh `img_rgb.ravel()` trên 256 bins (`bins=256, range=(0, 256)`)** giống hệt `histogram(img(:), 0:256)` của MATLAB.
     - Trong `ChaoticCipher.__init__(self, x0, r, ecc_seed, *, cache_mask: bool = False)`: **mặc định `cache_mask=False`** (tính động cả `chaos_mask` bằng Numba JIT và `ecc_mask` ở mỗi lần gọi sau khi đã `warmup()` để công bằng mật mã học), nhưng cho phép bật `cache_mask=True` như một chế độ thực nghiệm tường minh khi muốn so sánh tốc độ XOR thuần với con số `3.62e-5 s` của bài báo.
- **Quyết định chọn:** **Phương án B.**
- **Tại sao chọn:** Tái tạo biểu đồ Histogram khớp trực quan 100% với Hình 4–5 của bài báo gốc, đồng thời giữ sự trung thực học thuật trong phép đo thời gian thực thi (có số liệu cho cả chế độ tính động lẫn chế độ keystream tính sẵn).
