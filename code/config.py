from pathlib import Path
import os

# Change these folders if the data is stored elsewhere
raw_folder = Path(os.environ.get("BACKBLAZE_RAW", str(Path.home() / "Desktop/Backblaze_Data")))
folder = Path(os.environ.get("BACKBLAZE_OUTPUT", str(Path.home() / "Desktop/Backblaze_Organised_Results")))
folder.mkdir(parents=True, exist_ok=True)
