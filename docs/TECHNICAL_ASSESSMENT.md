# Technical Assessment and Development Roadmap

Date: 2026-11-12
Assessed commit: `631e20e` (branch `master`)

## Scope and method

The whole repository was read without changing, installing or running anything.
Every finding below comes from reading code and documentation, not from
executing the system. Items marked "needs confirming" are inferences that must
be checked at runtime before they are treated as fact.

**Bottom line:** the live pipeline exists in code up to the ROS depth topic,
but live depth never reaches Nav2's costmaps. Navigation runs on a pre-built
static map with ground-truth odometry. Nothing can run on the current
development machine yet.

## 1. State of the development machine

| Item | Found |
|---|---|
| OS / ROS | Ubuntu 26.04.1, ROS 2 Lyrical with Nav2, `slam_toolbox`, `rtabmap_ros`, `depthimage_to_laserscan` |
| GPU | RTX 4050, 6 GB, driver 595.99 loaded |
| Python | System 3.14.4 with no `torch`, `fastapi`, `uvicorn` or `websockets`; no conda |
| Other tools | COLMAP 3.12.6, ffmpeg, adb and colcon are installed |
| Missing | `MiDaS/` and its weights, a built `ros2_ws`, the `~/FYP` directory, test frames |
| Paths | About 20 files hardcode `/home/hammad/FYP` and about 40 assume `~/FYP`; the repo lives in `~/Projects/...` |

The README says the previous machine had no usable NVIDIA driver, so all
earlier timings (1–2 s per frame) are CPU figures. GPU performance is
unmeasured.

## 2. Live smartphone-streaming components

- **Backend:** `backend/api/main.py` accepts JPEG frames on `/ws/video`,
  answers UDP discovery (`FYP_DISCOVER_REQ` on port 51315), and runs MiDaS in a
  worker thread that keeps only the newest frame.
  `backend/depth/midas_processor.py` loads DPT-Hybrid-384.
- **Bridge:** `smartphone_depth_bridge/depth_bridge_node.py` polls
  `/latest-depth-image` over HTTP at 5 Hz and publishes `/smartphone/depth`.
- **Depth processing** (package `indoor_nav_costmap`): `depth_to_scan.py`,
  `depth_pipeline_node.py` (point cloud, filters, grid) and
  `pointcloud_costmap_layer.py` (persistent `/smartphone_map`).
- **Bring-up:** `simulation.launch.py`, `localization.launch.py`,
  `navigation.launch.py`, `run_system.sh`, and
  `scripts/test_backend_pipeline.py`, which fakes a phone by looping three
  saved frames.
- **Android app:** not in the repository. Scripts reference package
  `com.fyp.reconstruction`, and the docs point at the gitignored upstream MiDaS
  demo tree.

## 3. Recorded-video reconstruction components

- **Pipeline:** `scripts/fyp30_run_pipeline.sh` chains ffmpeg, frame selection,
  MiDaS batch, COLMAP, fusion, occupancy map, Gazebo world, and spawn/goal
  selection.
- **Navigation on the result:** `run_navigation.sh`,
  `scripts/fyp_realroom30_up.sh` and the `fyp30_*` demo and evidence scripts.
- **Hybrids:** `scripts/realroom_capture.py` and `scripts/fyp30_record30.py`
  record from the live stream, then disconnect the phone and go offline.

The README currently presents this pipeline as the project and calls the
backend a "live-input extension point". That contradicts the official FYP
direction and should be corrected.

## 4. FastAPI to ROS2 integration problems

1. **Live depth does not influence Nav2.** Both costmaps read `/map` from the
   static map server and have their obstacle layers disabled
   (`nav2_params.yaml:212-222` and `250-260`). Nothing subscribes to
   `/smartphone_map`; only AMCL uses `/scan`.
2. **Depth is crushed to 8 bits per frame.** Each frame is min-max normalised
   to 0–255 (`backend/api/main.py:142`), so the scale changes every frame and
   the raw MiDaS values are lost.
3. **The sequence header counts the wrong thing.** `X-FYP-Depth-Sequence` is
   the number of frames received, not depth maps produced
   (`backend/api/main.py:410`). The bridge republishes old depth as new and
   stamps it with poll time, so latency is invisible.
