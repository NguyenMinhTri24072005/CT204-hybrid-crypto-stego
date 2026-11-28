# Dàn ý slide báo cáo đồ án CT204 – An toàn và Bảo mật thông tin

**Đề tài:** Khung lai mật mã – giấu tin cho truyền ảnh an toàn (3DES, AES, Chaotic kết hợp giấu tin đa bit LSB)  
**Người báo cáo:** Nguyễn Minh Trí – MSSV B2308398 · **GVHD:** ThS. Phan Bích Chung · **Người nghe:** giảng viên chấm · **Demo trực tiếp:** có  
**Quy mô dàn ý:** 35 slide, tổng thời gian nói 15'00" (đã gồm demo 2'30")  

**Nguồn chính (chỉ đọc, không sửa):**  
- Báo cáo LaTeX: `E:\COMPUTER SCIENCE\NAM4_HK1_(2026-2027)\CT204_Information Security\Project\Reports\My_reports\Latex\main.tex` (ghép `chapters/chuong1–4.tex`, `chuong3_ketqua.tex`; PDF 66 trang đối chiếu số trang/bảng/hình)  
- Mã nguồn: `E:\COMPUTER SCIENCE\NAM4_HK1_(2026-2027)\CT204_Information Security\Project\SOURCES`  
- Template: `Slide\03_TEMPLATE\CTU_PowerPoint_Template.pptx` (13,33 × 7,5 in; font nhúng K2D cho tiêu đề, Readex Pro cho nội dung)  

Quy ước nguồn: 'tr.' là số trang in trong báo cáo; Bảng/Hình đánh số theo danh mục trong báo cáo (vd Bảng 3.8 = chương 3, bảng thứ 8).

---

## 0. Giả định cần bạn xác nhận (đọc trước)

1. **Thời lượng và số slide:** yêu cầu để trống ('[vd 15 phút]', '[vd 30–35]'), nên tôi lấy **15 phút** và **35 slide** (cận trên của 30–35). Trung bình ≈ 26 giây/slide nếu tính cả 2'30" demo, tức khá dày. Có bản rút gọn 28 slide ở mục 4. Nếu thời lượng thật khác, nói tôi số phút, tôi chỉnh lại số slide và giây nói.
2. **Slide 5 'Mô hình đe dọa':** báo cáo không có mục mô hình đe dọa riêng. Slide này tôi tổng hợp từ các mục 2.1, 1.4.4, 3.8.3–3.8.5. Nếu thầy cô/bạn không muốn, có thể bỏ và nói miệng ở slide 2.
3. **Entropy 7.05 của bài báo (slide 23, 26):** báo cáo mục 3.7.4 viết 'chứng tỏ' bài báo đo trên ảnh stego, còn mục 3.7.7 chỉ viết 'có thể'. Trên slide tôi dùng 'gợi ý / nhiều khả năng', không khẳng định. Bạn xác nhận cách diễn đạt.
4. **Demo (slide 32):** tôi đề xuất chạy `CT204_CryptoStego.exe` đã build sẵn (hoặc `python app.py`). Tôi chưa chạy thử ứng dụng trong phiên này. Slide có 4 ảnh crop làm phương án dự phòng.
5. **Tài liệu tham khảo:** dàn ý không có slide riêng; sẽ ghi nguồn nhỏ ở chân slide cần thiết (bài báo gốc, Westfeld–Pfitzmann). Muốn thêm 1 slide Tài liệu tham khảo thì báo tôi (thành 36 slide).

---

## 1. Cần kiểm tra

### 1.1 Số liệu (đã tính lại từ số liệu gốc)

