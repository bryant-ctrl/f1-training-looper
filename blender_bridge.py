"""
Communicates with the blender-mcp socket server running inside Blender.

Setup:
  1. Install Blender: https://www.blender.org/download/
  2. Install the blender-mcp addon: https://github.com/ahujasid/blender-mcp
  3. In Blender: Edit > Preferences > Add-ons > install blender_mcp.zip
  4. Enable the addon, click "Start MCP Server" in the N-panel (sidebar)
  The server listens on localhost:9876 by default.

Object naming convention (set these up once in Blender before running):
  front_wing   — front wing assembly
  rear_wing    — rear wing main plane
  diffuser     — rear diffuser
  floor        — floor/plank assembly
  car_body     — everything else (chassis, sidepods, etc.)

Run setup_model.py once after loading your Sketchfab model to rename objects.
"""

import json
import socket
import tempfile
from pathlib import Path


BLENDER_HOST = "localhost"
BLENDER_PORT = 9876


class BlenderBridge:
    def _send(self, code: str) -> dict:
        """Send a Python snippet to Blender and return the response."""
        payload = json.dumps({"type": "execute_code", "code": code})
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(60)
            try:
                s.connect((BLENDER_HOST, BLENDER_PORT))
            except ConnectionRefusedError:
                raise RuntimeError(
                    "Cannot connect to Blender MCP server on port 9876.\n"
                    "Make sure Blender is open and the MCP server is started\n"
                    "(N-panel > MCP > Start MCP Server)."
                )
            s.sendall((payload + "\n").encode())
            chunks = []
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
                if b"\n" in chunk:
                    break
            response = json.loads(b"".join(chunks).strip())
        if not response.get("success", False):
            raise RuntimeError(f"Blender error: {response.get('error', 'unknown')}")
        return response

    def ping(self) -> bool:
        try:
            self._send("print('ping')")
            return True
        except Exception:
            return False

    def load_model(self, model_path: Path) -> None:
        path_str = str(model_path).replace("\\", "/")
        ext = model_path.suffix.lower()
        if ext == ".obj":
            code = f"import bpy; bpy.ops.wm.obj_import(filepath='{path_str}')"
        elif ext in (".fbx",):
            code = f"import bpy; bpy.ops.import_scene.fbx(filepath='{path_str}')"
        elif ext == ".blend":
            code = f"import bpy; bpy.ops.wm.open_mainfile(filepath='{path_str}')"
        else:
            raise ValueError(f"Unsupported model format: {ext}")
        self._send(code)
        print(f"Loaded model: {model_path.name}")

    def apply_params(self, params: dict) -> None:
        """Apply design parameter changes to the Blender scene."""
        code = f"""
import bpy, math

params = {json.dumps(params)}

def set_rotation_x(obj_name, angle_deg):
    obj = bpy.data.objects.get(obj_name)
    if obj:
        obj.rotation_euler[0] = math.radians(angle_deg)

def set_z(obj_name, z_mm):
    obj = bpy.data.objects.get(obj_name)
    if obj:
        obj.location.z = z_mm / 1000.0  # mm to metres

set_rotation_x('front_wing', params.get('front_wing_main_angle', 12))
set_rotation_x('rear_wing',  params.get('rear_wing_main_angle',  12))
set_rotation_x('diffuser',   params.get('diffuser_angle',         8))

# Ride height: move whole car on Z using 'car_body' as the root
set_z('car_body', params.get('front_ride_height', 40))

# Update the scene
bpy.context.view_layer.update()
print('params applied')
"""
        self._send(code)

    def export_stl(self, job_id: str, output_dir: Path) -> Path:
        """Export the current scene as a single STL file."""
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"{job_id}.stl"
        path_str = str(out_path).replace("\\", "/")
        code = f"""
import bpy
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_mesh.stl(filepath='{path_str}', use_selection=True)
print('exported')
"""
        self._send(code)
        if not out_path.exists():
            raise RuntimeError(f"STL export failed — file not found at {out_path}")
        return out_path

    def reset_to_base(self) -> None:
        """Revert all objects to their base transform (saved on first load)."""
        self._send(
            "import bpy\n"
            "for obj in bpy.data.objects:\n"
            "    obj.rotation_euler = (0, 0, 0)\n"
            "bpy.context.view_layer.update()\n"
        )