4. **Camera intrinsics are invented.** `fx=554.25, cx=320, cy=240` are fixed
   regardless of the phone's resolution (`depth_pipeline_node.py:148`); no
   `CameraInfo` is published.
5. **Likely 90° frame error (needs confirming in RViz).** The cloud uses the
   optical convention (z forward) but is published in `camera_depth_frame`,
   which is x-forward (`simulation.launch.py:84-97`). The map assembler then
   applies only a yaw, which would place obstacles ahead of the robot to its
   left.
6. **No metric scale.** MiDaS predicts inverse depth up to an unknown scale and
   shift (Ranftl et al., "Towards Robust Monocular Depth Estimation", TPAMI
   2022). The code maps it to metres with fixed anchors (2.0 m nearest, 3.5 m
   farthest), which is a heuristic rather than a measurement.

## 5. Missing functionality and risks

- **Conceptual gap (highest risk):** the phone sees a real room while the robot
  moves in Gazebo, and nothing ties the phone's pose to the simulated robot.
  The docs claim a live phone fixes the "drifting marks" problem; it does not
  unless the phone moves exactly as the simulated robot does.
- **No pose source for the phone:** live mapping needs camera poses; only the
  offline COLMAP path provides them.
- **Simulation is idealised:** the robot uses direct velocity control and
  odometry taken from its true pose (`fyp_robot.sdf:438-455`), so localisation
  is perfect by construction. This must be disclosed in the report.
- **Docs contradict evidence:** `realroom/capture_fresh/evidence/VERDICT.md`
  states that no pass is claimed and the earlier pass was a "phantom", yet the
  README says 3/3 legs reached and "demo-ready".
- **Safety config:** the collision monitor and velocity smoother are configured
  but never launched, and DWB allows 0.85 m/s on perception that updates a few
  times per second.
- **Dead and conflicting code:** `backend/main.py` and `backend/app.py` are
  leftovers, and four legacy nodes disagree on whether a high value means near
  or far. `depth_obstacle_node` publishes straight to `/cmd_vel`.
- **Reproducibility:** `backend/requirements.txt` lists three unpinned packages
  and omits torch, OpenCV and the rest. The only real tests are three unit
  tests for `depth_to_scan`. `package.xml` files omit dependencies such as
  `tf2_ros`.
- **Version risk:** whether PyTorch wheels exist for Python 3.14 has not been
  checked; verify before choosing the environment.

## 6. Roadmap

| Phase | Goal | Done when |
|---|---|---|
| 0. Baseline | Python env with CUDA torch, MiDaS weights, built workspace, hardcoded paths removed, Android source obtained from the original author | Backend serves depth from the test streamer; `colcon test` passes; GPU frame time measured |
| 1. Concept decision | Agree with the supervisor how the phone and simulator relate | Written one-page system definition |
| 2. Bridge contract | Send raw depth as 16-bit or float, a true depth sequence, capture timestamps, `CameraInfo`, and a correct optical frame | Cloud appears in front of the robot in RViz; end-to-end latency logged |
| 3. Closed-loop harness | Feed the Gazebo robot's camera through the backend; the robot model already has an unbridged RGB-D sensor giving ground-truth depth | MiDaS error reported against ground truth after scale-shift alignment |
| 4. Scale and costmap | Recover scale (ground plane with known camera height, or ARCore), then feed Nav2's obstacle or voxel layer | Robot avoids an obstacle that is absent from the static map |
| 5. Live phone mapping | Add a pose source (ARCore or RTAB-Map), build the map from the stream, reuse the existing map-to-world generator | A room streamed live becomes a map the robot navigates |
| 6. Evaluation and docs | Experiments, one consolidated status document, honest limitations | Report chapters backed by logged data |

### Recommendation for Phase 1

Adopt a two-stage design: a handheld phone streams live to build the map, then
the robot navigates that map in Gazebo. Phase 3's simulated camera is the
closed-loop test bed. This keeps the live objective, reuses the recorded
pipeline's world generator, and avoids pretending the phone rides on the
simulated robot. The alternative, mounting the phone on a real robot, needs
hardware the team does not have.