| # | Mức | Vấn đề | Tôi sẽ dùng trên slide |
|---|---|---|---|
| K1 | Nhẹ | Mục 3.7.3 viết 'bản mã 24336–24352 byte … chiếm 99.09%'. Con số 99.09% chỉ đúng với **Chaotic** (24 336 B, không đệm). Với 3DES (24 344 B) tỷ lệ lấp là 99.12% và AES (24 352 B) là 99.15%. MSE lý thuyết tương ứng 0.49561 và 0.49577, khớp thực nghiệm (0.495602 và 0.495773) sát hơn. Hàng 'Lý thuyết (tải 99.09%)' ở Bảng 3.7 vì vậy là giá trị của Chaotic. | Ghi 'tỷ lệ lấp ≈ 99.1%' và 'MSE kỳ vọng ≈ 0.4954–0.4958'. Không sửa báo cáo. |
| K2 | Trung bình | Giải thích entropy 7.05 của bài báo: mục 3.7.4 nói 'chứng tỏ' đo trên ảnh stego; mục 3.7.7 nói 'có thể đến từ cách tính' (vd chuyển ảnh xám). Entropy stego tái hiện là 7.47, không phải 7.05, nên chưa chứng minh được. | Dùng 'gợi ý', không dùng 'chứng tỏ'. |
| K3 | Nhẹ | SSIM tái hiện 0.99686 thấp hơn bài báo 0.99850 (chênh 0.0016). Báo cáo thừa nhận chưa xác định nguyên nhân. | Ghi 'chưa giải thích được'. |
| K4 | Trung bình | Bảng 3.10 trộn hai điều kiện: Chaotic 31.3 µs là trung bình 8000 ảnh 156×156 **có cache mặt nạ**; 834.5 µs là ảnh 246×300 **không cache**. 3DES/AES có cả hai cột. Dễ bị đọc nhầm là 'Chaotic nhanh hơn AES' hay 'chậm hơn AES'. | Ghi rõ điều kiện đo ngay trên slide 25; không so chéo hai cột. |
| K5 | Nhẹ | Mục 3.8.1 viết 'UACI xấp xỉ 33.4%', trong khi Chaotic (x₀, r) là 32.71% và 32.77%. | Dùng số trong bảng. |
| K6 | Trung bình | Phạm vi mẫu nhỏ hơn cảm giác: χ² (99.84%/4.58%) chỉ chạy với **AES**; độ nhạy khóa, vi sai, tamper, KPA chạy trên **một** ảnh bí mật 156×156, một khóa, một vị trí, không có độ lệch chuẩn. Bản mã mỗi thuật toán là **một** bản duy nhất trên cả 8000 lượt (khóa cố định) nên NPCR/UACI/entropy bản mã không phản ánh thuật toán nào 'tốt hơn' (báo cáo đã nói ở mục 3.7.4). | Ghi 'trên 1 ảnh mẫu' / 'với AES' ở chân slide 23, 27–31; không dùng chữ 'luôn'. |

### 1.2 Báo cáo ↔ mã nguồn

**Khớp (đã đối chiếu, không thấy chỗ lệch):** x₀ = 0.785398, r = 3.999, ecc_seed = 42, key_seed = 2025 (`configs/default.yaml`) · 3DES khóa 24 B/IV 8 B, AES khóa 16 B/IV 16 B, CBC, PKCS#7 · SHA-256 phân tách miền (`crypto/base.py` dòng 45–55) · thử nhãn kế khi khóa 3DES suy biến (`des3_cipher.py`) · Chaotic bắt đầu từ x₁, lượng tử hóa ⌊256·x⌋ (`chaotic_cipher.py` dòng 20–32) · header `>4sBBHHIH` 16 B, CRC-16 = CRC-32 của 14 B đầu & 0xFFFF, header ở 128 giá trị kênh đầu 1-LSB, magic `HCST` (`stego/lsb.py`) · nội suy cubic, max_lsb = 3 · MSE chia H×W×3, SSIM Gauss 11×11 σ = 1.5 (`metrics/visual.py`) · hai nhóm độ đo *_enc/*_stego (`metrics/security.py`) · mật khẩu giao diện `ct204-ui:{thuật toán}:{mật khẩu}` (`ui/controller.py` dòng 98) · 4 kịch bản tamper + 'sai khóa' riêng = 5 kịch bản · số liệu bảng 3.6–3.8, 3.10 khớp `single_metrics.csv`, `benchmark_summary_table2.csv`, `summary.json`; bảng 3.12–3.14 và χ² khớp `experiments.json`.

**Chưa đối chiếu được:** số ca pytest 347 (tổng bảng 126+71+38+40+72 = 347 đúng, nhưng tôi chưa chạy lại pytest) · phiên bản thư viện Bảng 3.1 (`requirements.txt` chỉ ghi khoảng; riêng NumPy 2.2.6 khớp `dist/…/numpy-2.2.6.dist-info`) · `results/benchmark_results.csv` (7 MB) chỉ dùng bản tổng hợp, chưa đọc từng dòng · các tab giao diện (`ui/tabs/*`), `tests/`, notebook, `scripts/run_*.py` chưa đọc kỹ · phụ lục A, `references.bib`, lời cảm ơn chưa đọc kỹ.

### 1.3 Hình và trình bày

