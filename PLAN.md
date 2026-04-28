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

### 2. Mac Mini — Local LLM (Ollama)

Acts as the AI "brain." Reads:
- F1 2026 technical regulations (PDF, converted to text)
- Current design parameters (wing angles, diffuser geometry, etc.)
- CFD results from previous iterations (CL, CD, CL/CD ratio)

Outputs:
- A structured design change proposal (JSON)
- Reasoning for the change

**Recommended models (fit in 16GB M4 unified memory):**
- `qwen2.5:14b` (Q4_K_M, ~8GB) — best balance of speed and intelligence
- `llama3.1:8b` (Q4_K_M, ~5GB) — faster, slightly less capable
- `deepseek-r1:14b` (Q4_K_M, ~8GB) — strong reasoning, good for rule parsing

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
LLM reads: rulebook + current params + history
  │
  ▼
LLM proposes 2 design variants (for parallel CFD)
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
ollama pull qwen2.5:14b
```
This downloads ~8GB. Test it: `ollama run qwen2.5:14b "Hello"`

#### 1c. Install Blender MCP server
```bash
# In terminal (uv manages the Python env):
uv tool install blender-mcp
```
Then in Blender: install the companion addon (instructions in blender-mcp repo).
Start the MCP server from Blender's addon panel before running the orchestrator.

#### 1d. Create the project
```bash
cd ~/f1-training-looper   # or wherever you want it
uv init
uv add ollama openai pymupdf google-auth google-api-python-client watchdog
```

#### 1e. Google Drive API credentials
1. Go to https://console.cloud.google.com
2. Create a new project → Enable "Google Drive API"
3. Create credentials → OAuth 2.0 → Desktop app
4. Download the `credentials.json` file into your project folder
5. Run the orchestrator once — it'll open a browser to authorize, then save
   a `token.json` for future runs

---

### Phase 2 — Google Colab Setup

1. Go to https://colab.research.google.com
2. Create a new notebook, name it `cfd_worker_a.ipynb`
3. In the first cell, mount your Drive:
   ```python
   from google.colab import drive
   drive.mount('/content/drive')
   ```
4. Install OpenFOAM (takes ~5 min first run — save output to avoid redoing):
   ```bash
   !apt-get install -y openfoam
   ```
5. Paste the CFD worker loop code (provided in `notebooks/colab_worker.ipynb`
   in this repo)
6. Run → Keep the browser tab open on your Mac during the 12-hour session

**Free tier tip:** Click "Connect" and immediately run all cells. If you leave
the tab open and the notebook is actively running, Colab rarely disconnects.

---

### Phase 3 — Kaggle Setup

1. Go to https://www.kaggle.com → Your profile → "New Notebook"
2. Enable internet: Settings → Internet → On (required for Drive access)
3. Enable GPU: Settings → Accelerator → GPU T4 x2 or P100
4. Add your Google Drive credentials as a Kaggle Secret:
   - Settings → Secrets → Add new secret → paste contents of `credentials.json`
5. Paste the CFD worker loop code (same as Colab but with minor path changes,
   provided in `notebooks/kaggle_worker.ipynb`)
6. Run → Kaggle sessions auto-save and are more stable than Colab free

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
├── orchestrator.py          # Main loop — runs on Mac
├── blender_bridge.py        # Talks to Blender MCP
├── llm_agent.py             # Ollama LLM interface
├── drive_sync.py            # Google Drive upload/download
├── rule_checker.py          # Validates designs against F1 regs
├── scorer.py                # Parses CFD output, computes CL/CD
├── notebooks/
│   ├── colab_worker.ipynb   # Paste into Google Colab
│   └── kaggle_worker.ipynb  # Paste into Kaggle
├── prompts/
│   └── design_agent.txt     # System prompt for the LLM
├── output/
│   ├── best_design.obj      # Best design found
│   └── history.jsonl        # All runs + scores
├── pyproject.toml           # uv project config
└── PLAN.md                  # This file
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
| 16GB Mac RAM limits Blender + LLM running simultaneously | Run LLM inference in bursts (not streaming) between Blender ops |

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
