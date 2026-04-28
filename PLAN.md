# F1 Aero Optimization Framework — Plan

## Goal
Automatically iterate on a base F1 2026 car model to maximize aerodynamic
performance (downforce/drag ratio) while staying within the F1 2026 technical
regulations, using a 12-hour AI-driven loop.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    Mac Mini M4                      │
│                                                     │
│  ┌─────────────┐   ┌──────────┐   ┌─────────────┐  │
│  │  Orchestrat │   │  Blender │   │  Local LLM  │  │
│  │  or (Python)│◄─►│  + MCP   │   │  (Ollama)   │  │
│  └──────┬──────┘   └──────────┘   └──────┬──────┘  │
│         │                                │          │
│         └────────────────────────────────┘          │
│                        │                            │
│         Exports STL/OBJ mesh for CFD                │
└─────────────────────────────────────────────────────┘
              │                        │
              ▼                        ▼
   ┌──────────────────┐    ┌──────────────────────┐
   │  Google Colab    │    │   Kaggle Notebook     │
   │  (CFD Worker A)  │    │   (CFD Worker B)      │
   │                  │    │                       │
   │  OpenFOAM        │    │  OpenFOAM             │
   │  simpleFoam      │    │  simpleFoam           │
   │  Returns: CL, CD │    │  Returns: CL, CD      │
   └──────────────────┘    └──────────────────────┘
              │                        │
              └────────────┬───────────┘
                           ▼
                  Results back to Mac
                  Orchestrator decides
                  next design change
```

**Data flow summary:**
1. Mac LLM reads F1 rulebook PDF + current car geometry → proposes a change
2. Mac Blender applies the change via MCP → exports mesh (STL/OBJ)
3. Mesh uploaded to Google Drive / shared storage
4. Colab or Kaggle notebook picks it up, runs OpenFOAM CFD, saves results
5. Mac orchestrator reads results, scores the design, feeds back to LLM
6. Repeat for 12 hours, keep best design

---

## Component Details

### 1. Mac Mini — Orchestrator (`orchestrator.py`)

The main loop. Responsibilities:
- Load and parse the F1 2026 rulebook PDF into a text prompt for the LLM
- Maintain a design history log (what was tried, what scored what)
- Call the local LLM to propose the next geometry change
- Trigger Blender via MCP to apply the change and export the mesh
- Upload the mesh to Google Drive
- Poll for CFD results
- Score results and track the best-so-far design

**Language:** Python (managed with `uv`)

### 2. Mac Mini — Local Multimodal LLM (Ollama)

A single model handles both roles:

**Role A — Visual validator:** After Blender applies each design change, the
model is shown renders from three camera angles (front, side, isometric) and
asked whether the geometry looks like a valid F1 car. Broken geometry is caught
here before any CFD compute is wasted.

**Role B — Design agent:** When proposing the next design, the model receives
renders of the last 3–5 iterations *as images* alongside their CL/CD scores.
This means it can reason visually — e.g. "the front wing in iteration 4 looks
stalled, let me reduce the angle" — instead of purely pattern-matching on numbers.

**Model:** `llava:7b` (Q4_K_M, ~5 GB)
Fits comfortably in 16 GB alongside Blender. Handles both vision and structured
JSON output.

### 3. Mac Mini — Blender + MCP

Blender runs locally. The Blender MCP server exposes Python scripting
over a socket so the orchestrator can:
- Load the base F1 2026 .blend / .obj / .fbx file
- Apply parametric geometry changes (wing angles, ride height, diffuser flap
  angles, sidepod shapes, etc.)
- Export the modified mesh as STL for CFD

**Blender MCP server:** `blender-mcp` (open source, runs as a local server)

### 4. Google Colab — CFD Worker A

A persistent notebook that:
1. Mounts Google Drive
2. Watches for a new mesh file + job marker
3. Runs OpenFOAM `simpleFoam` (steady-state incompressible RANS)
4. Extracts CL (lift coefficient) and CD (drag coefficient)
5. Writes results JSON back to Drive
6. Loops back to step 2

Free tier gives a T4 GPU (16GB) + decent CPU. OpenFOAM mostly uses CPU
for mesh solving; GPU acceleration is a bonus.

**Session limit:** ~9-12 hours max on free tier. Keep the Colab tab open
in a browser on your Mac to prevent disconnect.

### 5. Kaggle Notebook — CFD Worker B

Same as Colab worker but on Kaggle's free P100/T4.
Kaggle gives 30 GPU hours/week; sessions up to 9 hours.
Used in parallel with Colab to evaluate more designs per 12-hour session.

**Parallelism:** Orchestrator sends two mesh variants simultaneously —
one to Colab, one to Kaggle — doubling throughput.

---

## Shared Storage: Google Drive

Google Drive acts as the message bus between Mac and notebooks:
- `f1-opt/queue/` — meshes waiting for CFD (dropped by Mac)
- `f1-opt/results/` — CFD result JSONs (written by notebooks)
- `f1-opt/best/` — current best design mesh + score
- `f1-opt/history/` — all past results for LLM context

The Mac orchestrator uses the `google-auth` + `google-api-python-client`
libraries (via `uv`) to upload/download files programmatically.
Colab and Kaggle mount Drive natively.

---

## The Optimization Loop (12-hour session)

```
START
  │
  ▼