- **Ảnh chụp giao diện** (`figures/ui/*.png`, 1600×900, toàn cửa sổ): chữ trong ảnh nhỏ (≈ 9–10 pt), thu về slide sẽ khó đọc. `tab4_benchmark.png` (đã mở xem) **bị cắt biểu đồ ở phía dưới** và hiện đường dẫn `E:\COMPUTER SCIENCE\…`. 4 ảnh còn lại cùng kích thước nên có thể cùng vấn đề (chưa mở xem từng ảnh). Slide 32 chỉ dùng ảnh crop và demo trực tiếp.
- **Biểu đồ matplotlib** (1,1–1,6 nghìn px): đã mở xem `kpa_attack.png` và `chi2_steganalysis.png`, đủ nét. Giữ làm ảnh ở slide 8, 29, 31. Các biểu đồ cột sẽ dựng lại thành chart gốc từ số trong bảng.
- **Biểu đồ χ² (Hình 3.22)** là histogram 40 cột log; `experiments.json` chỉ lưu tổng hợp (99.84%, 4.58%, trung vị p), không lưu p từng ảnh, nên không dựng lại thành chart gốc được. Slide 31 dùng ảnh gốc kèm chart 2 giá trị.
- **Ảnh trong `figures/paper/*.jpeg`** (3–8 KB, rất mờ) không được dùng trong báo cáo (chỉ nằm trong graphicspath) → không đưa lên slide.
- Template nhúng font K2D và Readex Pro. Khi render kiểm tra bằng LibreOffice sẽ dùng font thay thế nên tôi để dư chỗ ≈ 10%. PowerPoint trên máy bạn sẽ hiển thị đúng font nhúng.

---

## 2. Quy ước đối tượng và trình bày

- **Chart gốc PowerPoint (chỉnh được, có Excel nhúng):** slide 18, 22, 25, 28, 31. Thang log ở slide 25. Không có thanh sai số/đường xu hướng.
- **Bảng gốc:** slide 3, 7, 9, 14, 21, 23, 24, 26, 27, 30, 33 (tắt banding, header tô tay).
- **Sơ đồ vẽ lại bằng hình khối + mũi tên:** slide 2, 5, 6, 10, 11, 12, 13, 15 (kèm ô bit ở slide 9).
- **Ảnh:** slide 8, 19, 20, 29, 31, 32 (crop đúng tỉ lệ trước khi chèn).
- **Code:** slide 16, 17 (≤ 10 dòng, monospace, ghi file + dòng).
- **Chữ:** nội dung ≥ 18 pt, bảng 16–19 pt, chú thích ≥ 11–12 pt; tối đa ≈ 6 dòng/slide; công thức và ký hiệu dùng chỉ số trên/dưới thật (x₀, Cᵢ, 10⁻¹⁰, V_s…). Thuật ngữ tiếng Anh giữ nguyên (encryption, header, CBC, steganalysis…). Tiêu đề ≤ 2 dòng.
- **Ghi chú người nói:** mọi slide (2–3 câu văn nói, đọc số đúng).
- Cột 'Nội dung chính' dưới đây là **bản nháp** để duyệt ý; chữ trên slide sẽ ngắn hơn và đưa số liệu vào bảng/biểu đồ.

---

## 3. Dàn ý từng slide

### Phần 1 — Mở đầu: bài toán, bài báo, mục tiêu  (1'40")

| # | Tiêu đề slide | Nội dung chính | Nguồn | Layout / đối tượng | Nói |
|---|---|---|---|---|---|
| 1 | Bìa | Khung lai mật mã – giấu tin cho truyền ảnh an toàn · (3DES, AES, Chaotic kết hợp giấu tin đa bit LSB) · CT204 – An toàn và Bảo mật thông tin · SV: Nguyễn Minh Trí, MSSV B2308398 · GVHD: ThS. Phan Bích Chung · Cần Thơ, 11/2026 | thongtin.tex; frontmatter/biachinh.tex | Title Slide (nền xanh, có logo) | 10 s |
| 2 | Truyền ảnh qua kênh không tin cậy | 3 thẻ: Chỉ mã hóa (bản mã như nhiễu, dễ gây chú ý) · Chỉ giấu tin (lộ nội dung khi bị phát hiện) · Khung lai hai lớp (mã hóa trước, nhúng sau). Dòng đầu: ảnh có thể bị nghe lén, chặn bắt, sửa đổi (MITM) | Mục 2.1 (tr.6); mục 1.5 (tr.5) | Title Only + 3 thẻ bo góc (hình khối) | 25 s |
| 3 | Mật mã và giấu tin bổ sung cho nhau | Bảng 3 hàng × 2 cột (Mật mã / Giấu tin): mục tiêu (che nội dung / che sự tồn tại) · khi bị phát hiện (nội dung vẫn an toàn nếu khóa an toàn / lộ nếu không mã hóa) · điểm yếu (thu hút chú ý / không tự bảo vệ nội dung) | Bảng 1.1 (tr.5), rút gọn | Title Only + bảng gốc | 20 s |
| 4 | Bài báo gốc và mục tiêu đề tài | Trái: Raut, Ugale, Chandwadkar – ICITSC 2025 (SCITEPRESS 2026, tr.175–182); cài đặt MATLAB R2024a; Linnaeus 5: 8000 ảnh 256×256, 5 lớp. Phải – 4 mục tiêu: tái hiện 3 lớp mã hóa + LSB đa bit (khôi phục chính xác từng bit) · làm rõ 10 điểm mù · đối chiếu Hình 4–5, Bảng 2 · đánh giá an toàn mở rộng · ứng dụng desktop | Bảng 2.1 (tr.6); mục 3.1 (tr.17) | Comparison (2 cột chữ) | 25 s |
| 5 | Mô hình đe dọa của hệ thống | 4 thẻ (kẻ tấn công → cách kiểm chứng): nghe lén kênh công khai (bản mã là nhiễu) · phân tích giấu tin χ² (slide 31) · biết bản rõ – KPA (slide 29) · chỉnh sửa ảnh stego: JPEG, nhiễu, đảo bit (slide 30). Mục tiêu bảo vệ: bí mật, vô hình, toàn vẹn | Tổng hợp từ mục 2.1, 1.4.4, 3.8.3–3.8.5 (báo cáo không có mục 'mô hình đe dọa' riêng) — CẦN XÁC NHẬN | Title Only + 4 thẻ | 20 s |

