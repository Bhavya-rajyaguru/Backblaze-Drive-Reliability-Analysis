import pandas as pd
from scipy.stats import chi2

# Set the results folder
from config import folder

# Read current classifications and daily results
models = pd.read_csv(folder / "model_classification.csv")
daily = pd.read_csv(
    folder / "daily_model_summary.csv",
    parse_dates=["date"]
)

# Select confirmed HDDs
hdd_models = models.loc[models["drive_type"] == "HDD", "model"]
hdd = daily[daily["model"].isin(hdd_models)]

# Summarise exposure and failure flags
summary = hdd.groupby("model").agg(
    first_seen=("date", "min"),
    last_seen=("date", "max"),
    days_observed=("date", "nunique"),
    average_daily_drives=("observed_drives", "mean"),
    drive_days=("drive_days", "sum"),
    failure_flags=("failure_flag_rows", "sum")
)

# Calculate annualised rates
scale = 365 / summary["drive_days"] * 100
flags = summary["failure_flags"]
summary["afr_percent"] = flags * scale

# Calculate Poisson confidence intervals
summary["lower_95_percent"] = 0.0
positive = flags > 0

summary.loc[positive, "lower_95_percent"] = (
    chi2.ppf(0.025, 2 * flags[positive]) / 2 * scale[positive]
)
summary["upper_95_percent"] = (
    chi2.ppf(0.975, 2 * (flags + 1)) / 2 * scale
)

# Save the refreshed comparison
summary.to_csv(folder / "hdd_comparison.csv")

print("\nHDD models included:", len(summary))

print(summary.sort_values("afr_percent", ascending=False).round(3).to_string())