Load base F1 2026 model into Blender
  │
  ▼
Agent reads: rulebook + current params + history + renders of last 5 designs
  │
  ▼
Agent proposes 2 variants — visual reasoning from renders + numerical CFD history
  │
  ├──► Blender applies variant A → export mesh A → upload to Drive
  └──► Blender applies variant B → export mesh B → upload to Drive
                │
                ▼
       Colab runs CFD on A          Kaggle runs CFD on B
       Returns: CL_A, CD_A         Returns: CL_B, CD_B
                │
                ▼
       Score = CL/CD (maximize downforce, minimize drag)
       Rule check: does design violate any 2026 regs?
                │
                ├── If better than best: save as new best
                └── Always: append to history
                │
                ▼
             Repeat
              │
              ▼ (after 12 hours or keyboard interrupt)
            DONE
  Export best design, generate report
```

**Expected iterations:** CFD for a simplified F1 mesh on a T4/P100 takes
roughly 5-20 minutes depending on mesh resolution. In 12 hours with 2
parallel workers: ~36-144 design evaluations.

---

## F1 Regulations Compliance

The LLM is given the full F1 2026 technical regulations PDF as context.
It is prompted to:
- Only propose changes within legal bounds (wing dimensions, ride height
  limits, floor geometry, etc.)
- Explicitly state which regulation article permits each change
- Flag if a proposed change is near a limit

A separate rule-checker function (Python, deterministic) validates key
dimensional constraints before sending a mesh to CFD, to avoid wasting
compute on illegal designs.

---

## Setup Guide (Beginner Step-by-Step)

### Phase 0 — Prerequisites

- [ ] Download Blender (free): https://www.blender.org/download/
- [ ] Download your base F1 2026 model from Sketchfab (get .obj or .fbx)
- [ ] Have your F1 2026 rulebook PDF ready
- [ ] Create a Google account (for Drive + Colab)
- [ ] Create a Kaggle account: https://www.kaggle.com

---

### Phase 1 — Mac Mini Setup

#### 1a. Install `uv` (Python manager)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
Restart your terminal after. Verify: `uv --version`

#### 1b. Install Ollama (local LLM runner)
```bash
# Download from https://ollama.com — it's a .dmg, drag to Applications
# Then in terminal:
ollama pull llava:7b
```
This downloads ~5 GB. Test it: `ollama run llava:7b "Hello"`

#### 1c. Install Blender MCP server
```bash
# In terminal (uv manages the Python env):
uv tool install blender-mcp
```
Then in Blender: install the companion addon (instructions in blender-mcp repo).
Start the MCP server from Blender's addon panel before running the orchestrator.

#### 1d. Set up the project
```bash
cd ~/f1-training-looper
uv sync
```

#### 1e. Set up Google Drive (no API needed)
Install Google Drive for Desktop from https://www.google.com/drive/download/
Sign in. It creates a synced folder on your Mac — no credentials file needed.

---

### Phase 2 — Google Colab Setup

The notebook file is at `notebooks/colab_worker.ipynb` in this repo.
It is a complete, ready-to-run notebook — you do not need to type any code.

#### 2a. Upload the notebook to Colab

1. Go to https://colab.research.google.com
2. In the welcome dialog, click the **Upload** tab
   (if there's no dialog, go to **File → Upload notebook**)
3. Click **Browse** and select `notebooks/colab_worker.ipynb` from this project
4. The notebook opens with all cells already populated

#### 2b. Switch to a GPU runtime

1. Click **Runtime** in the top menu bar
2. Click **Change runtime type**
3. Under **Hardware accelerator**, select **T4 GPU**
4. Click **Save**

You'll see a note that the runtime has restarted — that's expected.

#### 2c. Run the cells in order

Cells run by clicking the **▶ play button** on the left side of each cell,
or by pressing **Shift+Enter** with the cell selected.

Run them **one at a time, top to bottom**. Do not skip ahead.

**Cell 1 — Mount Google Drive**
- Click ▶
- A popup appears: click **Connect to Google Drive**
- Sign in with your Google account if prompted
- ✅ Success looks like: `Mounted at /content/drive`

**Cell 2 — Install OpenFOAM**
- Click ▶
- You will see a large wall of text scrolling — this is normal
- Takes **4–6 minutes**
- ✅ Success: last line says `OpenFOAM installed.`
- ❌ If it errors, click ▶ again — apt sometimes fails on first try

**Cell 3 — Setup paths**
- Click ▶ — finishes instantly
- ✅ Prints the queue and results folder paths

**Cell 4 — Define case functions**
- Click ▶ — finishes instantly
- ✅ Prints: `Case setup functions ready.`

**Cell 5 — Start the worker loop**
- Click ▶
- ✅ Prints: `CFD Worker (colab) started at HH:MM:SS`
- `Waiting for jobs...`
- The cell now shows a spinning indicator — it is running and waiting
- **Do not click stop.** Leave this running.

#### 2d. Keep Colab awake

Open your browser's developer console:
- **Mac:** press `Cmd + Option + J`
- **Windows:** press `F12`, then click the Console tab

Open `notebooks/colab_keepalive.js` in a text editor, copy all the text,
paste it into the console, and press **Enter**.

You should see: `[keep-alive] Started. Runs every 30s.`

Close DevTools. The script runs invisibly in the background.

**Also:** Go to **System Settings → Battery** on your Mac and make sure
"Prevent automatic sleeping when the display is off" is enabled, or simply
keep your Mac awake and the Colab tab visible.

---

### Phase 3 — Kaggle Setup

The notebook file is at `notebooks/kaggle_worker.ipynb` in this repo.

#### 3a. Create a Kaggle account and verify your phone

1. Go to https://www.kaggle.com → **Register**
2. After signing up, go to **Settings → Phone Verification** and verify
   your phone number — Kaggle requires this to unlock GPU access

#### 3b. Add your rclone config as a secret

Kaggle uses rclone to talk to your Google Drive.

On your Mac, run:
```bash
brew install rclone
rclone config
```

In the rclone config wizard:
- New remote → name it `gdrive` → type `drive` → press Enter through the
  defaults → use auto config (opens browser) → sign in → done

Then copy the config to clipboard:
```bash
cat ~/.config/rclone/rclone.conf | pbcopy
```

In Kaggle:
1. Click your profile picture → **Settings**
2. Scroll to **Secrets** → **Add New Secret**
3. Name: `RCLONE_CONF` (must be exact, it is case-sensitive)
4. Value: paste from clipboard (Cmd+V)
5. Click **Add**

#### 3c. Upload the notebook

1. On Kaggle, click **Create** (top right) → **New Notebook**
2. Click the **⋮** menu (three dots, top right of the notebook editor)
3. Click **Import Notebook**
4. Upload `notebooks/kaggle_worker.ipynb` from this project
5. The notebook loads with all cells populated

#### 3d. Enable GPU and Internet

Both must be on before running any cells.

1. Click the **⋮** menu → **Accelerator** → select **GPU T4 x2**
2. Click the **⋮** menu → **Internet** → toggle **On**

If you don't see Internet or GPU options, your phone verification
may not have completed — check Kaggle Settings.

#### 3e. Run the cells in order

Same approach as Colab — click ▶ on each cell, top to bottom.

**Cell 1 — Install rclone + connect to Drive**
- Takes ~1 minute
- ✅ Success: `Google Drive connected! f1-opt contents: ...`
- ❌ "secret not found": check the secret name is exactly `RCLONE_CONF`
- ❌ "auth error": your rclone config may have expired — re-run `rclone config`
  on your Mac and update the Kaggle secret

**Cell 2 — Install OpenFOAM**
- Same as Colab, takes 4–6 minutes
- ✅ `Done.`

**Cells 3–4** — Setup, finishes quickly

**Cell 5 — Worker loop**
- ✅ `CFD Worker (kaggle) started at HH:MM:SS`
- Leave running. Kaggle sessions are more stable than Colab free tier.

Kaggle sessions cap at **9 hours**. Plan to start it ~3 hours into your
12-hour session so both workers are active for most of the run.

---

### Phase 4 — First Run

```bash
cd ~/f1-training-looper
uv run python orchestrator.py \
  --rulebook path/to/f1_2026_regulations.pdf \
  --base-model path/to/f1_2026_car.obj \
  --hours 12
