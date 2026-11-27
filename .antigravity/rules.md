# Antigravity Project Rules — Hybrid Crypto-Steganography Framework (CT204)

## 1. Project Context & Repository Layout
- **Objective:** Python 3.12 reproduction of *"A Hybrid Crypto-Steganography Framework for Secure Image Transfer"* (ICITSC 2025, originally MATLAB R2024a) for course CT204 Information Security.
- **Paper Specification:** `Docs/145987.md` (lightweight Markdown transcription of `Docs/145987.pdf`; figures in `Docs/145987_assets/`). Always read `Docs/145987.md` instead of parsing the PDF.
- **Planning, Technical Spec & ADRs:** `Plans/01_TECHNICAL_SPEC.md`, `Plans/02_EXECUTION_PLAN_AND_ROLES.md`, and `Plans/03_TECHNICAL_BLIND_SPOTS_AND_DECISIONS.md` (`BM-01` through `BM-10`, outside `SOURCES/`). Always consult and strictly follow the locked-in decisions in `Plans/` when implementing or reviewing phases.
- **Code Root:** `SOURCES/` (Git root is the parent directory `Project/`). All Python source code, configs, tests, scripts, and virtual environment live under `SOURCES/`.

## 2. Environment & Terminal Execution Rules (Windows)
- **Python Runtime:** Local Python 3.12 (`pyenv-win`, pinned in `SOURCES/.python-version` = `3.12.8`) with virtual environment at `SOURCES/.venv`.
- **Mandatory Executables:** NEVER invoke bare `python`, `pip`, or `pytest`. Always execute via the venv binaries from `SOURCES/`:
  - Python: `.\.venv\Scripts\python.exe`
  - Pytest: `.\.venv\Scripts\pytest.exe`
  - (If running from the repository root `Project/`, invoke `.\SOURCES\.venv\Scripts\python.exe` or change working directory to `SOURCES/` first.)
- **Imports:** Always use package-absolute imports rooted at `SOURCES/` (e.g., `from src.config import load_config`, `from src.crypto.base import BaseCipher`). Pytest resolves imports via `pythonpath = .` in `SOURCES/pytest.ini`.

## 3. Mandatory Architecture & Actual Config Schema (Post-Phase 1)

### 3.1 Configuration (`SOURCES/configs/default.yaml` & `SOURCES/src/config.py`)
- Single source of truth loaded via `src.config.load_config()`, which resolves `paths.*` (`data_dir`, `sample_dir`, `results_dir`) and `secret.path` to `pathlib.Path` objects relative to `SOURCES/`.
- **Exact Config Keys:**
  - `paths`: `data_dir` (`data/linnaeus5`), `sample_dir` (`data/sample`), `results_dir` (`results`).
  - `crypto`:
    - `key_seed`: `2025`
    - `des3`: `key_bytes: 24`, `iv_bytes: 8`
    - `aes`: `key_bytes: 16`, `iv_bytes: 16`
    - `chaotic`: `x0: 0.785398`, `r: 3.999`, `ecc_seed: 42`
  - `stego`: `cover_size: [256, 256]`, `max_lsb: 3`, `header_lsb: 1`, `scale_up_interpolation: cubic`.
  - `secret`: `path: data/sample/secret.png`, `resize: null`.
  - `benchmark`: `ciphers: [3des, aes, chaotic]`, `splits: [train, test]`, `csv_name: benchmark_results.csv`.
- **Rule:** Never hard-code hyperparameters, keys, seeds, or file paths inside `src/`.

### 3.2 Cryptography Layer (`SOURCES/src/crypto/`) — Strategy Pattern
- Define abstract `BaseCipher` in `src/crypto/base.py` with `encrypt(plaintext: bytes) -> bytes`, `decrypt(ciphertext: bytes) -> bytes`, `name` property, and optional `warmup()` hook.
- Pipeline and steganography modules must depend ONLY on `BaseCipher`.
- **3 Required Branches:**
  1. `des3_cipher.py` (`DES3Cipher`): 3DES-192 (EDE), CBC mode, 24-byte key, 8-byte IV, PKCS7 padding (8B block) via `pycryptodome`. Apply `DES3.adjust_key_parity` and guard against degenerate keys. Instantiate a fresh CBC cipher object per call.
  2. `aes_cipher.py` (`AESCipher`): AES-128, CBC mode, 16-byte key, 16-byte IV, PKCS7 padding (16B block) via `pycryptodome`. Instantiate a fresh CBC cipher object per call.
  3. `chaotic_cipher.py` (`ChaoticCipher`): Logistic Map $x_{n+1} = r \cdot x_n \cdot (1 - x_n)$ ($x_0 = 0.785398$, $r = 3.999$), `@numba.njit` accelerated, scaled deterministically to `uint8` (`clip(floor(x * 256), 0, 255)`), combined with simulated ECC mask (`np.random.default_rng(ecc_seed).integers(0, 256, size=n, dtype=np.uint8)`), stream XOR `S ^ chaos_mask ^ ecc_mask` (no block padding).
- **Key Management:** Keys and IVs are derived deterministically from `crypto.key_seed` (with domain separation between ciphers) and are NEVER stored in stego images.

### 3.3 Steganography Layer (`SOURCES/src/stego/lsb.py`)
- Embed ciphertext bits into **1–3 LSBs** of R, G, B channels of a `256×256` RGB cover using **fully vectorized NumPy bitwise operations** (no per-pixel Python loops).
- Prepend a fixed 16-byte (128-bit) metadata header in the first 128 channel values at `header_lsb = 1` containing magic bytes, `num_lsb`, secret `(H, W)`, `ciphertext_len`, and checksum; embed payload from channel index 128 onward at `num_lsb ∈ {1, 2, 3}`.
- If payload exceeds `max_lsb = 3` capacity, automatically scale up cover image (`cv2.INTER_CUBIC`).
- **Lossless Output Only:** Stego images MUST be saved in `.png` format.

### 3.4 Metrics, Pipeline & Scripts
- `visual.py`: MSE, PSNR, SSIM (`scikit-image`, `channel_axis=-1` for RGB) for Cover vs. Stego.
- `security.py`: `EncTime` (`time.perf_counter()` on `cipher.encrypt` only, after Numba `warmup()`), NPCR, UACI, Entropy (256 bins), Correlation Coefficient — supporting both **Secret vs. Encrypted** and **Stego** measurements.
- `pipeline.py`: End-to-end orchestration.
- `scripts/run_single.py` & `scripts/run_benchmark.py`: Demo Figures 4–5 and 8,000-image Linnaeus 5 CSV benchmark (`tqdm`).

## 4. Phased Implementation Status & Testing Rules
- **Phase 1 (Skeleton & Config):** COMPLETED (by Claude Code).
- **Phase 2:** `src/crypto/` + `tests/test_crypto.py`.
- **Phase 3:** `src/stego/lsb.py` + `src/pipeline.py` + `tests/test_lsb.py` & `tests/test_pipeline.py`.
- **Phase 4:** `src/metrics/` + `scripts/run_single.py` & `scripts/run_benchmark.py`.
- Finish and pass all `pytest` suites for a phase before starting the next; assert exact recovery (`MSE == 0`) end-to-end.
