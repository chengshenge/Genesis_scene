# Pipeline structure

The repository separates reusable infrastructure from task-specific scene code:

1. `RuntimeConfig` configures project-local caches, prefers an optional local Genesis checkout, and adds the compiled LuisaRender runtime before Genesis is imported.
2. `RenderSpec` creates either an explicit RayTracer scene or an explicit rasterizer diagnostic scene.
3. Reusable scene primitives add the table, target, blocks, bowl, and water surface.
4. The example adds optional RobotSmith xArm geometry and places it with Genesis IK.
5. A Genesis camera renders RGB frames and the run writes a manifest beside the image/GIF.

There is intentionally no silent RayTracer-to-rasterizer fallback. A failed RayTracer run should be fixed at the CUDA/OptiX layer rather than accidentally accepted as a lower-quality benchmark render.

## Adding a new benchmark scene

Copy `examples/raytraced_tabletop.py` and change only these task-specific parts:

- object assets, dimensions, materials, and initial poses;
- camera `pos`, `lookat`, `up`, and `fov`;
- robot ready pose or task trajectory;
- success checks and task metadata in the manifest.

Keep runtime setup, renderer construction, output naming, and manifest fields shared. External visual meshes should use a visual entity plus a separately validated collision representation when the visual mesh is non-convex.

## Rendering profiles

- `raytracer`: final RGB collection. Requires NVIDIA CUDA/OptiX and uses LuisaRender `wavepath`.
- `rasterizer`: fast geometry/camera debugging only. It should not be used as the final photoreal benchmark input.
