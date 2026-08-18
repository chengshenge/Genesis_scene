# Genesis Scene Kit

A reusable Genesis scene toolkit extracted from our benchmark scene-generation pipeline. It focuses on strict RayTracer rendering, reproducible camera configuration, RobotSmith single-arm assets, structured outputs, and run manifests instead of publishing every experimental revision of each benchmark task.

![Ray-traced tabletop preview](docs/images/raytraced_tabletop_preview.png)

## What Is Included

- Explicit `raytracer` and `rasterizer` modes with no silent fallback for final rendering.
- Project-local Genesis, CUDA, OptiX, and LuisaRender cache directories.
- Reusable table, wall, target, transparent bowl, water surface, and visually identical block primitives.
- Optional RobotSmith xArm7 with a parallel gripper.
- RGB, GIF, and JSON manifest outputs recording the renderer, camera, runtime, and asset sources.

## Windows Quick Start

Python 3.11, an NVIDIA GPU, and a recent graphics driver are recommended. Run the following commands in PowerShell:

```powershell
git clone https://github.com/chengshenge/Genesis_scene.git
cd Genesis_scene

py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel

# Select the PyTorch CUDA wheel that matches your driver. Our tested environment uses cu128.
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
python -m pip install -e ".[dev]"

# The PyPI genesis-world package does not include a ready-to-use LuisaRenderPy build.
# This script checks out our tested Genesis commit and builds the Windows/CUDA RayTracer.
.\scripts\setup_raytracer_windows.ps1

git clone https://github.com/UMass-Embodied-AGI/RobotSmith .external/RobotSmith
$env:ROBOTSMITH_ROOT = (Resolve-Path .external/RobotSmith).Path
$env:GENESIS_SOURCE_ROOT = (Resolve-Path .external/Genesis).Path
$env:LUISA_RENDER_BUILD_BIN = (Resolve-Path .external/Genesis/genesis/ext/LuisaRender/build-win-cuda/bin/Release).Path

python scripts/check_environment.py --strict-raytracer
python examples/raytraced_tabletop.py --renderer raytracer --backend gpu --spp 16
```

The example writes the following files to `outputs/raytraced_tabletop/`:

```text
scene_rgb.png
scene_preview.gif
scene_manifest.json
generated_assets/open_bowl.obj
```

The first RayTracer run compiles Genesis kernels and shaders and creates several caches. Our first minimal smoke test took approximately five minutes on Windows with an RTX 3060 Ti; later runs reused the caches. Start with a small render while validating a new machine:

```powershell
python examples/raytraced_tabletop.py --no-robot --renderer raytracer --backend gpu --width 320 --height 180 --spp 1 --settle-steps 1
```

## Test Without RobotSmith

The base scene can be rendered without downloading RobotSmith:

```powershell
python examples/raytraced_tabletop.py --no-robot --renderer raytracer --backend gpu --spp 4
```

Use rasterizer mode explicitly when you only need to inspect geometry, camera framing, or object placement:

```powershell
python examples/raytraced_tabletop.py --no-robot --renderer rasterizer --backend gpu --width 640 --height 360
```

Rasterizer output is intended for debugging and should not be used as the final photoreal benchmark RGB input.

## Linux

Use the same installation sequence, but activate the virtual environment with:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

Install the PyTorch CUDA wheel that matches your driver, then run `pip install -e ".[dev]"`. RayTracer also requires a recursive Genesis clone and a LuisaRender build following `.external/Genesis/genesis/ext/LuisaRender/BUILD.md`. After building it, set:

```bash
export GENESIS_SOURCE_ROOT="$PWD/.external/Genesis"
export LUISA_RENDER_BUILD_BIN="$GENESIS_SOURCE_ROOT/genesis/ext/LuisaRender/build/bin"
```

## Create a New Scene

1. Copy `examples/raytraced_tabletop.py`.
2. Add task-specific assets, materials, poses, and collision geometry before `scene.build()`.
3. Adjust `CameraSpec`, then validate framing with a low resolution and low SPP.
4. Increase SPP for the final render and verify `renderer_effective`, `rasterizer_fallback_used`, and the runtime information in `scene_manifest.json`.
5. Do not commit downloaded BlenderKit or Objaverse binaries. Record asset IDs, sources, and licenses in `docs/ASSETS.md`.

See [docs/PIPELINE.md](docs/PIPELINE.md) for module boundaries and [docs/ASSETS.md](docs/ASSETS.md) for external asset conventions.

## Current Limitations

- Genesis RayTracer requires a separately built LuisaRender runtime and CUDA/OptiX. A normal `pip install genesis-world` installs the Python dependencies but does not complete the RayTracer setup.
- The example water is a visible transparent surface, not a full fluid simulation.
- RobotSmith and BlenderKit assets remain subject to their upstream licenses and are not redistributed here.
- This repository does not currently declare an open-source license. The maintainer should add an appropriate `LICENSE` before distributing it outside the intended group.
