import pandas as pd

# Set folders
from config import folder, raw_folder
saved = folder / "toshiba_location_records.csv"

daily = pd.read_csv(folder / "daily_model_summary.csv", parse_dates=["date"])
# Read saved monthly results
monthly = pd.read_csv(folder / "monthly_model_summary.csv")

# Select three models for investigation
selected_models = [
    "TOSHIBA MG08ACA16TEY",
    "ST10000NM0086",
    "ST14000NM0138"
]

patterns = monthly[
    monthly["model"].isin(selected_models)
].copy()

# Calculate monthly annualised rates
patterns["afr_percent"] = (
    patterns["failure_flag_rows"] * 365
    / patterns["drive_days"] * 100
)

# Show each model's monthly pattern
columns = [
    "month", "failure_flag_rows", "drive_days",
    "observed_days", "afr_percent"
]

for model in selected_models:
    print(f"\nMONTHLY FAILURE PATTERN: {model}")
    print(
        patterns.loc[patterns["model"] == model, columns]
        .sort_values("month")
        .round(3)
        .to_string(index=False)
    )

# Save monthly patterns
patterns.to_csv(folder / "monthly_failure_patterns.csv", index=False)

# Read saved daily results
daily = pd.read_csv(
    folder / "daily_model_summary.csv",
    parse_dates=["date"]
)

# Select the Toshiba model
toshiba = daily[
    daily["model"] == "TOSHIBA MG08ACA16TEY"
].copy()

# Find dates with the most failure flags
top_dates = toshiba.sort_values(
    "failure_flag_rows", ascending=False
).head(15)

# Show failure counts and exposure
print("\nTOSHIBA — DATES WITH MOST FAILURE FLAGS:")
print(top_dates[
    ["date", "failure_flag_rows", "observed_drives", "drive_days"]
].to_string(index=False))

# Save daily results
toshiba.to_csv(folder / "toshiba_daily_pattern.csv", index=False)

# Select July to October
period = toshiba[
    toshiba["date"].between("2025-07-01", "2025-10-31")
]

# Measure how spread out the flags were
total_flags = period["failure_flag_rows"].sum()
flagged_days = (period["failure_flag_rows"] > 0).sum()
top_five_flags = period["failure_flag_rows"].nlargest(5).sum()

# Show concentration results
print("\nTOSHIBA — JULY TO OCTOBER:")
print("Observed days:", period["date"].nunique())
print("Days with failure flags:", flagged_days)
print("Total failure flags:", total_flags)
print("Flags on the five highest-count days:", top_five_flags)
print("Share on those five days:",
      round(top_five_flags / total_flags * 100, 1), "%")


# Read saved records if available
if saved.exists():
    data = pd.read_csv(saved, parse_dates=["date"])

else:
    # Read included files
    inventory = pd.read_csv(folder / "file_inventory.csv")
    files = inventory.loc[inventory["status"] == "included", "file"]
    rows = []

    columns = [
        "date", "serial_number", "model", "failure",
        "cluster_id", "vault_id", "pod_id"
    ]

    # Collect Toshiba records
    for number, name in enumerate(files, 1):
        print(f"Reading {number}/{len(files)}: {name}", flush=True)

        part = pd.read_csv(
            raw_folder / name,
            usecols=columns,
            dtype={
                "serial_number": "string",
                "model": "string",
                "cluster_id": "string",
                "vault_id": "string",
                "pod_id": "string"
            }
        )

        part["model"] = part["model"].str.strip()
        part = part[part["model"] == "TOSHIBA MG08ACA16TEY"]
        rows.append(part)

    # Clean and save selected records
    data = pd.concat(rows, ignore_index=True)
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["serial_number"] = (
        data["serial_number"].str.strip().replace("", pd.NA)
    )
    data["failure"] = pd.to_numeric(data["failure"], errors="coerce")

    data = data[
        data["date"].notna()
        & data["serial_number"].notna()
        & data["failure"].isin([0, 1])
    ].copy()

    data.to_csv(saved, index=False)

