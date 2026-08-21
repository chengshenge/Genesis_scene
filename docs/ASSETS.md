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

## Reference robot, paper, can, and pen task

`tasks/reference_robot_paper_can_pen.json` expects these third-party assets. The files are intentionally not committed.

| Role | Source / ID | Expected path |
| --- | --- | --- |
| White work table | RoboWits `work_table.glb` | `assets/downloaded/robowits/work_table.glb` |
| Table normal | RoboWits `grained black plastic_Normal.jpg` | `assets/downloaded/robowits/worktable_texture/grained black plastic_Normal.jpg` |
| Table roughness | RoboWits `grained black plastic_Roughness.jpg` | `assets/downloaded/robowits/worktable_texture/grained black plastic_Roughness.jpg` |
| A4 paper | BlenderKit `41aebdc7-0c53-4197-98eb-5f6d4a80116a` | `assets/downloaded/blenderkit/41aebdc7-0c53-4197-98eb-5f6d4a80116a/obj.glb` |
| Red scanned can | BlenderKit `f52953ee-cb81-434d-a6ac-0008bff15508` | `assets/downloaded/blenderkit/f52953ee-cb81-434d-a6ac-0008bff15508/reference_scanned_tall_red_food_can.glb` |
| Ballpoint pen | BlenderKit `2f2c9c79-09c6-44de-9b3f-ae3e2bd3230c` | `assets/downloaded/blenderkit/2f2c9c79-09c6-44de-9b3f-ae3e2bd3230c/obj.glb` |

The can path refers to a prepared GLB exported from the BlenderKit 2K source with its scan geometry and normal map
preserved and the label stock color-adjusted to red. Preparing it is a content pipeline step, not a Genesis primitive
replacement. Keep the BlenderKit metadata and license record beside downloaded source files.

Robot geometry, the carpet, and the HDR environment come from the RobotSmith checkout described above. The task
runner splits the xArm GLB's asset-native white and silver material primitives without recomputing vertex normals.
