"""
Design agent + visual validator — unified qwen2-vl:7b multimodal model.

qwen2-vl:7b handles both roles:
  1. Geometry validation — checks renders for broken geometry before CFD
  2. Design proposals    — sees renders of past iterations alongside CFD
                           scores, so it reasons visually not just numerically

Setup:
  ollama pull qwen2-vl:7b
"""

import json
import re
import tempfile
from pathlib import Path

import fitz  # PyMuPDF
import ollama

from rule_checker import DEFAULT_PARAMS, LIMITS

MODEL = "qwen2-vl:7b"

SYSTEM_PROMPT = Path("prompts/design_agent.txt").read_text()

# Camera angles for Blender renders.
# (label, xyz location, euler rotation in radians)
# Assumes car at origin, nose pointing +X.
CAMERAS = [
    ("front", (0, -12, 1.5), (1.5708, 0, 0)),
    ("side",  (-12, 0, 2.0), (1.5708, 0, -1.5708)),
    ("iso",   (8,  -8, 6.0), (1.05,   0,  0.7854)),
]

VALIDATION_PROMPT = (
    "This is a render of an F1 racing car 3D model. "
    "Check for these problems: floating or detached parts, wings intersecting "
    "the bodywork, missing major components (front wing, rear wing, tyres), "
    "or heavily distorted geometry that doesn't resemble a real car. "
    "Reply with exactly one word on the first line — PASS or FAIL — "
    "then one sentence explaining why."
)


def extract_pdf_text(pdf_path: Path, max_chars: int = 40_000) -> str:
    doc = fitz.open(str(pdf_path))
    chunks, total = [], 0
    for page in doc:
        text = page.get_text()
        chunks.append(text)
        total += len(text)
        if total >= max_chars:
            break
    return "\n".join(chunks)[:max_chars]