# Select the elevated period
period = data[
    data["date"].between("2025-07-01", "2025-10-31")
].copy()

# Keep missing location labels visible
locations = ["cluster_id", "vault_id", "pod_id"]

for column in locations:
    period[column] = (
        period[column].astype("string").str.strip()
        .replace("", pd.NA).fillna("Unknown")
    )

# Summarise each storage group
result = period.groupby(locations, dropna=False).agg(
    drive_days=("serial_number", "size"),
    failure_flags=("failure", "sum"),
    observed_days=("date", "nunique")
).reset_index()

# Calculate rates using each group's exposure
result["afr_percent"] = (
    result["failure_flags"] * 365 / result["drive_days"] * 100
)

# Show locations with the most flags
result = result.sort_values("failure_flags", ascending=False)

print("\nTOSHIBA LOCATIONS — JULY TO OCTOBER:")
print(result.head(20).round(3).to_string(index=False))

print("\nTotal drive-days:", result["drive_days"].sum())
print("Total failure flags:", result["failure_flags"].sum())
print("Expected failure flags from monthly analysis: 261")

# Save all location results
result.to_csv(folder / "toshiba_location_summary.csv", index=False)
# Compare clusters and vaults
for groups in [["cluster_id"], ["cluster_id", "vault_id"]]:
    table = result.groupby(groups, dropna=False)[
        ["drive_days", "failure_flags"]
    ].sum()

    # Compare each group's share of exposure and flags
    table["exposure_share_percent"] = (
        table["drive_days"] / table["drive_days"].sum() * 100
    )
    table["flag_share_percent"] = (
        table["failure_flags"] / table["failure_flags"].sum() * 100
    )
    table["afr_percent"] = (
        table["failure_flags"] * 365 / table["drive_days"] * 100
    )

    table = table.sort_values("failure_flags", ascending=False)

    print("\nTOSHIBA —", " AND ".join(groups).upper())
    print(table.round(3).to_string())

    # Save each location comparison
    name = "_".join(groups)
    table.to_csv(folder / f"toshiba_{name}_summary.csv")

# Read saved Toshiba records
records = pd.read_csv(
    folder / "toshiba_location_records.csv",
    parse_dates=["date"],
    dtype={"cluster_id": "string", "vault_id": "string"}
)

# Select cluster 31 and four vaults
cluster = pd.to_numeric(records["cluster_id"], errors="coerce")
vault = pd.to_numeric(records["vault_id"], errors="coerce")

selected = records[
    (cluster == 31) & vault.isin([2009, 2007, 2005, 2016])
].copy()

# Group records by month and vault
selected["month"] = selected["date"].dt.strftime("%Y-%m")

monthly_vaults = selected.groupby(
    ["vault_id", "month"]
).agg(
    drive_days=("serial_number", "size"),
    failure_flags=("failure", "sum"),
    observed_days=("date", "nunique")
).reset_index()

# Calculate exposure-adjusted rates
monthly_vaults["afr_percent"] = (
    monthly_vaults["failure_flags"] * 365
    / monthly_vaults["drive_days"] * 100
)

# Show monthly results for each vault
for vault_id, table in monthly_vaults.groupby("vault_id"):
    print(f"\nTOSHIBA — VAULT {vault_id}:")
    print(table.round(3).to_string(index=False))

# Save the comparison
monthly_vaults.to_csv(
    folder / "toshiba_monthly_vaults.csv", index=False
)
import json

# Read saved column names
schemas = json.loads(
    (folder / "column_schemas.json").read_text()
)

# Find operating-hours and firmware fields
fields = sorted({
    column
    for columns in schemas.values()
    for column in columns
    if column.startswith("smart_9_") or "firmware" in column.lower()
})

# Show availability across included files
inventory = pd.read_csv(folder / "file_inventory.csv")
included = inventory.loc[inventory["status"] == "included", "file"]

print("\nOPERATING-HOURS AND FIRMWARE FIELDS:")

