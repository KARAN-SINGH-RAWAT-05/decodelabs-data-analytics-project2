"""
Builds outputs/EDA_Summary_Report.pdf from outputs/results.json and charts/*.png.
Run eda_analysis.py first, then:  python build_report.py
Needs: reportlab, Pillow
"""
import json
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parent
R = json.load(open(ROOT / "outputs" / "results.json"))
OUT = ROOT / "outputs" / "EDA_Summary_Report.pdf"
CH = ROOT / "charts"

TEAL, RED, INK = colors.HexColor("#1f6f8b"), colors.HexColor("#d1495b"), colors.HexColor("#1b2a35")
ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=16, textColor=INK, spaceBefore=10, spaceAfter=6)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=11.5, textColor=TEAL, spaceBefore=10, spaceAfter=3)
BODY = ParagraphStyle("B", parent=ss["BodyText"], fontSize=9.6, leading=13.4, spaceAfter=4)
SMALL = ParagraphStyle("S", parent=BODY, fontSize=8.2, leading=11, textColor=colors.HexColor("#55606b"))
TITLE = ParagraphStyle("T", parent=ss["Title"], fontSize=22, textColor=INK, alignment=0, spaceAfter=2)
SUB = ParagraphStyle("Sub", parent=BODY, fontSize=11, textColor=TEAL, spaceAfter=10)


def n(x, d=0):
    return f"{x:,.{d}f}"


def img(name, width=14.5 * cm):
    w, h = PILImage.open(CH / name).size
    return Image(str(CH / name), width=width, height=width * h / w)


