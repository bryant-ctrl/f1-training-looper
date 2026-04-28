"""
One-time helper: rename objects in your Blender scene so blender_bridge.py
can find them by the expected names.

Run this BEFORE starting the optimization loop:
  uv run python setup_model.py

It connects to the running blender-mcp server, lists all objects, and lets
you pick which one is the front wing, rear wing, etc.
"""

from blender_bridge import BlenderBridge


def list_objects(bridge: BlenderBridge) -> list[str]:
    bridge._send(
        "import bpy\n"
        "names = [o.name for o in bpy.data.objects]\n"
        "print('OBJECTS:', names)\n"
    )
    # blender-mcp returns stdout in the result; parse it out
    resp = bridge._send(
        "import bpy, json\n"
        "names = [o.name for o in bpy.data.objects]\n"
        "import sys; print(json.dumps(names))\n"
    )
    import json
    return json.loads(resp.get("result", "[]").strip())


def rename_object(bridge: BlenderBridge, old_name: str, new_name: str) -> None:
    bridge._send(
        f"import bpy\n"
        f"obj = bpy.data.objects.get('{old_name}')\n"
        f"if obj: obj.name = '{new_name}'\n"
    )
    print(f"  Renamed '{old_name}' → '{new_name}'")


REQUIRED = ["front_wing", "rear_wing", "diffuser", "floor", "car_body"]


def main():
    bridge = BlenderBridge()
    if not bridge.ping():
        print("ERROR: Cannot reach Blender MCP server.")
        print("Open Blender, enable the blender-mcp addon, and click 'Start MCP Server'.")
        return

    objects = list_objects(bridge)
    print("\nObjects in your Blender scene:")
    for i, name in enumerate(objects):
        print(f"  [{i}] {name}")

    print("\nYou need to map these 5 required names:")
    for req in REQUIRED:
        print(f"  {req}")

    print("\nFor each required name, enter the NUMBER of the matching object.")
    print("Press Enter to skip if not applicable.\n")

    for req in REQUIRED:
        raw = input(f"Which object is '{req}'? (number or Enter to skip): ").strip()
        if raw.isdigit():
            idx = int(raw)
            if 0 <= idx < len(objects):
                rename_object(bridge, objects[idx], req)
        else:
            print(f"  Skipped '{req}'")

    print("\nDone. Object names saved in Blender.")
    print("Save the .blend file now to preserve these names for future sessions.")


if __name__ == "__main__":
    main()
