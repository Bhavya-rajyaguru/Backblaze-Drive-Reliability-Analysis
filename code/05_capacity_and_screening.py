import pandas as pd

# Set the results folder
from config import folder

# Read saved results
daily = pd.read_csv(
    folder / "daily_model_summary.csv",
    parse_dates=["date"]
)
models = pd.read_csv(folder / "model_classification.csv")
reliability = pd.read_csv(folder / "hdd_comparison.csv")

# Select confirmed HDD models
hdd_models = models.loc[
    models["drive_type"] == "HDD", "model"
].unique()

hdd = daily[daily["model"].isin(hdd_models)].copy()

# Select one common date for capacity comparisons
latest_date = daily["date"].max()
latest = hdd[hdd["date"] == latest_date].copy()

# Calculate installed capacity in decimal TB
latest["installed_capacity_tb"] = (
    latest["installed_capacity_bytes"] / 10**12
)

# Calculate shares of the classified HDD fleet
latest["drive_share_percent"] = (
    latest["observed_drives"]
    / latest["observed_drives"].sum() * 100
)
latest["capacity_share_percent"] = (
    latest["installed_capacity_tb"]
    / latest["installed_capacity_tb"].sum() * 100
)

# Add annual reliability results
columns = [
    "model", "failure_flags", "drive_days", "afr_percent",
    "lower_95_percent", "upper_95_percent"
]

comparison = latest.merge(
    reliability[columns],
    on="model",
    how="left",
    validate="one_to_one"
)

# Show models contributing the most installed capacity
comparison = comparison.sort_values(
    "installed_capacity_tb", ascending=False
)

print("\nCAPACITY SNAPSHOT DATE:", latest_date.date())
print("\nCONFIRMED HDD MODELS — LARGEST INSTALLED CAPACITY:")

show = [
    "model", "observed_drives", "installed_capacity_tb",
    "capacity_share_percent", "failure_flags", "afr_percent"
]

print(comparison[show].head(15).round(3).to_string(index=False))

# Check capacity coverage
print("\nRecords missing valid capacity:",
      int((latest["observed_drives"] - latest["capacity_records"]).sum()))

# Save the combined comparison
comparison.to_csv(folder / "capacity_reliability.csv", index=False)

print("\nSaved: capacity_reliability.csv")

# Read monthly results
monthly = pd.read_csv(folder / "monthly_model_summary.csv")

# Select confirmed HDD models
monthly = monthly[
    monthly["model"].isin(hdd_models)
].copy()

# Calculate monthly annualised rates
monthly["afr_percent"] = (
    monthly["failure_flag_rows"] * 365
    / monthly["drive_days"] * 100
)

# Calculate a pooled HDD rate for each month
totals = monthly.groupby("month")[
    ["failure_flag_rows", "drive_days"]
].sum()

totals["monthly_hdd_afr"] = (
    totals["failure_flag_rows"] * 365
    / totals["drive_days"] * 100
)

# Attach each month's comparison rate
monthly = monthly.merge(
    totals[["monthly_hdd_afr"]],
    on="month",
    validate="many_to_one"
)

# Count months above the pooled rate
monthly["above_monthly_hdd_rate"] = (
    monthly["afr_percent"] > monthly["monthly_hdd_afr"]
)

screen = monthly.groupby("model").agg(
    months_observed=("month", "nunique"),
    months_above_hdd_rate=("above_monthly_hdd_rate", "sum"),
    peak_monthly_afr=("afr_percent", "max"),
    annual_failure_flags=("failure_flag_rows", "sum"),
    annual_drive_days=("drive_days", "sum")
).reset_index()

# Add capacity and annual confidence intervals
extra = reliability[["model", "afr_percent", "lower_95_percent", "upper_95_percent"]].merge(
    latest[["model", "capacity_share_percent"]], on="model", how="left", validate="one_to_one"
)

screen = screen.merge(
    extra, on="model", how="left", validate="one_to_one"
)

