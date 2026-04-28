"""
Visual sanity check using moondream vision model.

After Blender applies a design change, renders the car from three angles
and asks moondream whether the geometry looks like a valid F1 car.
If moondream flags obvious problems, the design is skipped before any
CFD compute is wasted on it.

Setup:
  ollama pull moondream
"""

import tempfile
from pathlib import Path

import ollama

VISION_MODEL = "moondream"

# (label, xyz location, euler rotation in radians)
# Tuned for a car sitting at the origin, nose pointing in +X.
CAMERAS = [
    ("front", (0, -12, 1.5),  (1.5708, 0, 0)),
    ("side",  (-12, 0, 2.0),  (1.5708, 0, -1.5708)),
    ("iso",   (8,  -8, 6.0),  (1.05,   0,  0.7854)),
]

PROMPT = (
    "This is a render of an F1 racing car 3D model. "
    "Check for these problems: floating or detached parts, wings intersecting "
    "the bodywork, missing major components (front wing, rear wing, tyres), "
    "or heavily distorted geometry that doesn't resemble a real car. "
    "Reply with exactly one word on the first line — PASS or FAIL — "
    "then one sentence explaining why."
)


class VisualValidator:
    def __init__(self, blender_bridge, render_dir: Path | None = None):
        self.blender = blender_bridge
        self.render_dir = render_dir or Path(tempfile.mkdtemp(prefix="f1_renders_"))
        self.render_dir.mkdir(parents=True, exist_ok=True)
        self._verify_model()

    def _verify_model(self) -> None:
        try:
            ollama.show(VISION_MODEL)
        except Exception:
            raise RuntimeError(
                f"Vision model '{VISION_MODEL}' not found in Ollama.\n"
                f"Run: ollama pull {VISION_MODEL}"
            )

    def _render_angle(self, label: str, location: tuple, rotation: tuple) -> Path | None:
        out_path = self.render_dir / f"render_{label}.png"
        path_str = str(out_path).replace("\\", "/")
        code = f"""
import bpy

cam_name = 'f1_validator_{label}'
if cam_name not in bpy.data.objects:
    cam_data = bpy.data.cameras.new(cam_name)
    cam_obj  = bpy.data.objects.new(cam_name, cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
else:
    cam_obj = bpy.data.objects[cam_name]

cam_obj.location      = {location}
cam_obj.rotation_euler = {rotation}
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
            return out_path if out_path.exists() else None
        except Exception as e:
            print(f"  [visual_validator] Render '{label}' failed: {e}")
            return None

    def _ask_moondream(self, image_path: Path) -> tuple[bool, str]:
        """Return (passed, one-line reason) for a single render."""
        try:
            response = ollama.chat(
                model=VISION_MODEL,
                messages=[{
                    "role": "user",
                    "content": PROMPT,
                    "images": [str(image_path)],
                }],
            )
            text = response["message"]["content"].strip()
            first_line = text.split("\n")[0].strip().upper()
            passed = "FAIL" not in first_line
            return passed, text[:200]
        except Exception as e:
            return True, f"moondream error ({e}) — treating as pass"

    def validate(self) -> tuple[bool, str]:
        """
        Render from three angles, check each with moondream.
        Returns (is_valid, summary_string).
        A design needs 2 of 3 renders to pass (majority vote).
        """
        results = []
        for label, loc, rot in CAMERAS:
            img = self._render_angle(label, loc, rot)
            if img is None:
                continue
            passed, reason = self._ask_moondream(img)
            results.append((label, passed, reason))

        if not results:
            return True, "No renders available — skipping visual check"

        pass_count = sum(1 for _, p, _ in results if p)
        fail_count = len(results) - pass_count
        majority_pass = pass_count >= (len(results) / 2)

        lines = [f"  {label}: {'PASS' if p else 'FAIL'} — {r}" for label, p, r in results]
        summary = f"{'PASS' if majority_pass else 'FAIL'} ({pass_count}/{len(results)} angles OK)\n" + "\n".join(lines)

        return majority_pass, summary
