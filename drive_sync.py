"""
Handles all Google Drive file operations via the local Drive desktop app folder.
No API credentials needed — just write files to the synced folder.
"""

import json
import shutil
import time
from pathlib import Path


def find_drive_root() -> Path:
    """Find the Google Drive My Drive folder on this Mac."""
    home = Path.home()

    # New Drive for Desktop (macOS 12+)
    cloud = home / "Library" / "CloudStorage"
    if cloud.exists():
        for entry in cloud.iterdir():
            if entry.name.startswith("GoogleDrive-"):
                candidate = entry / "My Drive"
                if candidate.exists():
                    return candidate

    # Legacy Google Drive app
    legacy = home / "Google Drive" / "My Drive"
    if legacy.exists():
        return legacy

    legacy2 = home / "Google Drive"
    if legacy2.exists():
        return legacy2

    raise RuntimeError(
        "Could not find Google Drive folder.\n"
        "Make sure Google Drive for Desktop is installed and signed in.\n"
        "Download: https://www.google.com/drive/download/"
    )


class DriveSync:
    def __init__(self, subfolder: str = "f1-opt"):
        root = find_drive_root()
        self.base = root / subfolder
        self.queue = self.base / "queue"
        self.results = self.base / "results"
        self.best = self.base / "best"
        self.history_file = self.base / "history.jsonl"

        for d in (self.queue, self.results, self.best):
            d.mkdir(parents=True, exist_ok=True)

        print(f"Drive sync active at: {self.base}")

    def submit_job(self, mesh_path: Path, params: dict, job_id: str) -> str:
        """Copy mesh + write job descriptor to the queue folder."""
        dest_mesh = self.queue / f"{job_id}.stl"
        shutil.copy2(mesh_path, dest_mesh)

        job_desc = {"job_id": job_id, "params": params, "mesh_file": f"{job_id}.stl"}
        (self.queue / f"{job_id}.json").write_text(json.dumps(job_desc, indent=2))
        return job_id

    def wait_for_result(self, job_id: str, timeout: int = 1200) -> dict | None:
        """Poll for a result file written by a CFD worker notebook."""
        result_file = self.results / f"{job_id}.json"
        deadline = time.time() + timeout
        while time.time() < deadline:
            if result_file.exists():
                try:
                    data = json.loads(result_file.read_text())
                    # Clean up queue files once result is in
                    (self.queue / f"{job_id}.json").unlink(missing_ok=True)
                    (self.queue / f"{job_id}.stl").unlink(missing_ok=True)
                    return data
                except json.JSONDecodeError:
                    pass  # file still being written, wait
            time.sleep(15)
        return None

    def save_best(self, mesh_path: Path, params: dict, results: dict) -> None:
        shutil.copy2(mesh_path, self.best / "best_design.stl")
        (self.best / "best_params.json").write_text(
            json.dumps({"params": params, "results": results}, indent=2)
        )

    def save_history(self, history: list) -> None:
        with self.history_file.open("w") as f:
            for entry in history:
                f.write(json.dumps(entry) + "\n")