class DesignAgent:
    def __init__(self, rulebook_path: Path, blender_bridge, model: str = MODEL):
        self.model = model
        self.blender = blender_bridge
        self.render_dir = Path(tempfile.mkdtemp(prefix="f1_renders_"))
        self.render_dir.mkdir(parents=True, exist_ok=True)

        print(f"Loading rulebook: {rulebook_path}")
        self.rules_text = extract_pdf_text(rulebook_path)
        print(f"  Extracted {len(self.rules_text):,} chars from rulebook")
        self._verify_ollama()

    def _verify_ollama(self) -> None:
        try:
            ollama.show(self.model)
        except Exception:
            raise RuntimeError(
                f"Model '{self.model}' not found in Ollama.\n"
                f"Run: ollama pull {self.model}"
            )

    # ── Rendering ────────────────────────────────────────────────────

    def render_current(self, label_prefix: str) -> list[Path]:
        """Render the current Blender scene from 3 angles. Returns paths."""
        paths = []
        for label, loc, rot in CAMERAS:
            out_path = self.render_dir / f"{label_prefix}_{label}.png"
            path_str = str(out_path).replace("\\", "/")
            code = f"""
import bpy
cam_name = 'f1_agent_{label}'
if cam_name not in bpy.data.objects:
    cam_data = bpy.data.cameras.new(cam_name)
    cam_obj  = bpy.data.objects.new(cam_name, cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
else:
    cam_obj = bpy.data.objects[cam_name]
cam_obj.location       = {loc}
cam_obj.rotation_euler = {rot}
bpy.context.scene.camera = cam_obj
scene = bpy.context.scene
scene.render.resolution_x = 512
scene.render.resolution_y = 384
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = '{path_str}'
bpy.ops.render.render(write_still=True)
print('render done')
"""
            try:
                self.blender._send(code)
                if out_path.exists():
                    paths.append(out_path)
            except Exception as e:
                print(f"  [agent] Render '{label}' failed: {e}")
        return paths

    # ── Validation ───────────────────────────────────────────────────

    def validate(self, renders: list[Path]) -> tuple[bool, str]:
        """
        Check renders for broken geometry. Majority vote across angles.
        Returns (is_valid, summary).
        """
        if not renders:
            return True, "No renders — skipping visual check"

        results = []
        for img in renders:
            try:
                resp = ollama.chat(
                    model=self.model,
                    messages=[{
                        "role": "user",
                        "content": VALIDATION_PROMPT,
                        "images": [str(img)],
                    }],
                )
                text = resp["message"]["content"].strip()
                passed = "FAIL" not in text.split("\n")[0].upper()
                results.append((img.stem.split("_")[-1], passed, text[:150]))
            except Exception as e:
                results.append((img.stem, True, f"check error: {e}"))

        pass_count = sum(1 for _, p, _ in results if p)
        majority_pass = pass_count >= (len(results) / 2)
        lines = [f"  {lbl}: {'PASS' if p else 'FAIL'} — {r}" for lbl, p, r in results]
        summary = (
            f"{'PASS' if majority_pass else 'FAIL'} "
            f"({pass_count}/{len(results)} angles OK)\n" + "\n".join(lines)
        )
        return majority_pass, summary

    # ── Design proposals ─────────────────────────────────────────────

    def _history_summary(self, history: list, max_entries: int = 8) -> str:
        if not history:
            return "No previous iterations yet."
        lines = []
        for h in history[-max_entries:]:
            lines.append(
                f"  iter={h['iteration']} variant={h['variant']} "
                f"score={h['score']:.3f} "
                f"CL={h['results']['cl']:.4f} CD={h['results']['cd']:.4f} "
                f"params={json.dumps(h['params'])}"
            )
        return "\n".join(lines)

    def _recent_renders(self, history: list, max_renders: int = 6) -> list[str]:
        """Collect up to max_renders render paths from recent history entries."""
        paths = []
        for entry in reversed(history):
            for p in entry.get("renders", []):
                if Path(p).exists():
                    paths.append(p)
                if len(paths) >= max_renders:
                    return paths
        return paths

    def propose(self, current_params: dict, history: list) -> dict:
        """
        Ask the model for two design variants. Passes recent renders as images
        so the model can reason visually about what past designs looked like.
        Returns: {"variant_a": {params, reasoning}, "variant_b": {params, reasoning}}
        """
        param_bounds = {k: {"min": v["min"], "max": v["max"]} for k, v in LIMITS.items()}
        recent_render_paths = self._recent_renders(history)

        text_content = f"""
Current design parameters:
{json.dumps(current_params, indent=2)}

Parameter legal limits:
{json.dumps(param_bounds, indent=2)}

Recent design history (newest last):
{self._history_summary(history)}

F1 2026 Technical Regulation excerpts:
{self.rules_text[:8000]}

{"The images above show renders of recent design iterations (front, side, isometric views)." if recent_render_paths else "No previous renders available yet."}

Propose two design variants to improve aerodynamic efficiency (maximize CL/CD).
Variant A should be a conservative refinement of the best result so far.
Variant B should be a bolder change — try something the history hasn't explored.

Respond ONLY with valid JSON in exactly this structure:
{{
  "variant_a": {{
    "reasoning": "...",
    "regulation_basis": "Art. X.X.X allows ...",
    "parameters": {{
      "front_wing_main_angle": 0.0,
      "front_wing_flap_angle": 0.0,
      "rear_wing_main_angle": 0.0,
      "rear_wing_beam_angle": 0.0,
      "front_ride_height": 0.0,
      "rear_ride_height": 0.0,
      "diffuser_angle": 0.0,
      "diffuser_exit_height": 0.0,
      "floor_edge_height": 0.0
    }}
  }},
  "variant_b": {{
    "reasoning": "...",
    "regulation_basis": "Art. X.X.X allows ...",
    "parameters": {{ ... }}
  }}
}}
"""
        message = {"role": "user", "content": text_content}
        if recent_render_paths:
            message["images"] = recent_render_paths

        response = ollama.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                message,
            ],
            options={"temperature": 0.4},
        )
        return self._parse_response(response["message"]["content"], current_params)

    def _parse_response(self, raw: str, fallback_params: dict) -> dict:
        raw = re.sub(r"```(?:json)?", "", raw).strip()
        try:
            data = json.loads(raw)
            for key in ("variant_a", "variant_b"):
                if key not in data or "parameters" not in data[key]:
                    raise ValueError(f"Missing '{key}.parameters'")
            return data
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[agent] Failed to parse response ({e}), using fallback")
            return {
                "variant_a": {"reasoning": "parse error", "regulation_basis": "", "parameters": fallback_params},
                "variant_b": {"reasoning": "parse error", "regulation_basis": "", "parameters": fallback_params},
            }
