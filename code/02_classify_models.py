import pandas as pd
from config import folder

# Read model capacities
models = pd.read_csv(folder / "model_capacity.csv")
if models["model"].duplicated().any():
    raise SystemExit("Check models with multiple capacities before classifying.")

# Keep the model labels established during the analysis
drive_types = {
    'CT250MX500SSD1': 'SSD',
    'HGST HMS5C4040ALE640': 'HDD',
    'HGST HMS5C4040BLE640': 'HDD',
    'HGST HUH721212ALE600': 'HDD',
    'HGST HUH721212ALE604': 'HDD',
    'HGST HUH721212ALN604': 'HDD',
    'HGST HUH728080ALE600': 'HDD',
    'HGST HUH728080ALE604': 'HDD',
    'HGST HUS726040ALE610': 'HDD',
    'HGST HUS728T8TALE6L4': 'HDD',
    'MTFDDAV240TCB': 'SSD',
    'MTFDDAV480TCB': 'SSD',
    'Micron 5300 MTFDDAK480TDS': 'SSD',
    'SSDSCKKB240GZR': 'SSD',
    'SSDSCKKB480G8R': 'SSD',
    'ST10000NM001G': 'HDD',
    'ST10000NM0086': 'HDD',
    'ST1000LM024 HN': 'HDD',
    'ST12000NM0007': 'HDD',
    'ST12000NM0008': 'HDD',
    'ST12000NM000J': 'HDD',
    'ST12000NM001G': 'HDD',
    'ST12000NM003G': 'HDD',
    'ST12000NM0117': 'HDD',
    'ST14000NM000J': 'HDD',
    'ST14000NM0018': 'HDD',
    'ST14000NM001G': 'HDD',
    'ST14000NM002J': 'HDD',
    'ST14000NM0138': 'HDD',
    'ST16000NM000J': 'HDD',
    'ST16000NM001G': 'HDD',
    'ST16000NM002J': 'HDD',
    'ST18000NM000J': 'HDD',
    'ST24000NM002H': 'HDD',
    'ST4000DM000': 'HDD',
    'ST500LM012 HN': 'HDD',
    'ST500LM021': 'HDD',
    'ST500LM030': 'HDD',
    'ST8000DM002': 'HDD',
    'ST8000DM005': 'HDD',
    'ST8000NM000A': 'HDD',
    'ST8000NM0055': 'HDD',
    'Samsung SSD 850 EVO 1TB': 'SSD',
    'Samsung SSD 850 PRO 1TB': 'SSD',
    'Samsung SSD 860 PRO 2TB': 'SSD',
    'Samsung SSD 870 EVO 2TB': 'SSD',
    'Seagate BarraCuda 120 SSD ZA250CM10003': 'SSD',
    'Seagate BarraCuda 120 SSD ZA500CM10003': 'SSD',
    'Seagate BarraCuda SSD ZA2000CM10002': 'SSD',
    'Seagate BarraCuda SSD ZA250CM10002': 'SSD',
    'Seagate BarraCuda SSD ZA500CM10002': 'SSD',
    'Seagate FireCuda 120 SSD ZA500GM10001': 'SSD',
    'Seagate IronWolf ZA250NM10002': 'SSD',
    'TOSHIBA MG07ACA14TA': 'HDD',
    'TOSHIBA MG07ACA14TEY': 'HDD',
    'TOSHIBA MG08ACA16TA': 'HDD',
    'TOSHIBA MG08ACA16TE': 'HDD',
    'TOSHIBA MG08ACA16TEY': 'HDD',
    'TOSHIBA MG09ACA16TE': 'HDD',
    'TOSHIBA MG10ACA20TE': 'HDD',
    'TOSHIBA MG11ACA24TE': 'HDD',
    'TOSHIBA MQ01ABF050': 'HDD',
    'WD Blue SA510 2.5 250GB': 'SSD',
    'WDC WDS250G2B0A': 'SSD',
    'WDC WUH721414ALE6L4': 'HDD',
    'WDC WUH721816ALE6L0': 'HDD',
    'WDC WUH721816ALE6L4': 'HDD',
    'WDC WUH722222ALE6L4': 'HDD',
    'WDC WUH722626ALE6L4': 'HDD',
    'WUH721816ALE6L4': 'HDD',
}

models["drive_type"] = models["model"].map(drive_types).fillna("Unknown")
models.to_csv(folder / "model_classification.csv", index=False)
print(models.groupby("drive_type")["model"].nunique().to_string())
print("\nModels still needing verification:")
print(models.loc[models["drive_type"] == "Unknown", ["model", "capacity_tb"]].to_string(index=False))