def table(rows, widths, hdr=True):
    t = Table(rows, colWidths=widths, repeatRows=1 if hdr else 0)
    st = [("FONTSIZE", (0, 0), (-1, -1), 8.4), ("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#c9d3da")),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
          ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if hdr:
        st += [("BACKGROUND", (0, 0), (-1, 0), TEAL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
               ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f6f8")])]
    t.setStyle(TableStyle(st))
    return t


def finding(title, text, chart=None):
    block = [Paragraph(title, H2), Paragraph(text, BODY)]
    if chart:
        block.append(img(chart))
    return KeepTogether(block)


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#6b7782"))
    canvas.drawString(2 * cm, 1.1 * cm, "DecodeLabs Data Analytics Internship | Project 2: EDA | Batch 2026")
    canvas.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f"Page {doc.page}")
    canvas.restoreState()


def build():
    q, d = R["quality"], {x["column"]: x for x in R["describe"]}
    tp = d["TotalPrice"]
    h1 = R["h1"]
    cal = R["calendar"]
    jun = cal[5]
    prod = R["product"]
    status = {s["OrderStatus"]: s for s in R["status"]}
    coupon = {c["CouponCode"]: c for c in R["coupon"]}
    t = R["tests"]
    fl = R["flagged_orders"]
    fl_total = sum(o["TotalPrice"] for o in fl)
    fl_status = {}
    for o in fl:
        fl_status[o["OrderStatus"]] = fl_status.get(o["OrderStatus"], 0) + 1
    aov_chg = (h1[2]["aov"] / h1[0]["aov"] - 1) * 100
    risk_pct_orders = R["risk_orders"] / q["rows"] * 100
    risk_pct_rev = R["risk_revenue"] / R["total_revenue"] * 100
    deliv_pct = R["delivered_orders"] / q["rows"] * 100
    corr = R["corr"]
    ref = {x["ReferralSource"]: x for x in R["referral"]}
    pay = {x["PaymentMethod"]: x for x in R["payment"]}
    top_p, low_p = prod[0], prod[-1]
    gap = (1 - low_p["revenue"] / top_p["revenue"]) * 100
    coupon_means = [c["mean_order"] for c in R["coupon"]]

    s = []
    s += [Paragraph("Project 2: Exploratory Data Analysis", TITLE),
          Paragraph(f"Order data, {q['date_min']} to {q['date_max']} | {n(q['rows'])} orders, {q['columns']} columns", SUB)]

    # ---- 1. Problem statement
    s += [Paragraph("1. Problem statement", H1),
          Paragraph("What does a typical order look like, how has revenue moved over time, which segments matter, "
                    "and what could mislead a decision-maker if the data were taken at face value?", BODY)]

    # ---- 2. Methodology
    s += [Paragraph("2. Methodology (Input - Process - Output)", H1),
          Paragraph(f"<b>Input:</b> Dataset_for_Data_Analytics.xlsx ({n(q['rows'])} rows). Integrity checks found "
                    f"{q['duplicate_rows']} duplicate rows, {q['duplicate_order_ids']} duplicate OrderIDs, and "
                    f"TotalPrice = Quantity x UnitPrice in every row ({q['total_price_mismatch']} mismatches). The only blank "
                    f"column is CouponCode ({q['missing_by_column']['CouponCode']} rows, {q['missing_by_column']['CouponCode'] / q['rows'] * 100:.1f}%), "
                    "read as 'no coupon used' and labelled 'None' rather than imputed.", BODY),
          Paragraph("<b>Process:</b> mean, median, count and the five-number summary per numeric column; outlier detection "
                    "with both the IQR rule (1.5 x IQR) and z-scores (|z| &gt; 3); monthly and like-for-like trend "
                    "comparison; segment breakdowns; Pearson correlation. Because group differences in random-looking data "
                    "are easy to over-read, each segment comparison also carries a significance test "
                    "(Kruskal-Wallis or chi-square). A p-value above 0.05 means the gap is consistent with chance.", BODY),
          Paragraph("<b>Output:</b> this report, nine charts, CSV summaries, and the reproducible script eda_analysis.py.", BODY)]

    # ---- 3. Summary of headline findings
    s += [Paragraph("3. Headline findings", H1)]
    bullets = [
        f"Typical order is <b>{n(tp['median'])}</b>, not {n(tp['mean'])}: order values are right-skewed (skew {tp['skew']:.2f}).",
        f"Revenue is drifting down: Jan-Jun revenue fell <b>{abs(h1[1]['rev_change_pct']):.1f}%</b> then <b>{abs(h1[2]['rev_change_pct']):.1f}%</b>; "
        f"average order value is down <b>{abs(aov_chg):.1f}%</b> since 2023.",
        f"<b>{risk_pct_orders:.0f}%</b> of orders ({n(R['risk_orders'])}) are Cancelled or Returned, worth {n(R['risk_revenue'])} "
        f"({risk_pct_rev:.0f}% of revenue). Only {deliv_pct:.0f}% are Delivered.",
        f"{len(fl)} bulk orders (Quantity 5 at high unit prices) are the only outliers: genuine signal, not typos.",
        "Product, channel, payment method and coupon differences are all statistically indistinguishable from chance.",
        "Several fields behave like randomly generated data (see finding 10), so conclusions should be presented as illustrative.",
    ]
    for b in bullets:
        s.append(Paragraph(f"&bull; {b}", BODY))

    # ---- 4. Findings
    s += [Paragraph("4. Detailed findings", H1)]

    s.append(Paragraph("Descriptive statistics", H2))
    rows = [["Column", "Count", "Mean", "Median", "Std", "Min", "Q1", "Q3", "Max"]]
    for c in ["Quantity", "UnitPrice", "ItemsInCart", "TotalPrice"]:
        x = d[c]
        rows.append([c, n(x["count"]), n(x["mean"], 2), n(x["median"], 2), n(x["std"], 2), n(x["min"], 2),
                     n(x["q1"], 2), n(x["q3"], 2), n(x["max"], 2)])
    s += [table(rows, [2.6 * cm, 1.4 * cm, 1.9 * cm, 1.9 * cm, 1.9 * cm, 1.7 * cm, 1.9 * cm, 1.9 * cm, 1.9 * cm]), Spacer(1, 6)]

    s.append(finding(
        f"1. Mean ({n(tp['mean'])}) sits {(tp['mean'] / tp['median'] - 1) * 100:.0f}% above median ({n(tp['median'])})",
        "Quantity and UnitPrice are each roughly symmetric (skew near 0), but their product, TotalPrice, is right-skewed "
        f"(skew {tp['skew']:.2f}). A few large baskets pull the mean up, so the median is the better 'typical order' figure.",
        "01_order_value_distribution.png"))

    s.append(finding(
        f"2. Eight bulk orders are the only outliers ({n(fl_total)} combined)",
        f"The IQR rule flags {len(fl)} orders above {n(R['outliers'][3]['iqr_high'])}. All have Quantity = 5 and a unit price of "
        f"{n(min(o['UnitPrice'] for o in fl))}-{n(max(o['UnitPrice'] for o in fl))}, so they are legitimate maximum-quantity, "
        f"high-price purchases rather than entry errors. The z-score method flags none (largest |z| = {R['outliers'][3]['max_abs_z']:.2f}), "
        "which shows why the IQR rule is preferred for skewed data. Their statuses are: "
        + ", ".join(f"{v} {k}" for k, v in sorted(fl_status.items())) + ". Only 3 of 8 were delivered.",
        "02_order_value_boxplot.png"))

    s.append(finding(
        f"3. Like-for-like revenue is down about 10% a year, driven by smaller baskets",
        f"Data stops on 30 June 2025, so full-year totals are not comparable; Jan-Jun is. H1 revenue: {n(h1[0]['revenue'])} (2023), "
        f"{n(h1[1]['revenue'])} (2024, {h1[1]['rev_change_pct']:+.1f}%), {n(h1[2]['revenue'])} (2025, {h1[2]['rev_change_pct']:+.1f}%). "
        f"Orders fell {abs(h1[1]['orders_change_pct']):.1f}% then {abs(h1[2]['orders_change_pct']):.1f}%, while average order value dropped from "
        f"{n(h1[0]['aov'])} to {n(h1[2]['aov'])} ({aov_chg:.1f}%). Caution: a straight-line fit through all 30 months slopes down by "
        f"{abs(R['trend_slope_per_month']):.0f} per month but is not significant on its own (p = {R['trend_slope_p']:.2f}); the repeated "
        "H1 decline is suggestive, not conclusive.",
        "03_monthly_revenue_trend.png"))
    s.append(img("04_h1_revenue_comparison.png", 11 * cm))

    s.append(finding(
        "4. No reliable seasonality",
        f"June looks strongest ({n(jun['rev_per_year'])} revenue per year observed, against an all-month average of "
        f"{n(sum(c['rev_per_year'] for c in cal) / 12)}), but it leans on a single spike in June 2024. Monthly orders range "
        f"{R['monthly_orders_min']}-{R['monthly_orders_max']} around a mean of {R['monthly_orders_mean']:.0f}, and order counts by calendar "
        f"month do not differ significantly from an even spread (chi-square p = {R['month_orders_chisq_p']:.2f}). "
        "January-June each have three years of data and July-December only two, so every month is scaled by years observed.",
        "05_calendar_month_seasonality.png"))

    s.append(finding(
        f"5. {top_p['Product']} leads and {low_p['Product']} trails by {gap:.0f}%, but the gap is not significant",
        f"{top_p['Product']} earns {n(top_p['revenue'])} ({top_p['revenue_share_pct']:.1f}% of revenue) against {low_p['Product']} at "
        f"{n(low_p['revenue'])} ({low_p['revenue_share_pct']:.1f}%). {low_p['Product']} also has the lowest median order "
        f"({n(low_p['median_order'])} vs {n(top_p['median_order'])}). Order value does not differ significantly across products "
        f"(Kruskal-Wallis p = {t['kruskal_TotalPrice_by_Product_p']:.2f}).",
        "06_revenue_by_product.png"))

    s.append(finding(
        f"6. {risk_pct_orders:.0f}% of orders are Cancelled or Returned; only {deliv_pct:.0f}% are Delivered",
        f"Cancelled ({n(status['Cancelled']['orders'])}) and Returned ({n(status['Returned']['orders'])}) orders carry "
        f"{n(R['risk_revenue'])} of revenue, {risk_pct_rev:.0f}% of the {n(R['total_revenue'])} total. Delivered revenue is {n(R['delivered_revenue'])}. "
        f"The five statuses are almost perfectly evenly split (chi-square p = {t['chisq_status_uniform_p']:.2f}). Real order books are usually "
        "dominated by delivered orders, so this field should be verified before anyone relies on it.",
        "07_order_status_share.png"))

    s.append(finding(
        "7. Coupons show no effect on order value, and discounts are not recorded in totals",
        f"Mean order value is {n(min(coupon_means))}-{n(max(coupon_means))} across FREESHIP, SAVE10 and WINTER15, versus {n(coupon['None']['mean_order'])} with no coupon "
        f"(Kruskal-Wallis p = {t['kruskal_TotalPrice_by_CouponCode_p']:.2f}). Since TotalPrice equals Quantity x UnitPrice in every row, "
        "no coupon discount is reflected in the total, so the true cost of couponing cannot be measured from this file.",
        "08_coupon_vs_order_value.png"))

    s.append(Paragraph("8. Channel and payment method: small gaps, none significant", H2))
    s.append(Paragraph(
        f"Instagram is the top referral source ({n(ref['Instagram']['revenue'])}, {ref['Instagram']['revenue_share_pct']:.1f}% of revenue) and Referral the lowest "
        f"({n(ref['Referral']['revenue'])}); average order value is highest for Facebook ({n(ref['Facebook']['mean_order'])}). Credit Card has the highest average order value "
        f"({n(pay['Credit Card']['mean_order'])}) and Debit Card the lowest ({n(pay['Debit Card']['mean_order'])}). Neither difference is significant "
        f"(p = {t['kruskal_TotalPrice_by_ReferralSource_p']:.2f} and {t['kruskal_TotalPrice_by_PaymentMethod_p']:.2f}).", BODY))

    s.append(finding(
        "9. UnitPrice and Quantity drive order value; correlation is a clue, not a verdict",
        f"TotalPrice correlates with UnitPrice (r = {corr['TotalPrice']['UnitPrice']:.2f}), Quantity (r = {corr['TotalPrice']['Quantity']:.2f}) and ItemsInCart "
        f"(r = {corr['TotalPrice']['ItemsInCart']:.2f}). Quantity and ItemsInCart move together (r = {corr['Quantity']['ItemsInCart']:.2f}), while UnitPrice is "
        f"unrelated to Quantity (r = {corr['Quantity']['UnitPrice']:.2f}): customers do not buy fewer units of pricier items. "
        "TotalPrice is computed from the other two columns, so its correlations are partly mechanical.",
        "09_correlation_heatmap.png"))

    s.append(Paragraph("10. Data-integrity flags", H2))
    pp = R["price_by_product"]
    s.append(Paragraph(
        f"&bull; <b>UnitPrice is not product-specific.</b> Every product spans roughly {n(min(p['min'] for p in pp))} to {n(max(p['max'] for p in pp))} "
        f"with averages of {n(min(p['mean'] for p in pp))}-{n(max(p['mean'] for p in pp))} (ANOVA p = {t['anova_UnitPrice_by_Product_p']:.2f}); a Phone or a Chair is as likely to cost "
        "700 as 12.<br/>"
        f"&bull; <b>Almost no repeat customers.</b> {n(q['unique_customers'])} unique customers placed {n(q['rows'])} orders; only {R['repeat_customers']} "
        f"customers ordered twice (maximum {R['max_orders_one_customer']}).<br/>"
        f"&bull; <b>Uniform splits everywhere.</b> Quantity, status, payment and referral values are all close to evenly spread, and addresses are all "
        f"'NNN Main St' ({n(q['unique_addresses'])} distinct).<br/>"
        "Together these suggest the file is sample or generated data. The methods transfer to real data, but business conclusions here are illustrative.", BODY))

    # ---- 5. Recommendations
    s += [Paragraph("5. Recommendations", H1)]
    recs = [
        "<b>Report the median beside the mean</b> for order value; use IQR, not z-scores, for outlier screening on this skewed field.",
        f"<b>Audit the order-status pipeline.</b> If real, {n(R['risk_revenue'])} of revenue sits in Cancelled/Returned orders; recovering even a quarter "
        f"would add about {n(R['risk_revenue'] * .25)}, roughly {R['risk_revenue'] * .25 / R['total_revenue'] * 100:.0f}% of total revenue.",
        f"<b>Investigate the {abs(aov_chg):.1f}% fall in average order value.</b> Quantity is a main driver, so test bundles or quantity-based offers.",
        "<b>Record coupon discount amounts</b> and run a controlled test before spending further on coupons.",
        "<b>Treat the 5-unit, high-price orders as a VIP segment</b> and check why only 3 of 8 reached Delivered.",
        "<b>Fix data capture:</b> a product-to-price mapping, validated status values, and customer attributes enabling proper segmentation.",
    ]
    for i, r in enumerate(recs, 1):
        s.append(Paragraph(f"{i}. {r}", BODY))

    s += [Paragraph("Limitations", H2),
          Paragraph("30 months of data; no cost or margin fields; no currency stated (figures are in the dataset's own units); "
                    "associations are not causal; and seasonal conclusions rest on two or three observations per month.", SMALL)]

    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                            bottomMargin=1.8 * cm, title="Project 2 - EDA Summary Report", author="Karan Singh Rawat")
    doc.build(s, onFirstPage=footer, onLaterPages=footer)
    print("wrote", OUT)


if __name__ == "__main__":
    build()