# Sort recurring patterns for inspection
screen = screen.sort_values(
    ["months_above_hdd_rate", "annual_failure_flags"],
    ascending=False
)

# Show the screening results
print("\nHDD SCREENING — RECURRING ABOVE-FLEET RATES:")
print(screen.head(20).round(3).to_string(index=False))

# Save all model and monthly results
screen.to_csv(folder / "hdd_model_screening.csv", index=False)
monthly.to_csv(folder / "hdd_monthly_screening.csv", index=False)
# Read model capacities
capacities = pd.read_csv(folder / "model_classification.csv")
capacities = capacities[
    capacities["drive_type"] == "HDD"
][["model", "capacity_bytes"]].drop_duplicates()

# Check that each model has one recorded capacity
if capacities["model"].duplicated().any():
    raise SystemExit("Check models with multiple capacities.")

# Read annual reliability results
rates = pd.read_csv(folder / "hdd_comparison.csv")

# Attach each model's capacity
peers = rates.merge(
    capacities, on="model", validate="one_to_one"
)

# Calculate the pooled rate for each capacity
groups = peers.groupby("capacity_bytes")[
    ["failure_flags", "drive_days"]
].sum()

groups["capacity_group_afr"] = (
    groups["failure_flags"] * 365 / groups["drive_days"] * 100
)

# Add capacity-group rates
peers = peers.merge(
    groups[["capacity_group_afr"]],
    on="capacity_bytes",
    validate="many_to_one"
)

peers["capacity_tb"] = peers["capacity_bytes"] / 10**12

# Show peers of five investigation candidates
candidates = [
    "ST12000NM0008",
    "HGST HUH721212ALN604",
    "HGST HUH721212ALE604",
    "ST8000NM0055",
    "TOSHIBA MG08ACA16TEY"
]

selected_capacities = peers.loc[
    peers["model"].isin(candidates), "capacity_bytes"
]

selected = peers[
    peers["capacity_bytes"].isin(selected_capacities)
].sort_values(["capacity_bytes", "afr_percent"], ascending=[True, False])

# Print the comparison
columns = [
    "model", "capacity_tb", "failure_flags", "drive_days",
    "afr_percent", "capacity_group_afr"
]

print("\nHDD COMPARISON — SAME CAPACITY:")
print(selected[columns].round(3).to_string(index=False))

# Save all capacity comparisons
peers.to_csv(folder / "hdd_capacity_peers.csv", index=False)
# Read saved screening and peer comparisons
screen = pd.read_csv(folder / "hdd_model_screening.csv")
peers = pd.read_csv(folder / "hdd_capacity_peers.csv")

# Select models for the first review
review_models = [
    "TOSHIBA MG08ACA16TEY",
    "HGST HUH721212ALN604",
    "ST12000NM0008",
    "HGST HUH721212ALE604",
    "ST8000NM0055"
]

# Combine recurring patterns and capacity comparisons
review = screen[screen["model"].isin(review_models)].merge(
    peers[["model", "capacity_tb", "capacity_group_afr"]],
    on="model",
    validate="one_to_one"
)

# Measure the difference from capacity peers
review["rate_ratio_to_capacity_group"] = (
    review["afr_percent"] / review["capacity_group_afr"]
)

# Record the reason for investigating each model
reasons = {
    "TOSHIBA MG08ACA16TEY":
        "High peer-relative rate; July–October surge; vault differences",
    "HGST HUH721212ALN604":
        "Above fleet rate in all months; elevated against capacity peers",
    "ST12000NM0008":
        "Recurring pattern; substantial deployment and failure count",
    "HGST HUH721212ALE604":
        "Recurring pattern; meaningful deployment; above peer rate",
    "ST8000NM0055":
        "Recurring fleet-level signal; rate close to capacity peers"
}

review["investigation_reason"] = review["model"].map(reasons)

