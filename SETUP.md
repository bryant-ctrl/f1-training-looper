# Setup Guide — F1 Aero Optimization Framework

This guide walks you through every step to get the full system running.
It assumes you are a beginner with all tools. Follow the phases in order —
each one is a checkpoint you should verify before moving on.

Estimated total setup time: **2–3 hours** (most of that is downloading things).

---

## What you need before starting

- Mac Mini M4 with 16 GB RAM
- A Google account (for Drive + Colab)
- A Kaggle account — sign up free at https://www.kaggle.com
- Your F1 2026 technical regulations PDF
- A base F1 2026 car model (instructions to get one in Phase 4)

---

## Phase 1 — Mac: Core Tools

### 1.1 Install Homebrew

Homebrew is the standard package manager for Mac. Open **Terminal**
(press Cmd+Space, type "Terminal", press Enter) and paste:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Follow the prompts. It may ask for your Mac password. After it finishes,
it will print two commands starting with `echo` and `eval` — run those too
(they add Homebrew to your PATH). Then close and reopen Terminal.

Verify: `brew --version` should print a version number.

---

### 1.2 Install uv (Python manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Close and reopen Terminal, then verify:

```bash
uv --version
```

You should see something like `uv 0.4.x`. uv manages Python and project
dependencies — you won't need to install Python separately.

---

### 1.3 Install Ollama

Ollama runs AI models locally on your Mac.

1. Go to https://ollama.com
2. Click **Download** → download the Mac `.dmg` file
3. Open the `.dmg` and drag Ollama to your Applications folder
4. Open Ollama from Applications — a small icon appears in your menu bar

Then in Terminal, download the model:

```bash
# Multimodal model — handles both design proposals and visual checks (~4 GB)
ollama pull llava:7b
```

Verify it installed:
```bash
ollama list
```

You should see `llava:7b` in the list.

**Troubleshooting:** If `ollama` is not found, make sure the Ollama app is
running (check your menu bar for the icon) and restart Terminal.

---

### 1.4 Install Blender

1. Go to https://www.blender.org/download/
2. Download the latest stable release for **macOS (Apple Silicon)**
3. Open the `.dmg` and drag Blender to Applications
4. Open Blender once to confirm it launches — you can close it again

---

### 1.5 Install the blender-mcp addon

The blender-mcp addon lets our Python script talk to Blender.

**Step 1:** Download the addon zip file from:
https://github.com/ahujasid/blender-mcp/releases

Download the file named `blender_mcp.zip` from the latest release.
Do **not** unzip it — Blender needs it as a zip.

**Step 2:** Open Blender.

**Step 3:** Go to **Edit → Preferences** (top menu bar).

**Step 4:** Click **Add-ons** in the left sidebar.

**Step 5:** Click **Install...** (top right of the addons window).

**Step 6:** Navigate to your Downloads folder and select `blender_mcp.zip`.

**Step 7:** After installing, you'll see the addon in the list. Check the
checkbox next to **"Blender MCP"** to enable it.

**Step 8:** Close Preferences. In the main 3D viewport, press **N** to open
the side panel. You should see a **"MCP"** tab on the right side.

**Step 9:** Click **"MCP"** → **"Start MCP Server"**.

You should see: `MCP Server running on port 9876`

Leave Blender open whenever you run the optimizer.

---

### 1.6 Install Google Drive for Desktop

This is what syncs files between your Mac and the Colab/Kaggle notebooks.

1. Go to https://www.google.com/drive/download/
2. Download and install **Google Drive for Desktop**
3. Sign in with your Google account
4. Choose **"Sync My Drive to this Mac"** when prompted
5. Google Drive will create a folder — its location varies by macOS version:
   - **macOS 12+**: `~/Library/CloudStorage/GoogleDrive-youremail@gmail.com/My Drive/`
   - **Older macOS**: `~/Google Drive/My Drive/`

