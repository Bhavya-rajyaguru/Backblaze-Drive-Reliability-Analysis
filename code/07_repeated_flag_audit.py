import pandas as pd
from config import folder, raw_folder

# Collect failure records when no saved extract exists
saved = folder / "failure_records.csv"
if not saved.exists():
    inventory = pd.read_csv(folder / "file_inventory.csv")
    rows = []
    for name in inventory.loc[inventory["status"] == "included", "file"]:
        print("Reading failure flags:", name, flush=True)
        part = pd.read_csv(raw_folder / name, usecols=["date", "serial_number", "failure"], dtype={"serial_number": "string"})
        rows.append(part[part["failure"] == 1])
    pd.concat(rows, ignore_index=True).to_csv(saved, index=False)

failures = pd.read_csv(saved, dtype={"serial_number": "string"})
failures["serial_number"] = failures["serial_number"].str.strip().replace("", pd.NA)
if failures["serial_number"].isna().any():
    raise SystemExit("Missing failure serial numbers need review.")
counts = failures.groupby("serial_number").size()
serials = counts[counts > 1].index

# Read each repeated drive's history only once
saved_history = folder / "repeated_drive_history.csv"
if not saved_history.exists():
    inventory = pd.read_csv(folder / "file_inventory.csv")
    rows = []
    for name in inventory.loc[inventory["status"] == "included", "file"]:
        print("Checking repeated drives:", name, flush=True)
        part = pd.read_csv(raw_folder / name, usecols=["date", "serial_number", "model", "failure"], dtype={"serial_number": "string", "model": "string"})
        part["serial_number"] = part["serial_number"].str.strip()
        part["model"] = part["model"].str.strip()
        rows.append(part[part["serial_number"].isin(serials)])
    pd.concat(rows, ignore_index=True).to_csv(saved_history, index=False)

history = pd.read_csv(saved_history, parse_dates=["date"], dtype={"serial_number": "string", "model": "string"})
if history.groupby("serial_number")["model"].nunique().gt(1).any():
    raise SystemExit("A repeated serial has several model labels; review before continuing.")
if set(serials) != set(history["serial_number"].unique()):
    raise SystemExit("Saved history does not match the repeated serials. Refresh the extracts.")

# Check records between each pair of failure dates
results = []

for serial, data in history.groupby("serial_number"):
    dates = data.loc[data["failure"] == 1, "date"].sort_values()
    first = dates.iloc[0]
    second = dates.iloc[-1]

    between = data[
        (data["date"] > first) & (data["date"] < second)
    ]

    results.append({
        "serial": serial,
        "model": data["model"].iloc[0],
        "gap_days": (second - first).days,
        "records_between": len(between),
        "zero_flags_between": (between["failure"] == 0).sum()
    })

# Show and save the findings
result = pd.DataFrame(results)

print("\nDrive records between repeated failure flags:")
print(result.to_string(index=False))

result.to_csv(folder / "repeated_history_checks.csv", index=False)

# Load saved failure records and daily totals
failures = pd.read_csv(
    folder / "failure_records.csv",
    dtype={"serial_number": "string"}
)
daily = pd.read_csv(folder / "daily_model_summary.csv")

# Check missing or blank serial numbers
failures["serial_number"] = (
    failures["serial_number"].str.strip().replace("", pd.NA)
)

print("\nMissing failure serial numbers:",
      failures["serial_number"].isna().sum())

if failures["serial_number"].isna().any():
    raise SystemExit("Review missing serial numbers before comparing counts.")

# Count all flags for each model
comparison = daily.groupby("model").agg(
    all_flags=("failure_flag_rows", "sum"),
    drive_days=("drive_days", "sum")
)

# Map repeated serials to models; only extra flags need model labels
failure_models = history[["serial_number", "model"]].drop_duplicates()
failures = failures.merge(
    failure_models, on="serial_number", how="left"
)

# Identify the repeated flags belonging to each model
extra_flags = failures[
    failures.duplicated("serial_number")
].groupby("model").size()

comparison["extra_flags"] = extra_flags.reindex(
    comparison.index, fill_value=0
)
comparison["unique_serials_flagged"] = (
    comparison["all_flags"] - comparison["extra_flags"]
)

# Compare annualised rates using the same drive-days
comparison["all_flags_afr_percent"] = (
    comparison["all_flags"] * 365 / comparison["drive_days"] * 100
)
comparison["unique_serial_rate_percent"] = (
    comparison["unique_serials_flagged"] * 365
    / comparison["drive_days"] * 100
)

comparison["difference_percentage_points"] = (
    comparison["all_flags_afr_percent"]
    - comparison["unique_serial_rate_percent"]
)

# Show models affected by repeated flags
affected = comparison[comparison["extra_flags"] > 0]

print("\nSENSITIVITY CHECK — MODELS WITH REPEATED FLAGS")
print(affected.round(4).to_string())

print("\nAll failure flags:", comparison["all_flags"].sum())
print("Unique serials flagged:", failures["serial_number"].nunique())

comparison.to_csv(folder / "failure_count_sensitivity.csv")
# Rank rates under both counting methods
comparison["flag_rank"] = comparison[
    "all_flags_afr_percent"
].rank(ascending=False, method="min")

comparison["unique_rank"] = comparison[
    "unique_serial_rate_percent"
].rank(ascending=False, method="min")

# Show models whose rank changes
changed = comparison[
    comparison["flag_rank"] != comparison["unique_rank"]
]

print("\nRANK CHANGES UNDER THE TWO COUNTING METHODS")
print(changed[
    ["all_flags_afr_percent", "unique_serial_rate_percent",
     "flag_rank", "unique_rank"]
].round(3).to_string())

print("\nNumber of models with changed ranks:", len(changed))


if comparison["all_flags"].sum() != len(failures):
    raise SystemExit("Saved failure records and daily totals disagree. Refresh the extracts.")
print("This is a numerator sensitivity check, not a first-failure survival estimate.")