# Show the evidence together
columns = [
    "model", "annual_failure_flags", "afr_percent",
    "lower_95_percent", "upper_95_percent",
    "months_above_hdd_rate", "capacity_share_percent",
    "rate_ratio_to_capacity_group"
]

print("\nPRELIMINARY INVESTIGATION SHORTLIST:")
print(review[columns].round(3).to_string(index=False))

# Save the shortlist and reasons
review.to_csv(folder / "investigation_shortlist.csv", index=False)

print("\nSaved: investigation_shortlist.csv")
print("Next checks: drive role, age evidence and comparison coverage.")

# Select daily records for shortlisted models
selected = daily[daily["model"].isin(review_models)].copy()

# Summarise observation coverage
coverage = selected.groupby("model").agg(
    first_seen=("date", "min"),
    last_seen=("date", "max"),
    observed_days=("date", "nunique"),
    minimum_daily_drives=("observed_drives", "min"),
    maximum_daily_drives=("observed_drives", "max")
)

# Compare fleet size on the first and last observed dates
ordered = selected.sort_values("date")

coverage["first_day_drives"] = (
    ordered.groupby("model")["observed_drives"].first()
)
coverage["last_day_drives"] = (
    ordered.groupby("model")["observed_drives"].last()
)

# Count dates without model records inside its observed span
coverage["calendar_span_days"] = (
    coverage["last_seen"] - coverage["first_seen"]
).dt.days + 1

coverage["dates_without_records"] = (
    coverage["calendar_span_days"] - coverage["observed_days"]
)

# Show and save coverage checks
print("\nSHORTLIST — COVERAGE AND DEPLOYMENT:")
print(coverage.to_string())

coverage.to_csv(folder / "shortlist_coverage.csv")

# Find the lowest-count date for each model
lowest = selected.loc[
    selected.groupby("model")["observed_drives"].idxmin()
]

print("\nLOWEST DAILY DRIVE COUNTS:")
print(lowest[
    ["model", "date", "observed_drives", "failure_flag_rows"]
].to_string(index=False))

# Check records around each minimum
for _, row in lowest.iterrows():
    nearby = selected[
        (selected["model"] == row["model"])
        & selected["date"].between(
            row["date"] - pd.Timedelta(days=2),
            row["date"] + pd.Timedelta(days=2)
        )
    ]

    print(f"\nRECORDS AROUND THE MINIMUM: {row['model']}")
    print(nearby[
        ["date", "observed_drives", "failure_flag_rows"]
    ].sort_values("date").to_string(index=False))

# Show missing dates for each shortlisted model
expected = pd.date_range(daily["date"].min(), daily["date"].max())

print("\nDATES WITHOUT MODEL RECORDS:")

for model in review_models:
    recorded = selected.loc[selected["model"] == model, "date"]
    missing = expected.difference(pd.DatetimeIndex(recorded))
    print(model, ":", missing.strftime("%Y-%m-%d").tolist())


# Compare results with and without 12 May
checks = []

for label, records in [
    ("All observed dates", selected),
    ("Without 12 May", selected[
        selected["date"] != pd.Timestamp("2025-05-12")
    ])
]:
    totals = records.groupby("model").agg(
        failure_flags=("failure_flag_rows", "sum"),
        drive_days=("drive_days", "sum")
    )

    totals[label] = (
        totals["failure_flags"] * 365
        / totals["drive_days"] * 100
    )

    checks.append(totals[[label]])

# Measure the change in percentage points
sensitivity = pd.concat(checks, axis=1)

sensitivity["change_percentage_points"] = (
    sensitivity["Without 12 May"]
    - sensitivity["All observed dates"]
)

print("\nAFR SENSITIVITY — EXCLUDING 12 MAY:")
print(sensitivity.round(4).to_string())

# Save both estimates
sensitivity.to_csv(folder / "may12_sensitivity.csv")
# Read the saved shortlist
shortlist = pd.read_csv(folder / "investigation_shortlist.csv")

