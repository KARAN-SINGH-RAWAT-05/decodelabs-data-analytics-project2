"""
DecodeLabs Data Analytics Internship - Project 2: Exploratory Data Analysis (EDA)

Run:  python eda_analysis.py
Needs: pandas, numpy, scipy, matplotlib, seaborn, openpyxl

Pipeline (IPO framework):
    INPUT    data/Dataset_for_Data_Analytics.xlsx
    PROCESS  quality checks -> descriptive stats -> outliers -> trends ->
             segments -> correlations (with simple significance tests)
    OUTPUT   outputs/*.csv, outputs/results.json, charts/*.png
"""
from pathlib import Path
import json

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data" / "Dataset_for_Data_Analytics.xlsx"
CHART_DIR = ROOT / "charts"
OUT_DIR = ROOT / "outputs"
NUMERIC = ["Quantity", "UnitPrice", "ItemsInCart", "TotalPrice"]

ACCENT, ALERT, MUTED = "#1f6f8b", "#d1495b", "#9aa5b1"
sns.set_theme(style="whitegrid", font="DejaVu Sans")
plt.rcParams.update({"axes.titleweight": "bold", "axes.titlesize": 12,
                     "figure.dpi": 150, "savefig.bbox": "tight"})


# --------------------------------------------------------------------------
# INPUT
# --------------------------------------------------------------------------
def load_raw(path=DATA_FILE):
    return pd.read_excel(path)


def prepare(raw):
    """Light prep only: blank CouponCode means 'no coupon used', not missing."""
    df = raw.copy()
    df["CouponCode"] = df["CouponCode"].fillna("None")
    df["Year"] = df["Date"].dt.year
    df["MonthStart"] = df["Date"].dt.to_period("M").dt.to_timestamp()
    df["MonthNum"] = df["Date"].dt.month
    return df


# --------------------------------------------------------------------------
# PROCESS
# --------------------------------------------------------------------------
def quality_checks(raw):
    calc = (raw["Quantity"] * raw["UnitPrice"]).round(2)
    return {
        "rows": int(len(raw)),
        "columns": int(raw.shape[1]),
        "missing_by_column": {k: int(v) for k, v in raw.isna().sum().items() if v},
        "duplicate_rows": int(raw.duplicated().sum()),
        "duplicate_order_ids": int(raw["OrderID"].duplicated().sum()),
        "duplicate_tracking": int(raw["TrackingNumber"].duplicated().sum()),
        "total_price_mismatch": int((abs(calc - raw["TotalPrice"]) > 0.01).sum()),
        "date_min": str(raw["Date"].min().date()),
        "date_max": str(raw["Date"].max().date()),
        "unique_customers": int(raw["CustomerID"].nunique()),
        "unique_addresses": int(raw["ShippingAddress"].nunique()),
    }


def descriptive_stats(df):
    rows = []
    for c in NUMERIC:
        s = df[c]
        rows.append({
            "column": c, "count": int(s.count()), "mean": s.mean(),
            "median": s.median(), "std": s.std(), "min": s.min(),
            "q1": s.quantile(.25), "q3": s.quantile(.75), "max": s.max(),
            "skew": s.skew(),
        })
    return pd.DataFrame(rows).round(3)


def outlier_report(df):
    rows, flagged = [], None
    for c in NUMERIC:
        s = df[c]
        q1, q3 = s.quantile([.25, .75])
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        z = (s - s.mean()) / s.std()
        rows.append({"column": c, "iqr_low": lo, "iqr_high": hi,
                     "iqr_outliers": int(((s < lo) | (s > hi)).sum()),
                     "zscore_outliers": int((z.abs() > 3).sum()),
                     "max_abs_z": float(z.abs().max())})
        if c == "TotalPrice":
            flagged = df[(s < lo) | (s > hi)].sort_values("TotalPrice", ascending=False)
    return pd.DataFrame(rows).round(3), flagged


