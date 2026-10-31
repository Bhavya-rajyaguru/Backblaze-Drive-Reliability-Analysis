from pathlib import Path
import json
import zipfile
import pandas as pd

# Set folders
from config import raw_folder as folder, folder as output
output.mkdir(exist_ok=True)

files = sorted(folder.rglob("*.csv"))
cols = ["date", "serial_number", "model", "capacity_bytes", "failure"]

if not files:
    raise SystemExit("No CSV files found.")

daily_data = []
model_data = []
checks = []
schemas = {}
seen_dates = set()

# Read and check each file
for number, file in enumerate(files, 1):
    print(f"Checking {number}/{len(files)}: {file.name}", flush=True)
    name = str(file.relative_to(folder))
    check = {"file": name, "size_bytes": file.stat().st_size}

    try:
        schemas[name] = pd.read_csv(file, nrows=0).columns.tolist()
        check["columns"] = len(schemas[name])

        data = pd.read_csv(
            file, usecols=cols,
            dtype={"serial_number": "string", "model": "string"}
        )

        check["rows"] = len(data)
        check["missing_core_cells"] = int(data.isna().sum().sum())

        # Clean basic fields
        for col in ["serial_number", "model"]:
            data[col] = data[col].str.strip().replace("", pd.NA)

        data["date"] = pd.to_datetime(
            data["date"], errors="coerce"
        ).dt.normalize()

        for col in ["failure", "capacity_bytes"]:
            data[col] = pd.to_numeric(data[col], errors="coerce")

        # Count invalid values and duplicates
        bad_failure = ~data["failure"].isin([0, 1])
        bad_capacity = data["capacity_bytes"].isna() | data["capacity_bytes"].le(0)
        bad_rows = data[cols[:3]].isna().any(axis=1) | bad_failure

        check["invalid_failure_rows"] = int(bad_failure.sum())
        check["invalid_capacity_rows"] = int(bad_capacity.sum())
        check["invalid_reliability_rows"] = int(bad_rows.sum())
        check["duplicate_keys"] = int(
            data.duplicated(["date", "serial_number"]).sum()
        )

        dates = set(data["date"].dropna().dt.strftime("%Y-%m-%d"))
        check["dates"] = ", ".join(sorted(dates))

        if dates & seen_dates:
            raise ValueError("Overlapping dates")
        if check["duplicate_keys"]:
            raise ValueError("Duplicate drive-day records")

        # Summarise valid drive-days
        valid = data.loc[~bad_rows].copy()
        valid["capacity_bytes"] = valid["capacity_bytes"].where(
            valid["capacity_bytes"].gt(0)
        )

        summary = valid.groupby(["date", "model"], as_index=False).agg(
            drive_days=("serial_number", "size"),
            observed_drives=("serial_number", "nunique"),
            failure_flag_rows=("failure", "sum"),
            installed_capacity_bytes=(
                "capacity_bytes", lambda x: x.sum(min_count=1)
            ),
            capacity_records=("capacity_bytes", "count")
        )

        # Collect model and capacity pairs
        pairs = data.loc[
            data["model"].notna() & ~bad_capacity,
            ["model", "capacity_bytes"]
        ].drop_duplicates()

        daily_data.append(summary)
        model_data.append(pairs)
        seen_dates.update(dates)
        check["status"] = "included" if len(valid) else "empty"

    except Exception as error:
        check["status"] = "excluded"
        check["reason"] = str(error)
        print(f"Excluded: {error}", flush=True)

    checks.append(check)

# Save file checks
inventory = pd.DataFrame(checks)
inventory.to_csv(output / "file_inventory.csv", index=False)

if not daily_data:
    raise SystemExit("No files included. Check file_inventory.csv.")

# Save daily totals
daily = pd.concat(daily_data, ignore_index=True)
daily.to_csv(output / "daily_model_summary.csv", index=False)

# Save monthly totals and annualised failure rates
daily["month"] = daily["date"].dt.strftime("%Y-%m")
monthly = daily.groupby(["month", "model"], as_index=False).agg(
    drive_days=("drive_days", "sum"),
    failure_flag_rows=("failure_flag_rows", "sum"),
    observed_days=("date", "nunique")
)
monthly["afr"] = monthly["failure_flag_rows"] * 365 / monthly["drive_days"]
monthly.to_csv(output / "monthly_model_summary.csv", index=False)

# Create df with distinct model and capacity pairs
df = pd.concat(model_data, ignore_index=True).drop_duplicates()
df["capacity_tb"] = df["capacity_bytes"] / 10**12
df = df.sort_values(["capacity_tb", "model"]).reset_index(drop=True)
df.to_csv(output / "model_capacity.csv", index=False)

# Check missing dates
expected = pd.date_range(min(seen_dates), max(seen_dates))
missing = [
    date.strftime("%Y-%m-%d")
    for date in expected
    if date.strftime("%Y-%m-%d") not in seen_dates
]

coverage = {
    "included_dates": sorted(seen_dates),
    "files_found": len(files),
    "excluded_files": int((inventory["status"] == "excluded").sum()),
    "missing_dates_between_first_and_last": missing,
    "notes": [
        "Drive types have not been classified.",
        "Repeated failure flags across dates have not been checked.",
        "AFR is a decimal annualised rate, not a forecast.",
        "Capacity totals apply to individual dates."
    ]
}

# Save coverage and column names
for name, values in [
    ("coverage.json", coverage),
    ("column_schemas.json", schemas)
]:
    (output / name).write_text(json.dumps(values, indent=2))

# Zip the results
names = [
    "file_inventory.csv", "daily_model_summary.csv",
    "monthly_model_summary.csv", "model_capacity.csv",
    "coverage.json", "column_schemas.json"
]
archive = output.parent / f"{output.name}.zip"

with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
    for name in names:
        zipped.write(output / name, name)

# Print model capacities and counts
print("\nModel capacities:")
print(df.to_string(index=False))

print("\nNumber of models at each capacity:")
print(df.groupby("capacity_tb")["model"].nunique().to_string())

print(f"\nTotal models: {df['model'].nunique()}")
print(f"Missing dates: {missing}")
print(f"Results saved at: {archive}")