# Record the purpose of each investigation
interpretation = {
    "TOSHIBA MG08ACA16TEY":
        "Operational-event case study: Backblaze linked the Q3 spike to firmware work.",
    "HGST HUH721212ALN604":
        "Investigate recurring elevated rates against capacity peers.",
    "ST12000NM0008":
        "Investigate recurring rates and substantial deployment.",
    "HGST HUH721212ALE604":
        "Investigate recurring rates and meaningful deployment.",
    "ST8000NM0055":
        "Monitor: annual rate is close to its capacity-group reference."
}

shortlist["interpretation"] = shortlist["model"].map(interpretation)

# Record the source for the Toshiba explanation
shortlist["context_source"] = ""
shortlist.loc[
    shortlist["model"] == "TOSHIBA MG08ACA16TEY",
    "context_source"
] = "https://www.backblaze.com/blog/backblaze-drive-stats-for-q3-2025/"

# Save updated interpretations
shortlist.to_csv(folder / "investigation_shortlist.csv", index=False)

print("\nUPDATED SHORTLIST INTERPRETATIONS:")
print(shortlist[["model", "interpretation"]].to_string(index=False))
# Read current classifications
labels = pd.read_csv(folder / "model_classification.csv")
labels = labels[["model", "drive_type"]].drop_duplicates()

# Attach labels to daily records
scope = daily.merge(
    labels, on="model", how="left", validate="many_to_one"
)
scope["drive_type"] = scope["drive_type"].fillna("Unknown")

# Summarise exposure and flags by classification
scope_summary = scope.groupby("drive_type").agg(
    models=("model", "nunique"),
    drive_days=("drive_days", "sum"),
    failure_flags=("failure_flag_rows", "sum")
)

scope_summary["exposure_share_percent"] = (
    scope_summary["drive_days"]
    / scope_summary["drive_days"].sum() * 100
)

print("\nANALYSIS SCOPE — ALL CLASSIFICATIONS:")
print(scope_summary.round(3).to_string())

# Show the contribution of unclassified models
unknown_summary = scope[
    scope["drive_type"] == "Unknown"
].groupby("model").agg(
    drive_days=("drive_days", "sum"),
    failure_flags=("failure_flag_rows", "sum")
).sort_values("drive_days", ascending=False)

print("\nUNCLASSIFIED MODELS — EXPOSURE AND FLAGS:")
print(unknown_summary.to_string())

# Save scope checks
scope_summary.to_csv(folder / "analysis_scope.csv")
unknown_summary.to_csv(folder / "unclassified_model_summary.csv")



























# Read saved results
screen = pd.read_csv(folder / "hdd_model_screening.csv")
peers = pd.read_csv(folder / "hdd_capacity_peers.csv")

# Remove annual values from the snapshot-based merge
annual_columns = [
    "afr_percent", "lower_95_percent", "upper_95_percent"
]

screen = screen.drop(columns=annual_columns, errors="ignore")

# Attach annual values from the full peer table
review = screen.merge(
    peers[
        ["model", "capacity_tb", "capacity_group_afr"]
        + annual_columns
    ],
    on="model",
    how="left",
    validate="one_to_one"
)

# Check missing comparison values
required = annual_columns + ["capacity_group_afr"]
missing = review[required].isna().any(axis=1)

if missing.any():
    print("\nMODELS WITH MISSING VALUES:")
    print(review.loc[
        missing, ["model"] + required
    ].to_string(index=False))

    raise SystemExit("Check the missing values shown above.")

# Compare annual rates with capacity peers
review["peer_rate_ratio"] = (
    review["afr_percent"]
    / review["capacity_group_afr"].replace(0, float("nan"))
)

# Mark recurring above-fleet patterns
review["recurring_signal"] = (
    review["months_observed"].eq(12)
    & review["months_above_hdd_rate"].ge(9)
)

review["above_capacity_rate"] = (
    review["afr_percent"] > review["capacity_group_afr"]
)

# Record the Toshiba explanation
review["context"] = "Cause not established"