def trend_analysis(df):
    monthly = (df.groupby("MonthStart")
                 .agg(orders=("OrderID", "count"), revenue=("TotalPrice", "sum"),
                      aov=("TotalPrice", "mean")).reset_index())
    monthly["rev_roll3"] = monthly["revenue"].rolling(3).mean()

    slope = stats.linregress(np.arange(len(monthly)), monthly["revenue"])

    # like-for-like: data stops on 30 Jun 2025, so compare Jan-Jun only
    h1 = df[df["MonthNum"] <= 6].groupby("Year").agg(
        orders=("OrderID", "count"), revenue=("TotalPrice", "sum"),
        aov=("TotalPrice", "mean")).reset_index()
    h1["rev_change_pct"] = h1["revenue"].pct_change() * 100
    h1["orders_change_pct"] = h1["orders"].pct_change() * 100

    yearly = df.groupby("Year").agg(orders=("OrderID", "count"),
                                    revenue=("TotalPrice", "sum")).reset_index()

    # calendar-month seasonality, normalised for years of exposure
    days = pd.Series(pd.date_range(df["Date"].min(), df["Date"].max())).dt.month.value_counts().sort_index()
    cal = df.groupby("MonthNum").agg(orders=("OrderID", "count"),
                                     revenue=("TotalPrice", "sum")).reindex(range(1, 13))
    cal["years_observed"] = [(days[m] / pd.Timestamp(2001, m, 1).days_in_month) for m in cal.index]
    cal["rev_per_year"] = cal["revenue"] / cal["years_observed"]
    expected = days / days.sum() * cal["orders"].sum()
    chi = stats.chisquare(cal["orders"], expected)
    cal = cal.reset_index().round(2)
    return monthly, h1, yearly, cal, slope, chi


def segment_table(df, col):
    t = (df.groupby(col).agg(orders=("OrderID", "count"), revenue=("TotalPrice", "sum"),
                             mean_order=("TotalPrice", "mean"),
                             median_order=("TotalPrice", "median")).reset_index())
    t["revenue_share_pct"] = t["revenue"] / t["revenue"].sum() * 100
    return t.sort_values("revenue", ascending=False).round(2)


def segment_tests(df):
    out = {}
    for col in ["Product", "CouponCode", "ReferralSource", "PaymentMethod"]:
        groups = [g["TotalPrice"].values for _, g in df.groupby(col)]
        out[f"kruskal_TotalPrice_by_{col}_p"] = float(stats.kruskal(*groups).pvalue)
    counts = df["OrderStatus"].value_counts()
    out["chisq_status_uniform_p"] = float(stats.chisquare(counts).pvalue)
    up = [g["UnitPrice"].values for _, g in df.groupby("Product")]
    out["anova_UnitPrice_by_Product_p"] = float(stats.f_oneway(*up).pvalue)
    return out


# --------------------------------------------------------------------------
# OUTPUT: charts
# --------------------------------------------------------------------------
def _save(fig, name):
    CHART_DIR.mkdir(exist_ok=True)
    fig.savefig(CHART_DIR / name)
    plt.close(fig)


def chart_distribution(df):
    mean, med = df["TotalPrice"].mean(), df["TotalPrice"].median()
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.hist(df["TotalPrice"], bins=36, color=ACCENT, alpha=.85, edgecolor="white")
    ax.axvline(med, color="#222", lw=2, ls="--", label=f"Median {med:,.0f}")
    ax.axvline(mean, color=ALERT, lw=2, label=f"Mean {mean:,.0f}")
    ax.set(xlabel="Order value (TotalPrice)", ylabel="Orders")
    ax.set_title(f"Mean is {(mean / med - 1) * 100:.0f}% above median: order values are right-skewed")
    ax.legend()
    _save(fig, "01_order_value_distribution.png")


def chart_boxplot(df, flagged):
    fig, ax = plt.subplots(figsize=(8, 3.2))
    sns.boxplot(x=df["TotalPrice"], color="#bcd6e0", fliersize=0, ax=ax)
    ax.scatter(flagged["TotalPrice"], np.zeros(len(flagged)), color=ALERT, zorder=5,
               label=f"{len(flagged)} IQR outliers")
    ax.set(xlabel="Order value (TotalPrice)", yticks=[])
    ax.set_title(f"{len(flagged)} high-value orders sit beyond the IQR fence "
                 f"({flagged['TotalPrice'].min():,.0f}+)")
    ax.legend(loc="upper right")
    _save(fig, "02_order_value_boxplot.png")


