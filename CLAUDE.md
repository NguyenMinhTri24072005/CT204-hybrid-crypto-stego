# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Python reproduction of the paper *"A Hybrid Crypto-Steganography Framework for Secure Image Transfer"* (ICITSC 2025, originally MATLAB R2024a) for course CT204 Information Security. A grayscale secret image is encrypted with one of three ciphers (3DES-LSB, AES-LSB, Chaotic + PRNG Masking), the ciphertext is hidden in the 1–3 LSBs of a 256×256 RGB cover, then extracted and decrypted; metrics are compared against the paper's Table 2.

- **Paper spec:** `Docs/145987.md` (token-cheap markdown of `Docs/145987.pdf`; figures in `Docs/145987_assets/`). Read the relevant section there instead of the PDF.
- **Code lives in `SOURCES/`.** The git repo root is the parent folder (`Project/`); `Docs/` is outside the code tree.

## Environment & commands (Windows)

Python 3.12 (`pyenv-win`, `SOURCES/.python-version`) with the venv at `SOURCES/.venv`. Always use the venv executables, never bare `python`/`pytest`. Run everything from `SOURCES/`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\pytest.exe -q                                   # all tests
.\.venv\Scripts\pytest.exe tests/test_crypto.py -q              # one file
.\.venv\Scripts\pytest.exe "tests/test_crypto.py::test_name" -q # one test
.\.venv\Scripts\python.exe -m scripts.run_single                # demo: one cover/secret pair → images + histograms
.\.venv\Scripts\python.exe -m scripts.run_benchmark             # batch over Linnaeus 5 → CSV
.\.venv\Scripts\python.exe app.py                               # offline Tkinter desktop UI (Phase 6A)
```

Imports are package-absolute (`from src.crypto.aes_cipher import AESCipher`); pytest resolves them via `pythonpath = .` in its config.

## Architecture

Data flow (`src/pipeline.py` wires it end to end):

```
secret (H×W uint8) → bytes → BaseCipher.encrypt → ciphertext
  → lsb.embed(cover, header+ciphertext) → stego (.png, lossless)
  → lsb.extract(stego) → header+ciphertext → BaseCipher.decrypt → reshape(H, W) → recovered
