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

The notebook file is at `notebooks/colab_worker.ipynb` in this repo.
It is a complete, ready-to-run notebook — you do not need to type any code.

### 3.1 Upload the notebook

1. Go to https://colab.research.google.com
2. In the welcome dialog, click the **Upload** tab
   — if there's no dialog, go to **File → Upload notebook** in the top menu
3. Click **Browse** and select `notebooks/colab_worker.ipynb` from this project
4. The notebook opens with all 5 cells already populated — do not edit them

### 3.2 Switch to a GPU runtime

1. Click **Runtime** in the top menu bar
2. Click **Change runtime type**
3. Under **Hardware accelerator**, select **T4 GPU**
4. Click **Save**

You'll see a message that the runtime restarted — that's expected and normal.

### 3.3 Run Cell 1 — Mount Google Drive

Click the **▶ play button** on the left of Cell 1, or press **Shift+Enter**.

- A popup appears saying Colab wants to access your Google Drive
- Click **Connect to Google Drive**
- A second browser tab or popup opens — sign in with your Google account
- Come back to the Colab tab

✅ **Success:** the cell finishes and prints `Mounted at /content/drive`

❌ **If the popup never appeared:** click the ▶ button again. Sometimes the
popup is blocked — check your browser's address bar for a blocked popup icon.

### 3.4 Run Cell 2 — Install OpenFOAM

Click ▶ on Cell 2.

- A large wall of text starts scrolling — this is the OpenFOAM installation
- This is **completely normal** — do not stop it
- It takes **4–6 minutes**

✅ **Success:** scrolling stops and the last line says `OpenFOAM installed.`

❌ **If it errors with "apt-get failed":** click ▶ again — apt-get occasionally
fails on first attempt in Colab and succeeds on the second try.

### 3.5 Run Cell 3 — Setup paths

Click ▶. This finishes in under a second.

✅ **Success:** prints two lines like:
```
Queue: /content/drive/MyDrive/f1-opt/queue
Results: /content/drive/MyDrive/f1-opt/results
Worker ID: colab
```

If the paths look wrong or you see a Drive error, go back and re-run Cell 1.

### 3.6 Run Cell 4 — Define CFD functions

Click ▶. Also finishes instantly.

✅ **Success:** prints `Case setup functions ready.`

### 3.7 Run Cell 5 — Start the worker loop

Click ▶ on Cell 5.

✅ **Success:** prints:
```
CFD Worker (colab) started at HH:MM:SS
Watching queue: /content/drive/MyDrive/f1-opt/queue
Waiting for jobs...
```

The cell now shows a **spinning circle** on the left — this means it is
actively running and waiting for mesh jobs from your Mac. **Do not click stop.**

When a job arrives from the Mac, you will see it print lines like:
```
[14:32:01] Processing job: iter0001_A_ab3f92
  blockMesh...
  snappyHexMesh...
  simpleFoam...
  Done! CL=1.2341  CD=0.8823  L/D=1.399
```

### 3.8 Activate the keep-alive script

This prevents the browser from putting the tab to sleep and auto-reconnects
the session if it drops.

1. With the Colab tab active, press **Cmd + Option + J** on your Mac keyboard
   — this opens the browser's developer console in a panel at the bottom
2. Click the **Console** tab if it's not already selected
3. On your Mac, open `notebooks/colab_keepalive.js` in any text editor
   (TextEdit, VS Code, etc.)
4. Select all the text (**Cmd+A**) and copy it (**Cmd+C**)
5. Click inside the console input at the very bottom of the DevTools panel
6. Paste (**Cmd+V**) and press **Enter**

✅ **Success:** you see `[keep-alive] Started. Runs every 30s.`

You can now close the DevTools panel by pressing **Cmd + Option + J** again.
The script keeps running invisibly. Every 5 minutes it logs a heartbeat
message you can check if you re-open the console.

**Also do this:**
- Go to **System Settings → Battery → Options**
- Turn on **"Prevent automatic sleeping on power adapter when the display is off"**
- Keep the Colab tab visible in your browser — don't bury it behind other windows

---