def chart_monthly(monthly):
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(monthly["MonthStart"], monthly["revenue"], color=MUTED, marker="o", ms=3.5, label="Monthly revenue")
    ax.plot(monthly["MonthStart"], monthly["rev_roll3"], color=ACCENT, lw=2.6, label="3-month average")
    ax.set(ylabel="Revenue", xlabel="")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1000:.0f}k"))
    ax.set_title("Revenue is noisy month to month, with a gentle downward drift")
    ax.legend()
    _save(fig, "03_monthly_revenue_trend.png")


def chart_h1(h1):
    fig, ax = plt.subplots(figsize=(6.4, 4))
    bars = ax.bar(h1["Year"].astype(str), h1["revenue"], color=[MUTED, MUTED, ACCENT])
    for b, chg in zip(bars, h1["rev_change_pct"]):
        label = f"{b.get_height() / 1000:,.0f}k" + ("" if np.isnan(chg) else f"\n({chg:+.1f}%)")
        ax.text(b.get_x() + b.get_width() / 2, b.get_height(), label, ha="center", va="bottom", fontsize=9)
    ax.set(ylabel="Jan-Jun revenue", ylim=(0, h1["revenue"].max() * 1.18))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1000:.0f}k"))
    ax.set_title("Like-for-like (Jan-Jun) revenue is down ~10% a year")
    _save(fig, "04_h1_revenue_comparison.png")


def chart_seasonality(cal):
    fig, ax = plt.subplots(figsize=(8.5, 4))
    colors = [ALERT if m == cal.loc[cal["rev_per_year"].idxmax(), "MonthNum"] else ACCENT for m in cal["MonthNum"]]
    ax.bar(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
           cal["rev_per_year"], color=colors)
    ax.axhline(cal["rev_per_year"].mean(), color="#222", ls="--", lw=1, label="Average month")
    ax.set(ylabel="Revenue per year observed")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1000:.0f}k"))
    ax.set_title("June looks strongest, but only 2-3 years back each month")
    ax.legend()
    _save(fig, "05_calendar_month_seasonality.png")


def chart_products(prod):
    p = prod.sort_values("revenue")
    fig, ax = plt.subplots(figsize=(7.5, 4))
    colors = [ALERT if i == 0 else ACCENT for i in range(len(p))]
    ax.barh(p["Product"], p["revenue"], color=colors)
    for y, (v, s) in enumerate(zip(p["revenue"], p["revenue_share_pct"])):
        ax.text(v, y, f"  {v / 1000:,.0f}k ({s:.1f}%)", va="center", fontsize=9)
    ax.set(xlabel="Revenue", xlim=(0, p["revenue"].max() * 1.25))
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1000:.0f}k"))
    top, low = prod.iloc[0], prod.iloc[-1]
    ax.set_title(f"{top['Product']} leads, {low['Product']} trails by "
                 f"{(1 - low['revenue'] / top['revenue']) * 100:.0f}%")
    _save(fig, "06_revenue_by_product.png")


def chart_status(status):
    s = status.sort_values("orders")
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    risky = s["OrderStatus"].isin(["Cancelled", "Returned"])
    ax.barh(s["OrderStatus"], s["orders"] / s["orders"].sum() * 100,
            color=[ALERT if r else ACCENT for r in risky])
    for y, v in enumerate(s["orders"] / s["orders"].sum() * 100):
        ax.text(v, y, f"  {v:.1f}%", va="center", fontsize=9)
    ax.set(xlabel="Share of orders (%)", xlim=(0, 28))
    risk_share = s.loc[risky, "orders"].sum() / s["orders"].sum() * 100
    ax.set_title(f"Cancelled + Returned = {risk_share:.0f}% of orders; only ~19% Delivered")
    _save(fig, "07_order_status_share.png")


def chart_coupon(coupon):
    c = coupon.sort_values("mean_order", ascending=False)
    x = np.arange(len(c))
    fig, ax = plt.subplots(figsize=(7.2, 4))
    ax.bar(x - .2, c["mean_order"], .4, color=ACCENT, label="Mean order value")
    ax.bar(x + .2, c["median_order"], .4, color=MUTED, label="Median order value")
    ax.set_xticks(x, c["CouponCode"])
    ax.set(ylabel="Order value", ylim=(0, c["mean_order"].max() * 1.3))
    ax.set_title("Coupons make no visible difference to order value")
    ax.legend(loc="upper center", ncol=2)
    _save(fig, "08_coupon_vs_order_value.png")