```

The orchestrator will:
1. Parse the rulebook
2. Load the model into Blender
3. Start proposing and evaluating designs
4. Print a live scoreboard in your terminal
5. Save the best design to `output/best_design.obj` when done

---

## File Structure

```
f1-training-looper/
├── orchestrator.py           # Main loop — runs on Mac
├── blender_bridge.py         # Talks to Blender MCP
├── llm_agent.py              # llava:7b: design proposals + visual validation
├── drive_sync.py             # Google Drive desktop app folder sync
├── rule_checker.py           # Validates designs against F1 regs
├── scorer.py                 # Parses CFD output, computes CL/CD
├── setup_model.py            # One-time helper: name Blender objects
├── notebooks/
│   ├── colab_worker.ipynb    # Upload to Google Colab
│   ├── kaggle_worker.ipynb   # Upload to Kaggle
│   └── colab_keepalive.js    # Paste into browser console to prevent disconnect
├── prompts/
│   └── design_agent.txt      # System prompt for the design agent
├── output/
│   ├── best_design.stl       # Best design found
│   └── history.jsonl         # All runs + scores
├── pyproject.toml            # uv project config
├── PLAN.md                   # This file
└── SETUP.md                  # Detailed step-by-step setup guide
```

---

## Risks & Honest Caveats

| Risk | Mitigation |
|------|-----------|
| Colab free disconnects mid-session | Keep browser tab open; notebook auto-resumes from Drive queue |
| Kaggle session ends at 9hr limit | Start Kaggle ~3hrs into session so both workers overlap |
| OpenFOAM setup on Colab is fragile | Use a pre-built Docker image or conda install as fallback |
| CFD mesh quality affects results | Start with coarse mesh (fast), refine later once loop works |
| LLM proposes invalid designs | Rule checker rejects before CFD, no wasted compute |
| 16GB Mac RAM limits Blender + model simultaneously | llava:7b uses ~5GB — leaves plenty for Blender |

---

## Phased Implementation Order

1. **Phase 1** — Get Blender MCP working on Mac, manually export one mesh
2. **Phase 2** — Get OpenFOAM running in Colab, manually test one CFD run
3. **Phase 3** — Wire Mac → Drive → Colab with a dummy "mesh ready" signal
4. **Phase 4** — Add the LLM agent and rule checker
5. **Phase 5** — Close the loop end-to-end with a 1-hour test run
6. **Phase 6** — Run a full 12-hour session

Do not skip to Phase 6. Each phase is a checkpoint where you can verify
things work before adding complexity.
