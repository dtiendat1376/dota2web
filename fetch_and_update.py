import os
import subprocess
import kagglehub
from kagglehub import KaggleDatasetAdapter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET = "ektarr/dota-2-pro-matches"
DATA_DIR = os.path.join(BASE_DIR, "data")

FILES = [
    "players.csv",
    "teams.csv",
    "tournaments.csv",
    "all_tiers_games.csv",
    "tier1_games.csv",
    "tier2_games.csv",
    "tier3_games.csv"
]

def fetch_latest_dataset():
    os.makedirs(DATA_DIR, exist_ok=True)
    for filename in FILES:
        print(f"Downloading {filename}...")
        df = kagglehub.dataset_load(KaggleDatasetAdapter.PANDAS, DATASET, filename)
        path = os.path.join(DATA_DIR, filename)
        df.to_csv(path, index=False)
        print(f"Saved {filename} to {path}")
        
    print("All files downloaded and saved successfully.")
    
def run_pipeline():
    scripts_dir = os.path.join(BASE_DIR, "backend", "scripts")

    print("\nRunning data_cleaner.py...")
    subprocess.run(["python", os.path.join(scripts_dir, "data_cleaner.py")], check=True)

    print("\nRunning detect_rebrands.py...")
    subprocess.run(["python", os.path.join(scripts_dir, "detect_rebrands.py")], check=True)

    print("\nRunning load_db.py...")
    subprocess.run(["python", os.path.join(scripts_dir, "load_db.py")], check=True)

    print("\nRunning add_indexes.py...")
    subprocess.run(["python", "-m", "backend.scripts.add_indexes"], check=True)

    print("\nPipeline completed successfully.")
    
if __name__ == "__main__":
    fetch_latest_dataset()
    run_pipeline()
    