def chart_corr(df):
    corr = df[NUMERIC].corr()
    fig, ax = plt.subplots(figsize=(5.8, 4.6))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r", vmin=-1, vmax=1, center=0,
                linewidths=1, cbar_kws={"shrink": .8}, ax=ax)
    ax.set_title("UnitPrice and Quantity drive TotalPrice")
    _save(fig, "09_correlation_heatmap.png")
    return corr


# --------------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------------
def main():
    OUT_DIR.mkdir(exist_ok=True)
    raw = load_raw()
    df = prepare(raw)

    quality = quality_checks(raw)
    desc = descriptive_stats(df)
    outl, flagged = outlier_report(df)
    monthly, h1, yearly, cal, slope, chi = trend_analysis(df)
    prod = segment_table(df, "Product")
    status = segment_table(df, "OrderStatus")
    coupon = segment_table(df, "CouponCode")
    referral = segment_table(df, "ReferralSource")
    payment = segment_table(df, "PaymentMethod")
    tests = segment_tests(df)

    chart_distribution(df)
    chart_boxplot(df, flagged)
    chart_monthly(monthly)
    chart_h1(h1)
    chart_seasonality(cal)
    chart_products(prod)
    chart_status(status)
    chart_coupon(coupon)
    corr = chart_corr(df)

    # extra facts used in the write-up
    risk = status[status["OrderStatus"].isin(["Cancelled", "Returned"])]
    delivered = status[status["OrderStatus"] == "Delivered"].iloc[0]
    cust_orders = df["CustomerID"].value_counts()
    price_by_product = df.groupby("Product")["UnitPrice"].agg(["min", "max", "mean"]).round(2)

    results = {
        "quality": quality,
        "describe": desc.to_dict("records"),
        "outliers": outl.to_dict("records"),
        "flagged_orders": flagged[["OrderID", "Product", "Quantity", "UnitPrice", "TotalPrice", "OrderStatus"]]
        .to_dict("records"),
        "total_revenue": float(df["TotalPrice"].sum()),
        "trend_slope_per_month": float(slope.slope), "trend_slope_p": float(slope.pvalue),
        "h1": h1.round(2).to_dict("records"),
        "yearly": yearly.round(2).to_dict("records"),
        "calendar": cal.to_dict("records"),
        "month_orders_chisq_p": float(chi.pvalue),
        "monthly_orders_min": int(monthly["orders"].min()), "monthly_orders_max": int(monthly["orders"].max()),
        "monthly_orders_mean": float(monthly["orders"].mean()),
        "product": prod.to_dict("records"), "status": status.to_dict("records"),
        "coupon": coupon.to_dict("records"), "referral": referral.to_dict("records"),
        "payment": payment.to_dict("records"),
        "tests": tests,
        "risk_orders": int(risk["orders"].sum()), "risk_revenue": float(risk["revenue"].sum()),
        "delivered_orders": int(delivered["orders"]), "delivered_revenue": float(delivered["revenue"]),
        "repeat_customers": int((cust_orders > 1).sum()),
        "max_orders_one_customer": int(cust_orders.max()),
        "price_by_product": price_by_product.reset_index().to_dict("records"),
        "corr": corr.round(3).to_dict(),
    }

    desc.to_csv(OUT_DIR / "descriptive_statistics.csv", index=False)
    outl.to_csv(OUT_DIR / "outlier_summary.csv", index=False)
    flagged.to_csv(OUT_DIR / "flagged_high_value_orders.csv", index=False)
    monthly.to_csv(OUT_DIR / "monthly_trend.csv", index=False)
    prod.to_csv(OUT_DIR / "segment_product.csv", index=False)
    status.to_csv(OUT_DIR / "segment_order_status.csv", index=False)
    coupon.to_csv(OUT_DIR / "segment_coupon.csv", index=False)
    with open(OUT_DIR / "results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
