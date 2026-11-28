r"""Hình minh họa lý thuyết: giản đồ rẽ nhánh của ánh xạ Logistic và độ nhạy điều kiện đầu.

    .\.venv\Scripts\python.exe ..\Reports\My_reports\Latex\tools\make_theory_figures.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "figures" / "generated"
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.family": "Times New Roman", "mathtext.fontset": "stix",
                     "font.size": 10, "savefig.dpi": 220, "savefig.bbox": "tight",
                     "axes.spines.top": False, "axes.spines.right": False})

fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.6))
# (a) bifurcation diagram
rs = np.linspace(2.5, 4.0, 1800)
x = np.full_like(rs, 0.5)
for _ in range(600):
    x = rs * x * (1 - x)
pts_r, pts_x = [], []
for _ in range(150):
    x = rs * x * (1 - x)
    pts_r.append(rs.copy()); pts_x.append(x.copy())
axes[0].plot(np.concatenate(pts_r), np.concatenate(pts_x), ",", color="#1f4e8c", alpha=0.25)
axes[0].axvline(3.999, color="#dc2626", lw=0.9, ls="--")
axes[0].text(3.95, 0.04, "$r = 3.999$", color="#dc2626", ha="right", fontsize=9)
axes[0].set_xlabel("Tham số $r$"); axes[0].set_ylabel("$x_n$")
axes[0].set_title("(a) Giản đồ rẽ nhánh")
# (b) sensitivity to x0
n = 60
a = np.empty(n); b = np.empty(n)
a[0], b[0] = 0.785398, 0.785398 + 1e-10
for i in range(1, n):
    a[i] = 3.999 * a[i - 1] * (1 - a[i - 1])
    b[i] = 3.999 * b[i - 1] * (1 - b[i - 1])
axes[1].plot(a, "-o", ms=2.2, lw=0.9, color="#1f4e8c", label="$x_0 = 0.785398$")
axes[1].plot(b, "-s", ms=2.0, lw=0.9, color="#d97706", label="$x_0 + 10^{-10}$")
axes[1].set_xlabel("Bước lặp $n$"); axes[1].set_ylabel("$x_n$")
axes[1].set_title("(b) Nhạy cảm với điều kiện đầu ($r = 3.999$)")
# chú thích đặt ngoài vùng vẽ (dưới trục hoành) để không bị các đường che
axes[1].legend(frameon=False, fontsize=8, loc="upper center", ncol=2,
               bbox_to_anchor=(0.5, -0.27), handlelength=2.2, columnspacing=1.2)
fig.tight_layout()
fig.savefig(OUT / "logistic_map.png")
first = int(np.argmax(np.abs(a - b) > 0.1))
print("diverge (>0.1) at n =", first)