metrics: visual (cover vs stego), security (secret vs encrypted, and on stego)
```

### `configs/default.yaml`
Single source of all parameters: chaotic `x0=0.785398`, `r=3.999`, ECC mask seed, key-generation seed, key/IV lengths, data/result paths, max LSBs. Code must not hard-code these values. Load it with `src.config.load_config()`, which returns a dict and resolves `paths.*` and `secret.path` to absolute paths relative to `SOURCES/`.

### `src/crypto/` — Strategy pattern
`base.py` defines abstract `BaseCipher` with `encrypt(bytes) -> bytes` and `decrypt(bytes) -> bytes`. Pipeline/stego code depends only on this interface; ciphers are chosen by name from config.

| File | Cipher | Key / IV | Notes |
|---|---|---|---|
| `des3_cipher.py` | 3DES-192, CBC, EDE | 24 B key / 8 B IV | `pycryptodome` `DES3`; PKCS7 pad to 8 B; use `DES3.adjust_key_parity` (pycryptodome rejects degenerate 3DES keys) |
| `aes_cipher.py` | AES-128, CBC | 16 B key / 16 B IV | `pycryptodome` `AES`; PKCS7 pad to 16 B |
| `chaotic_cipher.py` | Logistic map ⊕ simulated ECC mask | x0, r, seed | Stream/XOR, no padding: `enc = S ^ chaos_mask ^ ecc_mask`; decrypt is the same operation |

Chaotic details: `x_{n+1} = r·x_n·(1−x_n)`, generate N values (N = payload length) in a `@numba.njit` loop, scale to uint8 with a single documented rule (e.g. `floor(x·256)` clipped to 255 — the paper does not specify; keep it consistent and record it in the docstring). ECC mask = `np.random.default_rng(seed).integers(0, 256, N, dtype=np.uint8)` (the paper's ECC is only *simulated*).

Keys/IVs are generated deterministically from the config seed so encrypt/decrypt and benchmark runs are reproducible; keys are never stored in the stego image.

### `src/stego/lsb.py`
- Fully vectorized NumPy bit operations (`np.unpackbits`/`packbits`, masks, reshape) — no per-pixel Python loops.
- Bits are written across R, G, B channels of the flattened cover. `num_lsb ∈ {1,2,3}` = smallest k such that `len(bits) ≤ H·W·3·k`; if 3 LSBs are not enough, scale the cover up (e.g. `cv2.resize`, INTER_CUBIC) until it fits.
- A small fixed-size header is embedded first (always at 1 LSB so it can be read before `num_lsb` is known): ciphertext length, secret `(H, W)`, `num_lsb`. Extraction must need nothing but the stego image + cipher.
- Stego images are saved as PNG only (JPEG destroys LSBs).

### `src/metrics/`
- `visual.py`: MSE, PSNR (`10·log10(255²/MSE)`), SSIM (`skimage.metrics`, `channel_axis=-1` for RGB) — cover vs stego.
- `security.py`: `EncTime`, NPCR, UACI, entropy (`−Σ p log2 p`, 256 bins), correlation coefficient. Functions accept any two images so they can run on **secret vs encrypted** and on **stego** images.
  - `EncTime` times only `cipher.encrypt` with `time.perf_counter()`; call the chaotic cipher once on a dummy input before timing to exclude Numba JIT compilation.

### `scripts/`
- `run_single.py`: one cover + secret through all three ciphers; saves cover/secret/encrypted/stego/recovered images and histograms (reproduces Figures 4–5) to `results/`.
- `run_benchmark.py`: all 8,000 Linnaeus 5 images (`data/linnaeus5/`, 5 classes × (1200 train + 400 test), 256×256) × 3 ciphers; per-image rows + averages to CSV (reproduces Table 2). Use `tqdm`.

### `tests/`
`test_crypto.py` (round-trip, key/IV sizes, padding, determinism), `test_lsb.py` (embed/extract round-trip, header, capacity → `num_lsb`, scale-up), `test_pipeline.py` (end-to-end: recovered secret identical, MSE = 0).

## Reproduction targets & known paper quirks

Paper Table 2 averages (3DES / AES / Chaotic): MSE ≈ 0.50, PSNR ≈ 51.15 dB, SSIM ≈ 0.998, EncTime 3.55e-3 / 6.0e-4 / 3.6e-5 s, NPCR ≈ 99.6 %, UACI ≈ 30.8–31.0 %, correlation ≈ 0, entropy ≈ 7.05 / 7.05 / 6.95.

- MSE ≈ 0.5 / PSNR ≈ 51.14 dB is exactly what 1-LSB embedding of a random bitstream filling the whole cover gives; payload size (secret dimensions) drives these numbers, so keep the secret size configurable.
- The paper's secret is a grayscale coins image (MATLAB `coins.png` is 246×300; `skimage.data.coins()` is 303×384 — different sizes give different capacity/`num_lsb`).
- Entropy ≈ 7.0 (< 8) and UACI < 33.44 % suggest the paper measured some metrics on stego images or against a non-uniform secret; report both measurement targets and note which matches.
- Paper text refers to "Eq. 1" for MSE; it means Eq. 3.

## Implementation phases

1. Project skeleton: `configs/default.yaml`, pytest config, `SOURCES/.gitignore`. (Completed)
2. `src/crypto/` + `tests/test_crypto.py`. (Completed)
3. `src/stego/lsb.py` + `src/pipeline.py` + `tests/test_lsb.py`, `tests/test_pipeline.py`. (Completed)
4. `src/metrics/` + `scripts/run_single.py`, `scripts/run_benchmark.py`. (Completed)
5. Full 8,000-image benchmark (`results/*.csv`) + `notebooks/visualize_results.ipynb`. (Completed)
6. Offline Tkinter Desktop UI (`SOURCES/app.py`, `SOURCES/src/ui/*`, `SOURCES/tests/test_ui_controller.py`) & PyInstaller `.exe` readiness — **strictly follow `Plans/04_TKINTER_UI_SPEC_AND_PLAN.md` without modifying any Phase 1–4 core files**.

## Gitignore note

The root `Project/.gitignore` patterns `data/linnaeus5/` and `results/*.csv|png` contain a slash, so git anchors them to `Project/` and they do **not** match `SOURCES/data/...` or `SOURCES/results/...`. Put project-specific ignores in `SOURCES/.gitignore`.
