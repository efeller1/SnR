import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, numpy as np
from scipy import stats
from dual_momentum_load import load

d = load()
m, s = d["model"].to_numpy() * 100, d["spx"].to_numpy() * 100
def st(x):
    return dict(mu=x.mean(), sd=x.std(ddof=1), sk=stats.skew(x, bias=False),
                ku=stats.kurtosis(x, bias=False), pos=(x > 0).mean(), lo=x.min(), hi=x.max())
A, B = st(m), st(s)

SURF, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e6e5e0"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "text.color": INK,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False})

fig = plt.figure(figsize=(14, 7.6), facecolor=SURF)
gs = fig.add_gridspec(2, 2, width_ratios=[1.55, 1], height_ratios=[1, 0.24], hspace=0.30, wspace=0.18)
ax, qq, tb = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[1, :])
for a in (ax, qq):
    a.set_facecolor(SURF); a.grid(axis="y", color=GRID, lw=0.8); a.set_axisbelow(True)

# Left: model histogram, fitted normal, sigma bands, S&P shape for comparison
mu, sd = A["mu"], A["sd"]
lo, hi = -15, 19
bins = np.arange(lo, hi + 0.01, 1.0)
for k, al in ((2, 0.05), (1, 0.09)):
    ax.axvspan(mu - k * sd, mu + k * sd, color=INK2, alpha=al, lw=0)
ax.hist(m, bins=bins, density=True, color=BLUE, edgecolor=SURF, lw=2, label="Dual Momentum: monthly returns")
g = np.linspace(lo, hi, 500)
ax.plot(g, stats.norm.pdf(g, mu, sd), color=ORANGE, lw=2, label="Normal curve, same mean and σ")
ax.plot(g, stats.gaussian_kde(s)(g), color=INK2, lw=1.6, ls="--", label="S&P 500 (VFINX): actual shape")
ax.axvline(0, color=MUTED, lw=1)
ax.axvline(mu, color=INK, lw=1.3)
ymax = ax.get_ylim()[1] * 1.12; ax.set_ylim(0, ymax)
for k in (-2, -1, 1, 2):
    ax.text(mu + k * sd, ymax * 0.985, f"{k:+d}σ\n{mu + k * sd:+.1f}%", ha="center", va="top", fontsize=8.5, color=INK2)
ax.text(mu, ymax * 0.875, f"mean {mu:+.2f}%", ha="center", fontsize=9, color=INK,
        bbox=dict(boxstyle="round,pad=0.2", fc=SURF, ec="none"))
ax.set_xlim(lo, hi)
ax.set_xlabel("Monthly return, %"); ax.set_ylabel("Density")
ax.set_title("Monthly return distribution with ±1σ / ±2σ bands", loc="left", fontsize=12, fontweight="bold")
ax.legend(frameon=False, loc="upper left", fontsize=9, bbox_to_anchor=(0, 0.86))
best = d.loc[d["model"].idxmax()]
ax.annotate(f"Best month {A['hi']:+.1f}%\n({int(best.month)}/{int(best.year)})", xy=(A["hi"], 0.004),
            xytext=(A["hi"], ymax * 0.30), ha="center", fontsize=8.5, color=INK2,
            arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))

# Right: Q-Q plot vs normal, both series standardized
for x, col, lab in ((s, MUTED, "S&P 500"), (m, BLUE, "Dual Momentum")):
    z = (x - x.mean()) / x.std(ddof=1)
    osm, osr = stats.probplot(z, dist="norm", fit=False)
    qq.scatter(osm, osr, s=24, color=col, edgecolor=SURF, lw=1, zorder=3, label=lab)
qq.plot([-3, 3], [-3, 3], color=ORANGE, lw=2, label="Perfectly normal", zorder=2)
qq.set_xlim(-3, 3); qq.set_ylim(-3.6, 4.2)
qq.set_xlabel("Expected σ if returns were normal"); qq.set_ylabel("Actual σ")
qq.set_title("Q-Q plot: where the tails differ", loc="left", fontsize=12, fontweight="bold")
qq.legend(frameon=False, loc="upper left", fontsize=9)
qq.text(2.9, -3.45, "Blue curls up on the right: big winning months\n"
        "are more frequent than a normal curve predicts.\n"
        "On the left blue sits above the line (losses milder\nthan normal); gray dips below (S&P losses bigger).",
        ha="right", va="bottom", fontsize=8.3, color=INK2)

# Bottom: stats table
tb.axis("off")
cols = ["", "Mean / mo", "Std dev / mo", "Std dev / yr", "Skewness", "Excess kurtosis", "Up months", "Worst month", "Best month"]
rows = [["Dual Momentum", f"{A['mu']:+.2f}%", f"{A['sd']:.2f}%", f"{A['sd']*np.sqrt(12):.1f}%", f"{A['sk']:+.2f}",
         f"{A['ku']:+.2f}", f"{A['pos']:.0%}", f"{A['lo']:+.1f}%", f"{A['hi']:+.1f}%"],
        ["S&P 500 (VFINX)", f"{B['mu']:+.2f}%", f"{B['sd']:.2f}%", f"{B['sd']*np.sqrt(12):.1f}%", f"{B['sk']:+.2f}",
         f"{B['ku']:+.2f}", f"{B['pos']:.0%}", f"{B['lo']:+.1f}%", f"{B['hi']:+.1f}%"]]
t = tb.table(cellText=rows, colLabels=cols, loc="center", cellLoc="center", colLoc="center")
t.auto_set_font_size(False); t.set_fontsize(10); t.scale(1, 1.7)
for (r, c), cell in t.get_celld().items():
    cell.set_edgecolor(GRID); cell.set_facecolor(SURF)
    cell.get_text().set_color(INK if r else INK2)
    if r == 0: cell.get_text().set_fontweight("bold")
    if c == 0: cell.get_text().set_ha("left"); cell.get_text().set_fontweight("bold"); cell.set_width(0.14)

fig.suptitle("Dual Momentum Model: return distribution, skew and kurtosis", x=0.012, y=0.985, ha="left", fontsize=15, fontweight="bold")
fig.text(0.012, 0.935, f"{len(d)} monthly returns, Jan 2017 to Feb 2026. Top 3 of QQQ / TLT / GLD / XLE / GBTC, "
         "risk-parity weighted, UUP when trend is negative. Positive skew + fat tails = upside surprises.",
         fontsize=9.5, color=INK2)
fig.text(0.012, 0.01, "Source: Model_Backtest_20260304214422.xlsx (simulated backtest, monthly rebalancing). "
         "Skew and kurtosis are sample-adjusted and match the workbook. Past simulated results do not guarantee future returns.",
         fontsize=8, color=MUTED)
fig.subplots_adjust(left=0.05, right=0.985, top=0.88, bottom=0.05)
fig.savefig("/home/user/SnR/reports/dual_momentum_distribution.png", dpi=160, facecolor=SURF)