You don't need to do anything else — our code finds this folder automatically.

**Verify:** Open Finder and look for "Google Drive" in the left sidebar.
You should see it listed under Locations.

---

### 1.7 Install rclone (for Kaggle)

rclone lets the Kaggle notebook sync files with your Google Drive.

```bash
brew install rclone
```

Now configure it:

```bash
rclone config
```

This starts an interactive wizard. Follow these steps exactly:

1. Type `n` (new remote) and press Enter
2. Name: type `gdrive` and press Enter
3. Storage type: type `drive` and press Enter (Google Drive)
4. Client ID: press Enter (leave blank)
5. Client Secret: press Enter (leave blank)
6. Scope: type `1` and press Enter (full access)
7. Root folder ID: press Enter (leave blank)
8. Service account: press Enter (leave blank)
9. Edit advanced config: type `n` and press Enter
10. Use auto config: type `y` and press Enter
    → A browser window opens. Sign in and click Allow.
11. Configure as Shared Drive: type `n` and press Enter
12. Review the config and type `y` to confirm
13. Type `q` to quit

Verify it works:
```bash
rclone lsd gdrive:
```

You should see your Google Drive folders listed.

**Copy the config for Kaggle** (you'll need this in Phase 3):
```bash
cat ~/.config/rclone/rclone.conf | pbcopy
```

This copies the config to your clipboard. Keep it there for now.

---

### 1.8 Set up the project

Clone (or navigate to) the project folder and install dependencies:

```bash
cd ~/f1-training-looper    # or wherever you cloned it
uv sync
```

This creates a virtual environment and installs all Python packages.
It takes about 1 minute on first run.

---

## Phase 2 — Get your F1 2026 model

### 2.1 Download from Sketchfab

1. Go to https://sketchfab.com
2. Search for **"F1 2026"** or **"Formula 1 2026 car"**
3. Look for a model with a **Download** button (some are free, some paid)
4. Download format: choose **OBJ** if available, otherwise **FBX**
5. Save it somewhere easy to find (e.g., `~/Downloads/f1_2026.obj`)

**Good search terms if the first doesn't work:**
- "F1 car 2026"
- "Formula 1 car concept"
- "F1 2026 concept livery"

---

### 2.2 Load the model in Blender

1. Open Blender
2. Make sure the MCP server is started (N panel → MCP → Start MCP Server)
3. **File → Import → Wavefront (.obj)** (or FBX if you got that format)
4. Navigate to your downloaded model file and click Import
5. The car should appear in the viewport. Use the scroll wheel to zoom,
   middle-click to rotate the view.

---

### 2.3 Name the key objects

Run the setup helper to name car parts so the optimizer can find them:

```bash
uv run python setup_model.py
```

This connects to Blender and lists all objects in the scene. It will ask
you to match each required name (front_wing, rear_wing, etc.) to the
matching number in the list.

**If you can't tell which object is which:** In Blender, click on an object
in the viewport — it highlights in the list on the right (Outliner panel).
Note the number from the setup script that matches the highlighted name.

After running setup_model.py:
- In Blender: **File → Save As** → save as `f1_2026_named.blend`
- You can reopen this file in future sessions and the names will be preserved

---

## Phase 3 — Google Colab Setup

### 3.1 Create the notebook

1. Go to https://colab.research.google.com
2. Click **File → Upload Notebook**
3. Upload the file `notebooks/colab_worker.ipynb` from this project
4. The notebook opens automatically

### 3.2 Enable GPU

1. Click **Runtime** (top menu) → **Change runtime type**
2. Set **Hardware accelerator** to **T4 GPU**
3. Click **Save**

### 3.3 Run the cells

Run each cell **one at a time** by clicking the play button (▶) on the left.

**Cell 1 — Mount Drive:**
- Click ▶ on Cell 1
- A popup asks for Google Drive permission — click **Connect to Google Drive**
- Sign in if prompted
- You should see: `Mounted at /content/drive`

**Cell 2 — Install OpenFOAM:**
- Click ▶ on Cell 2
- This takes **4–6 minutes**. You'll see lots of output scrolling — this is normal.
- Wait until you see: `OpenFOAM installed.`

**Cell 3 — Setup:**
- Click ▶ — should finish instantly
- Verify the paths printed look correct (ending in `f1-opt/queue`, `f1-opt/results`)

**Cell 4 — Case functions:**
- Click ▶ — should finish with: `Case setup functions ready.`

**Cell 5 — Worker loop:**
- Click ▶
- You'll see: `CFD Worker (colab) started at HH:MM:SS`
- `Watching queue: /content/drive/MyDrive/f1-opt/queue`
- `Waiting for jobs...`

The notebook is now running and waiting. **Do not click stop.**

### 3.4 Activate the keep-alive script

This prevents Colab from disconnecting while you leave it running.

1. Press **F12** on your keyboard (opens browser developer tools)
   - On Mac: **Cmd + Option + J** opens the console directly
2. Click the **Console** tab at the top of the DevTools panel
3. Open the file `notebooks/colab_keepalive.js` from this project
4. Copy the **entire contents** of that file
5. Paste it into the console and press **Enter**
6. You should see: `[keep-alive] Started. Runs every 30s.`
7. You can close the DevTools panel (press F12 again) — the script keeps running

**Every 5 minutes** you'll see a tick message in the console confirming
it's still active.

**Important:**
- Keep the Colab browser tab open (don't close it)
- Keep your Mac awake: **System Settings → Battery → Prevent sleeping when
  on power adapter** → turn ON
- If you close the laptop lid, the session will likely disconnect

---

## Phase 4 — Kaggle Setup

### 4.1 Create a Kaggle account

Go to https://www.kaggle.com and sign up if you don't have an account.
Verify your phone number — Kaggle requires this to enable GPU access.

### 4.2 Add your rclone config as a secret

1. Click your profile picture (top right) → **Settings**
2. Scroll down to **API** section → click **Add New Token** if you don't have one
3. Scroll to **Secrets** section → click **Add New Secret**
4. Fill in:
   - **Name:** `RCLONE_CONF`
   - **Value:** paste the rclone config you copied earlier
     (if you lost it, run `cat ~/.config/rclone/rclone.conf` in Terminal)
5. Click **Add**

### 4.3 Create the notebook

1. Click **Create** (top right) → **New Notebook**
2. A blank notebook opens

### 4.4 Upload the notebook content

1. Click the three dots **⋮** menu (top right of the notebook)
2. Click **Import Notebook**
3. Upload `notebooks/kaggle_worker.ipynb` from this project

### 4.5 Enable GPU and Internet

1. Click the three dots **⋮** menu → **Accelerator**
2. Select **GPU T4 x2** (or P100 if available)
3. Click the three dots **⋮** menu → **Internet** → turn **ON**

### 4.6 Run the cells

Same as Colab — run each cell one at a time, top to bottom.

**Cell 1** installs rclone and connects to Drive. If it succeeds you'll see:
`Google Drive connected!`

If it fails with "secret not found" — go back to step 4.2 and check the
secret name is exactly `RCLONE_CONF` (case-sensitive).

**Cell 2** installs OpenFOAM (takes ~5 min, same as Colab).

**Cells 3–4** setup and functions — should be quick.

**Cell 5** starts the worker loop. You'll see:
`CFD Worker (kaggle) started at HH:MM:SS`

Kaggle doesn't need a keep-alive script — its sessions are more stable.
But still keep the tab open.

---

## Phase 5 — Running the Optimizer

### 5.1 Pre-flight checklist

Before starting a session, verify all of these:

- [ ] Blender is open with the named car model loaded
- [ ] Blender MCP server is running (N panel → MCP → green status)
- [ ] Google Drive for Desktop is running (icon in Mac menu bar, not paused)
- [ ] Colab notebook is running (Cell 5 shows "Waiting for jobs...")
- [ ] Kaggle notebook is running (Cell 5 shows "Waiting for jobs...")
- [ ] Ollama is running (its icon is in the Mac menu bar)
- [ ] Your Mac is plugged in and sleep is disabled

### 5.2 Start the optimizer

Open a new Terminal window and run:

```bash
cd ~/f1-training-looper
uv run python orchestrator.py \
  --rulebook ~/Downloads/f1_2026_technical_regs.pdf \
  --base-model ~/Downloads/f1_2026_named.blend \
  --hours 12
```

Replace the paths with wherever you saved your files.

You'll see:
```
F1 Aero Optimization Loop
Rulebook:   ...
Base model: ...
Duration:   12 hours

Connecting to Blender...
Loading model into Blender...
Connecting to Google Drive...
Loading design agent (llava:7b)...

Starting optimization loop...
Will run until: HH:MM:SS

─── Iteration 1 ─────────────────────────────
Asking design agent for proposals...
  Variant A: Increase front wing angle to improve downforce...
  Running visual check (llava:7b)...
  Visual check passed
  Exported mesh: iter0001_A_ab3f92.stl (2048 KB)
  Submitted job iter0001_A_ab3f92 to Drive queue
  ...
  Waiting for CFD results: iter0001_A_ab3f92...
```

The first CFD run will take the longest (~10-20 min) because OpenFOAM
meshes the car for the first time.

### 5.3 What to expect during the session

- **Each iteration** takes 10–20 minutes (dominated by CFD solve time)
- **In 12 hours** you'll get roughly 36–70 design evaluations
- The optimizer prints a scoreboard after every iteration showing
  CL (downforce), CD (drag), and L/D ratio (the score being maximized)
- The best design is saved to `f1-opt/best/` in your Google Drive
  and to `output/best_design.stl` locally

### 5.4 If something goes wrong

**"Cannot connect to Blender MCP server"**
→ Check Blender is open and MCP server is started (N panel → MCP tab)

**"Model not found in Ollama"**
→ Run `ollama list` to see what's installed. Pull missing models.

**"Could not find Google Drive folder"**
→ Make sure Google Drive for Desktop app is running and you're signed in

**CFD timeout after 20 minutes**
→ Check that Colab and/or Kaggle notebooks are still running.
   If Colab disconnected, run Cell 5 again and paste the keep-alive script.

**Visual check keeps failing**
→ The car geometry might be too far from the camera. Open `visual_validator.py`
   and adjust the `CAMERAS` locations to frame your specific model better.

**LLM keeps proposing the same params**
→ The history is too short — this is normal in early iterations.
   It should diversify after 3–4 iterations.

---

## Phase 6 — After the Session

When the 12 hours are up, the orchestrator stops and prints the best result.

**Your best design is at:**
- `~/Google Drive/My Drive/f1-opt/best/best_design.stl`
- `~/f1-training-looper/output/best_design.stl`

**To view it in Blender:**
1. Open Blender
2. **File → Import → STL**
3. Select `best_design.stl`

**Full history** (all iterations, params, and CFD scores) is at:
- `~/Google Drive/My Drive/f1-opt/history.jsonl`

Each line is a JSON object with the design parameters and CFD results.
You can open this in any text editor to see what the optimizer tried.

---

## Recommended Session Schedule

For a reliable 12-hour run:

| Time | Action |
|------|--------|
| T-30 min | Start Colab, run all cells, paste keep-alive script |
| T-20 min | Start Kaggle, run all cells |
| T-10 min | Open Blender, load model, start MCP server |
| T=0 | Run `orchestrator.py` |
| T+3 hr | Check Terminal — verify iterations are completing |
| T+9 hr | Check Kaggle (sessions cap at 9 hr) — restart if needed |
| T+12 hr | Optimizer finishes, review results |
