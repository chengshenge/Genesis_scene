# External assets

Third-party binary assets are not committed to this repository. This avoids mixing asset licenses with the source code and keeps the clone small.

## RobotSmith

The single-arm example expects:

```text
.external/RobotSmith/assets/xarm7_with_gripper_reduced_dof.urdf
.external/RobotSmith/assets/hdr.hdr
```

Clone [UMass-Embodied-AGI/RobotSmith](https://github.com/UMass-Embodied-AGI/RobotSmith) into `.external/RobotSmith`, or set `ROBOTSMITH_ROOT` to an existing checkout.

## BlenderKit references used by our internal scenes

- Transparent bowl: `6bd92939-0d93-49e8-bbf6-0a8beda6de0e`
- Steel mug: `da62c1a3-ce76-4bb9-8881-6f06729a92d2`

Download them through BlenderKit under your own account and verify the asset license before redistribution. Prefer storing downloaded files under `assets/downloaded/`, which is ignored by Git.