### Phần 2 — Cơ sở lý thuyết  (2'00")

| # | Tiêu đề slide | Nội dung chính | Nguồn | Layout / đối tượng | Nói |
|---|---|---|---|---|---|
| 6 | Kiến trúc khung lai hai lớp | Sơ đồ khối vẽ lại: Ảnh bí mật (xám) → Mã hóa 3DES/AES/Chaotic [khóa K] → Giấu tin LSB 1–3 bit ← Ảnh phủ RGB 256×256 → ảnh stego → kênh công khai → Trích xuất + giải mã [khóa K] → Ảnh khôi phục | Hình 2.5 (tr.13), vẽ lại | Title Only + hình khối/mũi tên | 20 s |
| 7 | Ba lớp mã hóa được so sánh | Bảng 3 cột: 3DES-CBC (EDE, khối 64 bit, khóa 24 B + IV 8 B, đệm bội 8 B) · AES-128-CBC (khối 128 bit, khóa 16 B + IV 16 B, đệm bội 16 B) · Chaotic + PRNG (mã dòng, x₀ = 0.785398, r = 3.999, không đệm). Dòng công thức CBC: Cᵢ = E_K(Pᵢ ⊕ Cᵢ₋₁) | Bảng 2.2 (tr.14); mục 2.2.1.c (tr.8) | Title Only + bảng gốc + 1 dòng công thức (chỉ số dưới) | 25 s |
| 8 | Chaotic + PRNG masking | x_{n+1} = r·x_n·(1 − x_n), x₀ = 0.785398, r = 3.999 · chaosMask[n] = min(⌊256·x_{n+1}⌋, 255) · encBytes = S ⊕ chaosMask ⊕ eccMask · 'ECC' chỉ là PRNG seed cố định, không có phép toán đường cong elliptic. Dưới: Hình 2.3 (giản đồ rẽ nhánh + độ nhạy điều kiện đầu) | Mục 2.2.1.d–e (tr.9); Hình 2.3 (tr.9); Hình 2.6 (tr.14); code crypto/chaotic_cipher.py dòng 20–38 | Title Only + công thức (chỉ số) + ảnh logistic_map.png (1562×505) | 25 s |
| 9 | Giấu tin k-LSB và độ méo kỳ vọng | s = c − (c mod 2ᵏ) + m, ∣s − c∣ ≤ 2ᵏ − 1 · E[(s − c)²] = (L² − 1)/6, L = 2ᵏ → MSE 0.5 / 2.5 / 10.5 cho k = 1 / 2 / 3 · MSE 0.5 ⇒ PSNR ≈ 51.14 dB. Ví dụ bit: c = 154 → 155 (1-LSB), 157 (3-LSB) | Mục 2.2.1.f (tr.10); Hình 2.4 (tr.10) vẽ lại | Title Only + ô bit (hình khối) + bảng 3 hàng k / MSE kỳ vọng | 30 s |
| 10 | Bộ độ đo đánh giá | 3 thẻ: Chất lượng ảnh stego – MSE (chia H×W×3), PSNR, SSIM (cửa sổ Gauss 11×11, σ = 1.5) · An toàn bản mã – NPCR, UACI, entropy, tương quan; hai nhóm *_enc và *_stego · Tốc độ và phát hiện – EncTime, χ² cặp giá trị. Công thức PSNR = 10·log₁₀(255²/MSE) | Mục 2.2.2 (tr.10–12); BM-08, BM-09 (tr.20–21); code metrics/visual.py, metrics/security.py | Title Only + 3 thẻ | 20 s |

### Phần 3 — Thiết kế và hiện thực  (2'40")