review.loc[
    review["model"] == "TOSHIBA MG08ACA16TEY", "context"
] = "Backblaze linked the Q3 spike to firmware work"

# Select models meeting both screening conditions
candidates = review[
    review["recurring_signal"] & review["above_capacity_rate"]
].sort_values("peer_rate_ratio", ascending=False)

# Show candidate results
columns = [
    "model", "annual_failure_flags", "afr_percent",
    "months_above_hdd_rate", "peer_rate_ratio",
    "capacity_share_percent"
]

print("\nMODELS FOR FURTHER REVIEW:")
print(candidates[columns].round(3).to_string(index=False))

# Save all models and screening candidates
review.to_csv(folder / "all_model_review.csv", index=False)
candidates.to_csv(folder / "review_candidates.csv", index=False)

print("\nReview tables saved.")
# Check sensitivity to the recurrence threshold
print("\nSCREENING THRESHOLD CHECK:")

for months in [8, 9, 10, 11, 12]:
    selected = review[
        review["months_observed"].eq(12)
        & review["months_above_hdd_rate"].ge(months)
        & review["above_capacity_rate"]
    ]

    print(f"\nAt least {months} above-fleet months: {len(selected)} models")
    print(", ".join(selected["model"]))


# Record interpretation limits
review["drive_role_status"] = "Not yet verified for every model"
review["age_adjustment"] = "Rates are not adjusted for operating age"
review["workload_status"] = "Actual read/write workload not established"

# Describe the screening outcome
review["review_status"] = "Does not meet the current screening rule"

review.loc[
    review["recurring_signal"] & review["above_capacity_rate"],
    "review_status"
] = "Investigate recurring rate pattern"

# Preserve the known operational explanation
review.loc[
    review["model"] == "TOSHIBA MG08ACA16TEY",
    "review_status"
] = "Operational-event case study"

# Save the full review with limitations
review.to_csv(folder / "all_model_review.csv", index=False)

print("\nMODEL REVIEW SAVED WITH EVIDENCE LIMITS.")

# Refresh candidates with context and evidence limits
candidates = review[
    review["recurring_signal"] & review["above_capacity_rate"]
].copy()

# Save complete review tables
review.to_csv(folder / "all_model_review.csv", index=False)
candidates.to_csv(folder / "review_candidates.csv", index=False)

# Read verified candidates
actions = pd.read_csv(folder / "review_candidates.csv")

# Record the next investigation for each model
next_steps = {
    "HGST HUH721212ALN604":
        "Review recurring flags, drive ages and replacement records.",
    "ST12000NM0008":
        "Review recurring flags alongside its substantial deployment.",
    "ST14000NM0138":
        "Investigate the large difference from capacity peers.",
    "ST12000NM0007":
        "Investigate recurring elevated rates and drive-age differences.",
    "HGST HUH721212ALE604":
        "Review recurring flags and compare operating conditions.",
    "ST24000NM002H":
        "Check deployment growth and monthly patterns together.",
    "WDC WUH721816ALE6L0":
        "Compare age and operating conditions with other 16 TB models.",
    "TOSHIBA MG07ACA14TEY":
        "Review uncertainty and age before escalating.",
    "ST8000NM0055":
        "Monitor trends; annual rate is close to capacity peers.",
    "ST10000NM0086":
        "Review the high absolute rate across the 10 TB comparison group.",
    "TOSHIBA MG08ACA16TEY":
        "Review firmware-maintenance context; do not infer mechanical failure."
}

# Attach actions without changing numerical results
actions["next_investigation"] = actions["model"].map(next_steps)

# Check that every candidate has an action
if actions["next_investigation"].isna().any():
    raise SystemExit("Add an investigation action for the unmatched models.")

# Save the action table
actions.to_csv(folder / "model_investigation_actions.csv", index=False)

print("\nMODEL INVESTIGATION ACTIONS:")
print(actions[
    ["model", "next_investigation"]
].to_string(index=False))
