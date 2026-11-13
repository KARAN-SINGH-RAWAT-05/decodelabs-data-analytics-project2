# DecodeLabs Data Analytics Internship - Project 2: Exploratory Data Analysis (EDA)

**Batch 2026 | Author: Karan Singh Rawat**

## What this project answers

Using an e-commerce order dataset (1,200 orders, Jan 2023 - Jun 2025), this EDA covers the three Project 2 requirements:

1. **Basic statistics:** mean, median, count, spread and five-number summaries
2. **Trends and outliers:** monthly and like-for-like trends, IQR and z-score outlier checks
3. **Key observations:** a written summary with quantified business impact and recommendations

## Headline findings

- The typical order is **824**, not the mean of 1,054: order values are right-skewed.
- **8 bulk orders** (Quantity 5 at high unit prices) are the only outliers, and they are real purchases, not entry errors.
- **Jan-Jun revenue fell about 10% a year** (286.5k, 257.1k, 231.9k); average order value is down 11.7% since 2023.
- **41% of orders are Cancelled or Returned** (519.7k of revenue); only 19% are Delivered.
- Differences by product, referral source, payment method and coupon are **not statistically significant**.
- Some fields look randomly generated (product-independent unit prices, near-uniform splits), so conclusions are illustrative.

Full write-up: [`outputs/EDA_Summary_Report.pdf`](outputs/EDA_Summary_Report.pdf)

## Method (Input - Process - Output)

| Stage | What happens |
|---|---|
| Input | `data/Dataset_for_Data_Analytics.xlsx`; integrity checks (duplicates, TotalPrice = Quantity x UnitPrice, missing values) |
| Process | Descriptive statistics, IQR and z-score outliers, trend analysis, segment breakdowns, correlations, significance tests (Kruskal-Wallis, chi-square) |
| Output | PDF report, 9 charts, CSV summaries, `results.json` |

CouponCode is blank in 309 rows (25.8%); this is read as "no coupon used" and labelled `None`, not imputed.

## Repository structure

```
.
├── data/Dataset_for_Data_Analytics.xlsx
├── eda_analysis.py          # full analysis, charts, CSVs, results.json
├── build_report.py          # builds the PDF from results.json and charts
├── charts/                  # 9 PNG charts
├── outputs/                 # CSV summaries, results.json, EDA_Summary_Report.pdf
├── requirements.txt
└── README.md
```

## How to run

```bash
pip install -r requirements.txt
python eda_analysis.py     # statistics, charts, CSVs
python build_report.py     # PDF summary report
```

## Limitations

30 months of data; no cost or margin fields; no currency stated; associations are not causal; seasonal conclusions rest on two or three observations per month.