| # | Tiêu đề slide | Nội dung chính | Nguồn | Layout / đối tượng | Nói |
|---|---|---|---|---|---|
| 11 | Kiến trúc phân lớp của hệ thống | Sơ đồ 4 tầng vẽ lại: Trình diễn (app.py GUI 4 tab, ui/controller.py, run_single.py, run_benchmark.py) → pipeline.py (hide / reveal / run_pipeline) → Lõi: crypto/ (BaseCipher – Strategy: DES3, AES, Chaotic) · stego/lsb.py · metrics/ → config.py + default.yaml (mọi tham số) | Hình 3.1 (tr.19); code src/crypto/__init__.py (create_cipher), configs/default.yaml | Title Only + hình khối/mũi tên | 20 s |
| 12 | Luồng xử lý gửi – nhận | Sơ đồ vẽ lại: Ảnh bí mật → tobytes → cipher.encrypt (đo EncTime) → header 16 B + bản mã → lsb.embed (k-LSB) ← ảnh phủ → ảnh stego (.png) → lsb.extract (đọc header) → cipher.decrypt (gỡ đệm) → reshape → ảnh khôi phục (MSE = 0). Nhấn mạnh: phía nhận chỉ cần ảnh stego và khóa | Hình 3.2 (tr.19); code src/pipeline.py (hide, reveal, run_pipeline) | Title Only + hình khối/mũi tên | 20 s |
| 13 | Mười điểm mù của bài báo | 3 thẻ nổi bật: BM-01 (kích thước ảnh bí mật: 1-LSB hay 3-LSB?) · BM-06 (bên nhận biết k, kích thước, độ dài bằng cách nào?) · BM-08 (đo trên bản mã hay ảnh stego?). Chân slide: 7 điểm còn lại (thứ tự trải phẳng, khóa/IV, lượng tử hóa Logistic, chuẩn đệm, phóng to ảnh phủ, mẫu số MSE/SSIM, histogram/EncTime) ở Bảng 3.2 | Bảng 3.2 (tr.20); BM-01, 06, 08 (tr.21) | Title Only + 3 thẻ — slide lướt | 15 s |
| 14 | BM-01: một nghịch lý, hai kịch bản | Bảng 3 cột (Kịch bản A / B): mục đích (Hình 4–5 / Bảng 2) · ảnh bí mật (246×300 = 73 800 B / 156×156 = 24 336 B) · LSB (3-LSB, cover phóng 257×257 / 1-LSB) · số lượt (3 / 24 000). Lý do: bản mã AES 73 808 B > dung lượng 3-LSB 73 680 B ⇒ phải 3-LSB ⇒ MSE ≈ 10.5; Bảng 2 báo ≈ 0.5 (đặc trưng 1-LSB) | Bảng 3.5 (tr.31); BM-01 (tr.21) | Title Only + bảng gốc | 25 s |
| 15 | Header 16 byte: trích xuất mù | Sơ đồ byte vẽ lại: magic 'HCST' (4 B) · ver (1) · k (1) · H_s (2) · W_s (2) · ciphertext_len (4) · CRC-16 (2). Thanh dưới: header 1-LSB (128 giá trị kênh đầu) · bản mã k-LSB · phần còn lại không đổi. Kiểm tra theo thứ tự magic → CRC → version → k → kích thước → dung lượng; sai thì dừng, không giải mã ra rác | Hình 3.3 (tr.24); mục 3.4.4 (tr.23); code stego/lsb.py dòng 30 (HEADER_STRUCT), 56 (pack_header), 195 (extract) | Title Only + hình khối | 25 s |
| 16 | Sinh khóa tất định và mã hóa CBC | Đoạn code (4 dòng): derive_bytes – SHA-256(seed:nhãn) → PCG64 · Ý chính: mỗi vai trò một nhãn ('aes:key', 'aes:iv', '3des:key:0'…) · khóa 3DES suy biến (K₁ = K₂ hoặc K₂ = K₃) thì thử nhãn kế · đối tượng CBC tạo mới mỗi lần gọi · Lưu ý: chỉ để tái lập thực nghiệm, không phải quản lý khóa an toàn | Mục 3.4.1–3.4.2 (tr.22); code crypto/base.py dòng 45, 53–55; crypto/des3_cipher.py | Title Only + khung code (monospace) + 3 gạch đầu dòng | 20 s |
| 17 | Nhúng LSB vectơ hóa | Đoạn code _write_lsb (9 dòng) · k nhỏ nhất ∈ {1, 2, 3} thỏa 8·len ≤ (M − 128)·k; không đủ thì phóng to ảnh phủ bicubic, s = √((⌈8·len/3⌉ + 128)/(3HW)) · không có vòng lặp Python trên điểm ảnh · ví dụ coins 246×300 → ảnh phủ 257×257 | Mục 3.4.5 (tr.24); code stego/lsb.py dòng 93–101 (_write_lsb), 117–138 | Title Only + khung code + 3 gạch đầu dòng | 20 s |
| 18 | Công nghệ và kiểm thử | Trái: Python 3.12.8 · PyCryptodome 3.24.1 · NumPy 2.2.6 · Numba 0.68.1 · OpenCV · scikit-image · Tkinter · mọi tham số trong default.yaml. Phải: biểu đồ cột ngang số ca pytest (crypto 126, lsb 71, metrics 38, pipeline 40, ui_controller 72) = 347, tất cả đạt | Bảng 3.1 (tr.18); Bảng 3.3 (tr.29) | Title Only + CHART gốc (cột ngang) + 1 khối chữ | 15 s |