## Phase 4 — Kaggle Setup

The notebook file is at `notebooks/kaggle_worker.ipynb` in this repo.
Kaggle uses rclone to talk to your Google Drive instead of a native mount.

### 4.1 Verify your Kaggle account has GPU access

1. Go to https://www.kaggle.com and sign in
2. Click your profile picture (top right) → **Settings**
3. Scroll to **Phone Verification** — if it says unverified, verify now
   (Kaggle requires this to unlock GPU and Internet access)

### 4.2 Add your rclone config as a Kaggle secret

The rclone config you created in Phase 1.7 needs to be stored in Kaggle
so the notebook can authenticate with your Google Drive.

On your Mac, run:
```bash
cat ~/.config/rclone/rclone.conf | pbcopy
```

This copies the config contents to your clipboard.

In Kaggle:
1. Click your profile picture → **Settings**
2. Scroll down to the **Secrets** section
3. Click **Add New Secret**
4. **Name:** type `RCLONE_CONF` exactly — capital letters, underscore, no spaces
5. **Value:** paste from clipboard (**Cmd+V**)
6. Click **Add**

### 4.3 Create the notebook

1. Click **Create** (top right of any Kaggle page) → **New Notebook**
2. A blank notebook opens in the editor

### 4.4 Upload the notebook file

1. In the notebook editor, click the **⋮** (three dots) menu in the top right
2. Click **Import Notebook**
3. In the dialog that appears, click **Browse** or drag-and-drop
4. Select `notebooks/kaggle_worker.ipynb` from this project
5. The notebook reloads with all 5 cells populated

### 4.5 Enable GPU and Internet

These **must** be turned on before running any cells, otherwise Cell 1
and Cell 2 will fail.

1. Click the **⋮** menu (top right) → **Accelerator**
2. Select **GPU T4 x2** — click **Save**
3. Click the **⋮** menu again → **Internet**
4. Toggle it **On** — click **Save**

If you don't see the Internet or GPU options, your phone verification
hasn't been approved yet — check your Kaggle Settings and try again.

### 4.6 Run Cell 1 — Install rclone and connect to Drive

Click ▶ on Cell 1. Takes about 1 minute.

✅ **Success:** last line says:
```
Google Drive connected! f1-opt contents: (empty or folder list)
```

❌ **"secret not found":** the secret name must be exactly `RCLONE_CONF`
(all caps, underscore). Go back to step 4.2 and re-add it with the
correct name.

❌ **"Failed to create file system":** your rclone token may have expired.
On your Mac, run `rclone config reconnect gdrive:` to refresh it, then
copy the updated `~/.config/rclone/rclone.conf` and update the Kaggle secret.

### 4.7 Run Cell 2 — Install OpenFOAM

Click ▶. Takes 4–6 minutes, same as Colab.

✅ **Success:** prints `Done.`

❌ If it errors, click ▶ again — same apt-get quirk as Colab.

### 4.8 Run Cells 3 and 4 — Setup and functions

Click ▶ on each. Both finish instantly.

✅ Cell 3 prints: `Worker kaggle ready.`
✅ Cell 4 prints: `Functions ready.`

### 4.9 Run Cell 5 — Start the worker loop

Click ▶.

✅ **Success:**
```
CFD Worker (kaggle) started at HH:MM:SS
Syncing from Drive and watching for jobs...
```

The cell shows a spinning circle — it is running. Leave it.

When jobs arrive it prints the same progress as the Colab worker:
```
[14:45:11] Processing: iter0001_B_cc7e44
  blockMesh...
  snappyHexMesh...
  simpleFoam...
  CL=1.1902  CD=0.9011  L/D=1.321
```

**Kaggle session limit:** free sessions cap at **9 hours**. Plan to start
your Kaggle notebook about 3 hours into the 12-hour run so both workers
are active for most of the session. If Kaggle stops, go back to Cell 5
and click ▶ to resume — it will pick up from the Drive queue automatically.

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
→ The car geometry might be too far from the camera. Open `llm_agent.py`
   and adjust the `CAMERAS` list (around line 20) to frame your specific model better.

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