for field in fields:
    count = sum(field in schemas.get(name, []) for name in included)
    print(f"{field}: present in {count} included files")
# Refresh snapshots when raw data is available; otherwise keep the saved cohort
if raw_folder.exists():
    # Find the included file for 1 July
    inventory = pd.read_csv(folder / "file_inventory.csv")

    matches = inventory[
        (inventory["status"] == "included")
        & (inventory["dates"] == "2025-07-01")
    ]

    if len(matches) != 1:
        raise SystemExit("Check the inventory entry for 1 July.")

    # Read the starting snapshot
    snapshot = pd.read_csv(
        raw_folder / matches["file"].iloc[0],
        usecols=[
            "model", "serial_number", "cluster_id",
            "vault_id", "smart_9_raw"
        ]
    )

    # Select the same model and comparison vaults
    snapshot["model"] = snapshot["model"].str.strip()

    for column in ["cluster_id", "vault_id", "smart_9_raw"]:
        snapshot[column] = pd.to_numeric(
            snapshot[column], errors="coerce"
        )

    snapshot = snapshot[
        (snapshot["model"] == "TOSHIBA MG08ACA16TEY")
        & (snapshot["cluster_id"] == 31)
        & snapshot["vault_id"].isin([2005, 2007, 2009, 2016])
    ].copy()

    # Keep missing and negative readings out of the summary
    snapshot["smart_9_raw"] = snapshot["smart_9_raw"].where(
        snapshot["smart_9_raw"] >= 0
    )

    # Compare readings at the start of July
    age_check = snapshot.groupby("vault_id").agg(
        drives=("serial_number", "nunique"),
        valid_readings=("smart_9_raw", "count"),
        minimum_raw=("smart_9_raw", "min"),
        median_raw=("smart_9_raw", "median"),
        maximum_raw=("smart_9_raw", "max")
    )

    print("\nSMART 9 RAW — SNAPSHOT ON 1 JULY:")
    print(age_check.to_string())

    # Save the snapshot
    snapshot.to_csv(folder / "toshiba_july_start.csv", index=False)
    # Find the file for 2 July
    matches = inventory[
        (inventory["status"] == "included")
        & (inventory["dates"] == "2025-07-02")
    ]

    if len(matches) != 1:
        raise SystemExit("Check the inventory entry for 2 July.")

    # Read the next day's readings
    next_day = pd.read_csv(
        raw_folder / matches["file"].iloc[0],
        usecols=["serial_number", "model", "smart_9_raw"],
        dtype={"serial_number": "string"}
    )

    # Select the same Toshiba model
    next_day = next_day[
        next_day["model"].str.strip() == "TOSHIBA MG08ACA16TEY"
    ].copy()

    # Match individual drives across both days
    start = pd.read_csv(
        folder / "toshiba_july_start.csv",
        dtype={"serial_number": "string"}
    )

    for table in [start, next_day]:
        table["serial_number"] = table["serial_number"].str.strip()
        table["smart_9_raw"] = pd.to_numeric(
            table["smart_9_raw"], errors="coerce"
        )

    matched = start.merge(
        next_day[["serial_number", "smart_9_raw"]],
        on="serial_number",
        suffixes=("_july1", "_july2"),
        validate="one_to_one"
    )

    # Calculate the change over one day
    matched["daily_change"] = (
        matched["smart_9_raw_july2"] - matched["smart_9_raw_july1"]
    )

    print("\nSMART 9 — CHANGE FROM 1 TO 2 JULY:")
    print("Matched drives:", len(matched))
    print("Missing changes:", matched["daily_change"].isna().sum())
    print(matched["daily_change"].describe().to_string())

    # Save matched readings
    matched.to_csv(folder / "toshiba_smart9_daily_check.csv", index=False)


else:
    for name in ["toshiba_july_start.csv", "toshiba_smart9_daily_check.csv"]:
        if not (folder / name).exists():
            raise SystemExit(f"Missing {name}. Set the raw folder and rerun this script.")
    print("Using saved July snapshots; raw snapshot extraction was not rerun.")
