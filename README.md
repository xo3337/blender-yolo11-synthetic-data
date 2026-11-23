# Blender YOLO11 Synthetic Data Pipeline

Generates a synthetic dataset for **YOLO11 pose / keypoint** training using Blender.
Every frame randomizes the lighting and the Geometry Nodes scatter, renders a 640×640 image,
and writes a YOLO pose label containing one bounding box and **8 keypoints** (the corners of
each object's 3D bounding box) for every visible part.

```
blender/yolo11.blend          Scene: camera, sun, Geometry Nodes spawner, part meshes
scripts/generate_dataset.py   Generation script (also embedded in the .blend as "Text")
```

## Requirements

- Blender 5.0+ (the .blend was saved with Blender 5.0)
- Git LFS, to clone the .blend file: `git lfs install` before cloning

## Running

1. Set `dataset_path` near the top of `scripts/generate_dataset.py` to your output folder.
2. Set `num_frames` (default `50000`).
3. Run it either way:
   - **GUI:** open `blender/yolo11.blend` → *Scripting* tab → open the script → *Run Script*.
   - **Headless (recommended for large runs):**

     ```powershell
     blender -b blender/yolo11.blend -P scripts/generate_dataset.py
     ```

Output:

```
<dataset_path>/
  images/gfframe_001.png ...
  labels/gfframe_001.txt ...
```

## What each frame does

1. **Sun light:** random color temperature (3000–7000 K), strength (1–7) and rotation
   (X in 0–π, Z in 0–2π).
2. **Scatter:** sets a new random seed on the Geometry Nodes modifier `dd` (input `Socket_5`)
   on `Plane.001`, which re-scatters the part instances.
3. **Render:** renders the image at 640×640.
4. **Labels:** for every instanced mesh, projects its 8 bounding-box corners into the camera
   and works out whether each corner can be seen.

## Label format

One line per object (YOLO pose format, all values normalized to 0–1):

```
class_id cx cy w h  x1 y1 v1  x2 y2 v2  ...  x8 y8 v8
```

- `class_id`: taken from the **source mesh object name**, which must be an integer (e.g. `0`, `1`, `2`).
  Objects with non-integer names are skipped.
- `cx cy w h`: the box enclosing the 8 projected keypoints.
- Visibility `v`:
  - `2`: visible
  - `1`: on screen but hidden behind something (found with a ray cast from the camera)
  - `0`: off screen or behind the camera (coordinates are clamped to 0–1)
- An object is left out entirely if all 8 of its keypoints are occluded (`v = 1`).

Example `data.yaml` for Ultralytics (set the class names to match your object names):

```yaml
path: C:/path/to/dataset
train: images
val: images
kpt_shape: [8, 3]
names:
  0: part_0
  1: part_1
```

## Scene requirements

The script expects these names in the .blend:

| Object      | Purpose                                                         |
|-------------|-----------------------------------------------------------------|
| `Camera`    | Render camera                                                   |
| `Sun`       | Sun light that gets randomized                                  |
| `Plane.001` | Spawner with a Geometry Nodes modifier named `dd`               |
| `dd` → `Socket_5` | The exposed seed input of the scatter node tree           |

## Tuning

- `RAYCAST_TOLERANCE` (default `0.0001`): stops the ray from hitting the corner's own surface.
- `MIN_TEMP`, `MAX_TEMP`, `MIN_ENERGY`, `MAX_ENERGY`, `MIN_ROT_X`, `MAX_ROT_X`: lighting ranges.
- `scene.render.resolution_x / _y`: image size.
