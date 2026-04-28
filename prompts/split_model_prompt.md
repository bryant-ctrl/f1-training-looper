# Blender Mesh Splitting Prompt

Paste everything below the line into a Claude Code session that has the
Blender MCP server connected.

## How to set up Claude Code with Blender MCP

1. Open Blender and load your F1 car model
2. Enable the blender-mcp addon and click **Start MCP Server** (N panel → MCP)
3. In Terminal, add the Blender MCP server to Claude Code:

```bash
claude mcp add blender --transport http --url http://localhost:9876
```

4. Start Claude Code in this project directory:

```bash
cd ~/f1-training-looper
claude
```

5. Paste the prompt below into the Claude Code session

---

## Prompt to paste

```
I have a single-mesh F1 2026 car model loaded in Blender. It has no separate
parts — everything is welded into one object. I need you to split it into
5 named objects that my Python optimization script expects:

  front_wing   — the front wing assembly (nose-mounted, near the ground)
  rear_wing    — the rear wing (elevated, at the back)
  diffuser     — the rear underside/diffuser area
  floor        — the flat underbody panel spanning the car's length
  car_body     — everything else (chassis, sidepods, engine cover, cockpit)

Please do this step by step:

STEP 1: Inspect the scene
- List all objects currently in the scene
- Find the main car mesh (probably the only or largest object)
- Get its bounding box (min/max X, Y, Z) so we know the car's scale and
  orientation. The car should be pointing along the X axis, nose at the
  front (most negative X or most positive X — check which).

STEP 2: Plan the splits
Based on the bounding box, calculate approximate coordinate thresholds for
each part. Think aloud about where the front wing, rear wing, diffuser, and
floor would be in this specific model's coordinate space before cutting.

STEP 3: Do the splits
Use Blender Python (bpy + bmesh) to:
  1. Enter edit mode on the main mesh
  2. Select faces in the front wing region by spatial coordinates
  3. Separate → rename the new object "front_wing"
  4. Repeat for rear_wing, diffuser, floor
  5. Rename whatever remains "car_body"

For each separation, deselect all faces first, then select the target region
using face center coordinates. Use conservative thresholds — it's better to
leave ambiguous faces in car_body than to mislabel them.

STEP 4: Verify
- List all objects in the scene and confirm the 5 names exist
- Print the face count of each object so I can verify they're reasonable
  (e.g. front_wing and rear_wing should have a noticeable number of faces,
  not 0 or 2)
- If any object has 0 faces, adjust the thresholds and try that part again

STEP 5: Save
Save the result as a new .blend file called f1_2026_named.blend in the
same directory as the original model. Do not overwrite the original.

If you're unsure about any coordinate thresholds, print the bounding box
and ask me before cutting — it's easy to redo a cut but I want to make
sure the splits are sensible.
```
