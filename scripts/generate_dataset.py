import bpy
import mathutils
import bpy_extras
from mathutils import Vector
import os
import random
import math
import numpy as np

# --- Set Raycast Tolerance ---
RAYCAST_TOLERANCE = 0.0001 

# -----------------------------
## 1. Dataset Path Configuration
# -----------------------------
dataset_path = r"C:\Users\SAMI\Downloads\test_testy" 
images_path = os.path.join(dataset_path, "images")
labels_path = os.path.join(dataset_path, "labels")

os.makedirs(images_path, exist_ok=True)
os.makedirs(labels_path, exist_ok=True)

# -----------------------------
## 3. Scene and Object Setup
# -----------------------------
scene = bpy.context.scene
cam = bpy.data.objects.get("Camera")
spawner_obj = bpy.data.objects.get("Plane.001")
gn_mod = spawner_obj.modifiers.get("dd") 
light_obj = bpy.data.objects.get("Sun")

if cam is None: raise ValueError("Camera object not found in the scene.")
if spawner_obj is None: raise ValueError("Spawner object 'Plane.001' not found.")
if gn_mod is None: raise ValueError("Geometry Nodes modifier 'dd' not found on the spawner object.")
if light_obj is None: raise ValueError("Light object named 'Sun' not found.")
# --- Set Render Resolution ---
scene.render.resolution_x = 640
scene.render.resolution_y = 640
scene.render.resolution_percentage = 100 # Ensure it's rendered at full resolution
# -----------------------------

# Randomization
MIN_TEMP = 3000.0 
MAX_TEMP = 7000.0 
MIN_ENERGY = 1.0  
MAX_ENERGY = 7.0  
MIN_ROT_X = 0 * math.pi 
MAX_ROT_X = 1 * math.pi 

# -----------------------------
## 4. Helper: Get Spawned Parts
# -----------------------------
def get_spawned_parts():
    depsgraph = bpy.context.evaluated_depsgraph_get()
    parts = []
    for inst in depsgraph.object_instances:
        if inst.is_instance and inst.instance_object:
            src = inst.instance_object      
            if src.type == "MESH":
                parts.append({
                    "name": src.name,
                    "object": src,
                    "matrix_world": inst.matrix_world.copy()
                })
    return parts

# -----------------------------
## 5. Keypoint Function
# -----------------------------
def get_8_points(part, cam, scene):
    obj = part["object"]
    matrix_world = part["matrix_world"]
    cam_loc = cam.matrix_world.translation

    try:
        dg = bpy.context.evaluated_depsgraph_get()
    except:
        dg = bpy.context.view_layer.depsgraph
    
    point_properties = []
    
    for kpt_index, corner_local in enumerate(obj.bound_box):
        corner_world = matrix_world @ Vector(corner_local)
        co = bpy_extras.object_utils.world_to_camera_view(scene, cam, corner_world)
        
        x, y, z = co.x, co.y, co.z
        visibility_flag = 2 # visible

        is_on_screen_and_in_front = (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 and z >= 0.0)
        
        if not is_on_screen_and_in_front:
            visibility_flag = 0 
            x_norm = max(0.0, min(1.0, x))
            y_norm = max(0.0, min(1.0, y))
        else:
            x_norm = x
            y_norm = y
            
            cam_ray_direction = (corner_world - cam_loc).normalized()
            cam_ray_distance = (corner_world - cam_loc).length
            
            hit, _, _, _, hit_object, _ = scene.ray_cast(
                dg, cam_loc, cam_ray_direction, distance=cam_ray_distance - RAYCAST_TOLERANCE
            )
            
            if hit and hit_object is not None:
                visibility_flag = 1 # occluded

        point_properties.append({
            'x_norm': x_norm,
            'y_norm': y_norm,
            'v': visibility_flag,
        })

    final_pts = []
    for p in point_properties:
        final_pts.append((p['x_norm'], 1.0 - p['y_norm'], p['v']))
        
    return final_pts


# -----------------------------
## 6. Main Loop
# -----------------------------
num_frames = 50000

print(f"--- Starting generation of {num_frames} frames ---")

for frame in range(1, num_frames + 1):
    
    random_temp = random.uniform(MIN_TEMP, MAX_TEMP)
    light_obj.data.temperature = random_temp
    light_obj.data.use_nodes = False 

    random_energy = random.uniform(MIN_ENERGY, MAX_ENERGY)
    light_obj.data.energy = random_energy
    
    random_rotation_x = random.uniform(MIN_ROT_X, MAX_ROT_X)
    random_rotation_z = random.uniform(0, 2 * math.pi)
    
    light_obj.rotation_euler.x = random_rotation_x
    light_obj.rotation_euler.z = random_rotation_z 
    
    try:
        gn_mod["Socket_5"] = random.randint(0, 9999999)
        seed_value = gn_mod["Socket_5"]
    except KeyError:
        raise KeyError(
            "The key 'Socket_5' was not found. Check the exposed 'Seed' input on the modifier."
        )
    
    spawner_obj.data.update()  
    spawner_obj.update_tag()
    bpy.context.view_layer.update()

    scene.frame_set(frame)

    parts = get_spawned_parts()

    image_path = os.path.join(images_path, f"gfframe_{frame:03d}.png")
    scene.render.filepath = image_path
    bpy.ops.render.render(write_still=True)

    label_path = os.path.join(labels_path, f"gfframe_{frame:03d}.txt")
    
    print(f"[Frame {frame:03d}/{num_frames}] Energy: {random_energy:.1f}, Temp: {random_temp:.0f}K, Seed: {seed_value}, Parts: {len(parts)}")

    with open(label_path, "w") as f:
        for part in parts:
            class_name = part["name"]
            
            try:
                class_id = int(class_name) 
            except ValueError:
                print(f"ERROR: Object name '{class_name}' is not a valid integer class ID. Skipping.")
                continue
            
            pts = get_8_points(part, cam, scene)

            # -------------------------------------------------------
            # ✅ SKIP OBJECT IF ALL 8 KEYPOINTS HAVE v = 1 (occluded)
            # -------------------------------------------------------
            all_v1 = all(p[2] == 1 for p in pts)
            if all_v1:
                print(f"SKIPPED {class_name}: all 8 points occluded (v=1)")
                continue
            # -------------------------------------------------------

            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)
            
            bbox_cx = (x_min + x_max) / 2
            bbox_cy = (y_min + y_max) / 2
            bbox_w = x_max - x_min
            bbox_h = y_max - y_min
            
            flat = []
            for x, y, v in pts:
                flat.append(f"{x:.6f}")
                flat.append(f"{y:.6f}")
                flat.append(f"{v}")
                
            line = f"{class_id} {bbox_cx:.6f} {bbox_cy:.6f} {bbox_w:.6f} {bbox_h:.6f} " + " ".join(flat)
            f.write(line + "\n")

    print(f"[Frame {frame:03d}] Done. Parts: {len(parts)}, Seed: {seed_value}")

print("\n✅ Dataset generation complete!")