### Phần 4 — Thử nghiệm và đánh giá  (5'00")

| # | Tiêu đề slide | Nội dung chính | Nguồn | Layout / đối tượng | Nói |
|---|---|---|---|---|---|
| 19 | Thiết lập thực nghiệm | Linnaeus 5: 8000 ảnh, 5 lớp (berry, bird, dog, flower, other), 256×256 · 24 000 lượt (8000 × 3 thuật toán) · Intel Core i3-1005G1 (2 nhân/4 luồng, AES-NI), 20 GB RAM, Windows 11 IoT Enterprise LTSC 2024 · ảnh minh họa linnaeus5_samples.png | Mục 3.7.1 (tr.30); Bảng 3.4; Hình 3.8 (tr.30) | Title Only + ảnh (1278×919) + 3 dòng — slide lướt | 15 s |
| 20 | Kịch bản A: bản mã như nhiễu, khôi phục chính xác | Ảnh fig5_comparison_grid.png (2160×1710). 3 chỉ số: cả 3 thuật toán khôi phục MSE = 0 · 3-LSB: MSE ≈ 10.43, PSNR ≈ 37.94 dB (khớp lý thuyết 10.5 × 99.3%) · entropy bản mã ≈ 7.9976 (histogram phẳng) | Bảng 3.6 (tr.33); Hình 3.10 (tr.33); results/single/single_metrics.csv | Title Only + ảnh + 3 thẻ số | 25 s |
| 21 | Chất lượng ảnh stego trên 8000 ảnh | Bảng: MSE / PSNR / SSIM của bài báo (BB) và tái hiện (TH) cho 3 thuật toán + hàng lý thuyết. Ví dụ AES: MSE 0.50001 vs 0.49577 · PSNR 51.1537 vs 51.1780 dB. Kết luận: lệch < 1% (PSNR ≈ 0.03 dB), do tỷ lệ lấp đầy ≈ 99.1% so với ≈ 100% của bài báo; SSIM TH thấp hơn 0.0016, chưa rõ nguyên nhân | Bảng 3.7 (tr.35); mục 3.7.3; results/benchmark_summary_table2.csv | Title Only + bảng gốc (7 cột) | 30 s |
| 22 | SSIM và entropy theo lớp ảnh phủ | 2 biểu đồ cột (AES): SSIM theo lớp (dog 0.99721, berry 0.99709, other 0.99684, bird 0.99664, flower 0.99653) · entropy stego (dog 7.54, flower 7.516, berry 7.511, other 7.401, bird 7.365). Lớp nhiều kết cấu che giấu tốt hơn nền phẳng (che lấp thị giác) | Hình 3.18 (tr.40); Latex/tools/out/summary.json | Title Only + 2 CHART gốc (cột) — slide lướt | 10 s |
| 23 | Độ an toàn thống kê của bản mã | Bảng (3DES / AES / Chaotic / BB-AES): NPCR_enc 99.65 / 99.58 / 99.56 / 99.62 · UACI_enc 30.33 / 30.35 / 30.51 / 30.82 · tương quan 0.0062 / −0.0015 / −0.0134 / −0.0041 · entropy bản mã 7.993 / 7.992 / 7.993 / – · entropy stego 7.466 / 7.466 / 7.466 / 7.048. Ý: NPCR ≈ 255/256 = 99.609%; UACI kỳ vọng với ảnh bí mật này là 30.41% (ngưỡng 33.46% chỉ cho 2 ảnh ngẫu nhiên); entropy 7.05 của BB gần entropy ảnh stego hơn bản mã (gợi ý đo trên ảnh stego) | Bảng 3.8 (tr.36); mục 3.7.4; results/benchmark_summary_table2.csv | Title Only + bảng gốc + 2 dòng kết luận | 30 s |
| 24 | Tương quan điểm ảnh kề và χ² tính đều | Bảng 4 hàng (ảnh bí mật, 3DES, AES, Chaotic) × (ngang, dọc, chéo, entropy, χ²): ảnh bí mật 0.926 / 0.941 / 0.887, χ² = 15 143.5 (không đều); bản mã ∣r∣ ≤ 0.012, entropy ≈ 7.99, χ² = 241.2 / 272.3 / 231.9 < 293.25 (đều) | Bảng 3.9 (tr.38); Latex/tools/out/experiments.json (cipher_statistics) | Title Only + bảng gốc — slide lướt | 10 s |
| 25 | Tốc độ mã hóa | Biểu đồ cột (thang log, µs) BB vs TH: 3DES 3552 / 1303.1 · AES 601 / 111.1 · Chaotic 36.2 / 31.3. Ý: thứ tự Chaotic < AES < 3DES được tái hiện; 3DES trên 246×300 = 3587.7 µs ≈ 3552 µs của BB (BB đo ảnh đầy đủ); Chaotic 36.2 µs chỉ khi cache mặt nạ — không cache, 246×300: 834.5 µs, chậm hơn AES (285.1 µs) | Bảng 3.10 (tr.38); Hình 3.16 (tr.39); summary.json (trung vị, P95) | Title Only + CHART gốc (cột nhóm, trục log) + 2 dòng | 30 s |
| 26 | Đối chiếu tổng hợp với Bảng 2 của bài báo | Bảng 6 hàng (độ đo → mức khớp): MSE, PSNR – rất sát · NPCR, tương quan – rất sát (≈ 0) · SSIM – sát (−0.0016, chưa rõ nguyên nhân) · UACI – sát (30.3–30.5 vs 30.8–31.0; giải thích bằng phân bố mức xám) · EncTime – đúng thứ tự (AES nhanh hơn 5.4× nhờ AES-NI) · entropy stego – khác (7.47 vs 7.05; cần cách đo của BB) | Bảng 3.11 (tr.41) | Title Only + bảng gốc | 25 s |
| 27 | Độ nhạy khóa | Bảng: 3DES đảo 1 bit K₁: NPCR 99.626 / UACI 33.385 / PSNR giải mã sai 8.61 dB · AES đảo 1 bit: 99.552 / 33.466 / 8.63 · Chaotic x₀ + 10⁻¹⁰: 99.310 / 32.708 / 8.72 · r + 10⁻¹⁰: 99.240 / 32.771 / 8.71 · ecc_seed 42 → 43: 99.643 / 33.390 / 8.72. Cả 3 đạt; Chaotic thấp hơn chút vì quỹ đạo Logistic chỉ tách sau ≈ 30 bước | Bảng 3.12 (tr.42); experiments.json (key_sensitivity) | Title Only + bảng gốc — slide lướt | 10 s |
| 28 | Phân tích vi sai đúng định nghĩa | Biểu đồ cột nhóm: NPCR (%) khi đổi 1 điểm ảnh ở đầu / giữa / cuối ảnh: 3DES 99.626 / 49.511 / 0.033 · AES 99.667 / 49.466 / 0.066 · Chaotic 0.0041 ở cả 3 vị trí. Ý: CBC chỉ khuếch tán về phía sau; Chaotic không khuếch tán (đổi 1 điểm ảnh chỉ đổi 1 byte bản mã); NPCR ≈ 99.6% trong BB không chứng minh chống vi sai | Bảng 3.13 (tr.42); experiments.json (plaintext_sensitivity) | Title Only + CHART gốc (cột nhóm, nhãn số) + 2 dòng | 30 s |
| 29 | Tấn công biết bản rõ lên Chaotic | Ảnh kpa_attack.png (1518×788). Ý: C_A ⊕ C_B = A ⊕ B lộ đường nét (tương quan 1.0) · khóa dòng = A ⊕ C_A ⇒ giải mã B chính xác 100% mà không cần x₀, r, seed · cùng phép tấn công với AES-CBC chỉ ra nhiễu (PSNR 7.84 dB, tương quan 0.005) | Mục 3.8.3 (tr.43); Hình 3.19 (tr.43); experiments.json (known_plaintext) | Title Only + ảnh + 3 dòng | 30 s |
| 30 | Chống chỉnh sửa ảnh stego | Bảng (kịch bản → 3DES/AES → Chaotic): sai khóa → phát hiện (lỗi đệm PKCS#7) → không phát hiện (ảnh nhiễu) · JPEG Q = 95, nhiễu Gauss σ = 2 → phát hiện ở header (sai magic) · đảo 1 bit header → CRC-16 · đảo 1% bit payload → CBC: BER 24.1% / 35.9%, phát hiện nhờ lỗi đệm; Chaotic: BER 1.0%, PSNR 24.9 dB, không phát hiện. Ý: LSB thay thế mong manh; CRC chỉ chống lỗi ngẫu nhiên; payload không được bảo vệ toàn vẹn | Bảng 3.14 (tr.44); Hình 3.20 (tr.45); experiments.json (tamper) | Title Only + bảng gốc + 1 dòng | 25 s |
| 31 | Bị phát hiện bởi phân tích giấu tin χ² | Trái: biểu đồ cột 2 giá trị (ảnh stego bị phát hiện 99.84%; ảnh phủ báo nhầm 4.58%). Phải: ảnh chi2_steganalysis.png (1110×535). Ý: ngưỡng p > 0.95; AES, 156×156, 1-LSB lấp ≈ 99%; PSNR cao nhưng không 'vô hình' trước đối thủ biết kiểm định cặp giá trị (Westfeld–Pfitzmann) | Mục 3.8.5 (tr.46); Hình 3.22 (tr.47); experiments.json (steganalysis) | Title Only + CHART gốc + ảnh | 30 s |

### Phần 5 — Demo trực tiếp  (2'30")

| # | Tiêu đề slide | Nội dung chính | Nguồn | Layout / đối tượng | Nói |
|---|---|---|---|---|---|
| 32 | Demo ứng dụng desktop | Kịch bản ≈ 2'30": (1) Tab 1: ảnh phủ + coins 246×300, AES-128 → tự chọn 3-LSB, phóng 257×257, xem 4 ảnh + histogram (30 s) · (2) Tab 2: mở ảnh stego → header + CRC; thử 'sai khóa' (lỗi PKCS#7) và 'đảo 1 bit header' (CRC mismatch) (60 s) · (3) Tab 3: so sánh 3 thuật toán cùng cặp ảnh (30 s) · (4) Tab 4: dashboard 8000 ảnh (30 s). Slide: 4 ảnh crop theo tab làm nền cho demo/dự phòng | Mục 3.5 (tr.25–29); Hình 3.4–3.7; chạy SOURCES\dist\CT204_CryptoStego\CT204_CryptoStego.exe hoặc python app.py | Title Only + 4 ảnh crop (2×2) + nhãn bước | 150 s |

### Phần 6 — Hạn chế, kết luận  (1'10")

| # | Tiêu đề slide | Nội dung chính | Nguồn | Layout / đối tượng | Nói |
|---|---|---|---|---|---|
| 33 | Hạn chế đã kiểm chứng và hướng cải tiến | Bảng 5 hàng (hạn chế → khắc phục): Chaotic dùng lại dòng khóa, không khuếch tán → nonce + khóa bí mật / ChaCha20 · IV cố định → IV ngẫu nhiên lưu header · không xác thực bản mã → AES-GCM, header làm AAD · khóa từ seed/SHA-256 → Argon2/PBKDF2 · LSB thay thế bị χ² phát hiện, không bền → LSB matching, hoán vị theo khóa, giấu thích nghi, DCT/DWT. Chân slide: cải tiến mới ở mức phân tích, chưa cài đặt | Bảng 3.15 (tr.48); mục 4.2–4.3 (tr.50) | Title Only + bảng gốc | 30 s |
| 34 | Kết luận | 5 ý: tái hiện đầy đủ khung (3 thuật toán + LSB 1–3 bit), 24 000 lượt khôi phục chính xác 100%, 347 ca kiểm thử đạt · khớp Bảng 2: MSE 0.4956, PSNR 51.18 dB, NPCR ≈ 99.6% · giải thích số liệu bất thường (UACI 30.41%, entropy bản mã 7.99) · Chaotic bị KPA phá hoàn toàn, LSB bị χ² phát hiện 99.84% · AES-128 là phương án cân bằng nhất | Mục 4.1 (tr.49) | Title and Content with logo | 30 s |
| 35 | Cảm ơn | CÁM ƠN / Thank you · Xin cảm ơn thầy/cô đã lắng nghe — Hỏi đáp | Slide mẫu 'Title Blue Background' của template (giữ lại) | Title Blue Background | 10 s |

**Tổng: 35 slide · 15'00"** (khớp 15 phút). Phân bổ: Phần 1 = slide 1–5 (1'40"); Phần 2 = slide 6–10 (2'00"); Phần 3 = slide 11–18 (2'40"); Phần 4 = slide 19–31 (5'00"); Phần 5 = slide 32–32 (2'30"); Phần 6 = slide 33–35 (1'10").

---

## 4. Gợi ý rút gọn

**Bản 28 slide** (bỏ slide 3, 10, 13, 18, 22, 24, 27; tiết kiệm 1'40", còn 13'20"): slide 3 gộp vào lời nói ở slide 2; slide 10 (bộ độ đo) nói miệng khi vào slide 21; slide 13 gộp vào 14; slide 18 (công nghệ/kiểm thử) chuyển 1 câu sang slide 34; slide 22, 24, 27 là các slide 'lướt' (≤ 10 s), có thể bỏ hoặc để dự phòng cho phần hỏi đáp.

**Slide 'lướt' (≤ 15 s) đã đánh dấu:** 13, 18, 19, 22, 24, 27. Nếu bị cắt giờ, giữ nguyên các slide kết quả quan trọng nhất: 20, 21, 25, 28, 29, 31 và demo.

---

## 5. Bước tiếp theo

Dừng ở bước duyệt dàn ý. Chưa dựng slide. Khi bạn nói **'tiến hành'** (kèm chỉnh sửa nếu có), tôi dựng `.pptx` bằng python-pptx trên template, kiểm tra (validate, render từng slide, đối chiếu số liệu với bảng gốc) rồi lưu vào `04_SLIDE_HOAN_CHINH`.
