"""Phase 2 — Smartphone depth pipeline + AMCL localization.

Starts the smartphone depth bridge (FastAPI -> ROS), the depth-to-scan
converter, the map server and AMCL. Readiness gate for this phase (checked by
run_system.sh): /scan flowing from live MiDaS depth AND map -> odom
broadcast by AMCL.

Note for bringup order: /scan only flows once an Android phone (or the test
phone simulator) streams frames to the backend and MiDaS produces depth.
Starting this phase without any camera stream still brings AMCL up with its
configured initial pose, but /scan stays silent and the navigation phase must
not be started before depth data appears.
"""

import os
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    # Resolved from the installed package so the launch works from any clone
    # location (with --symlink-install these are the files in src/).
    pkg_share = Path(get_package_share_directory("indoor_nav_costmap"))
    params_file = str(pkg_share / "config" / "nav2_params.yaml")
    # Map can be overridden, e.g. a map generated from the real-room
    # reconstruction: FYP_MAP=$FYP_ROOT/realroom/realroom_map.yaml
    map_file = os.environ.get(
        "FYP_MAP",
        str(pkg_share / "maps" / "indoor_map.yaml"),
    )
    # AMCL initial pose override for non-default maps: FYP_INITIAL_POSE="x,y"
    _ip = os.environ.get("FYP_INITIAL_POSE", "0.0,-2.0").split(",")
    initial_pose = (float(_ip[0]), float(_ip[1]))

    backend_url = os.environ.get(
        "FYP_BACKEND_URL",
        "http://127.0.0.1:8000/latest-depth-image",
    )

    depth_bridge = Node(
        package="smartphone_depth_bridge",
        executable="depth_bridge_node",
        output="screen",
        parameters=[
            {
                "backend_url": backend_url,
                "depth_topic": "/smartphone/depth",
                "depth_frame_id": "camera_depth_frame",
                "use_sim_time": True,
                # Recorded-video test: phone is disconnected after capture,
                # keep republishing the last phone-derived MiDaS depth frame.
                "republish_stale": os.environ.get(
                    "FYP_DEPTH_REPUBLISH_STALE", "0"
                )
                == "1",
            }
        ],
    )

    # Which depth feeds /scan (and therefore AMCL):
    #   FYP_DEPTH_SOURCE=phone   (default) MiDaS depth from the smartphone
    #                            stream via the backend.
    #   FYP_DEPTH_SOURCE=gazebo  the simulated robot's depth camera, so AMCL
    #                            sees the same room that Gazebo simulates.
    #                            simulation.launch.py must be started with the
    #                            same setting (it bridges the camera).
    depth_source = os.environ.get("FYP_DEPTH_SOURCE", "phone")
    if depth_source not in ("phone", "gazebo"):
        raise ValueError(
            f"FYP_DEPTH_SOURCE must be 'phone' or 'gazebo', got {depth_source!r}"
        )

    if depth_source == "gazebo":
        scan_params = {
            "depth_topic": "/rgbd_camera/depth_image",     # 32FC1, metres
            "camera_info_topic": "/rgbd_camera/camera_info",
            "depth_mode": "metric",
            # Rigid camera frame (simulation.launch.py, base_link + 0.35/0/0.10)
            "camera_frame": "sim_depth_camera",
            # Levelled scan frame, published by depth_to_scan per image:
            # camera position and heading, roll/pitch removed.
            "scan_frame_id": "sim_depth_scan",
            # odom is gravity-aligned in Gazebo (the odometry plugin reports
            # the true pose), so it gives the camera's real roll and pitch.
            "level_reference_frame": "odom",
            # Accept rays rising 1.1 deg to 8.6 deg above horizontal: never
            # the floor; at 5.5 m they sample 0.11 m to 0.83 m above the
            # camera (~0.28 m), i.e. walls (3 m) and obstacles (>= 1 m).
            "min_elevation_rad": 0.02,
            "max_elevation_rad": 0.15,
            "target_beams": 160,
            "pixel_stride": 2,
            "min_range": 0.15,
            "obstacle_max_range": 3.0,
            # Must match the rgbd sensor's far clip (8 m).
            "clearing_max_range": 8.0,
        }
    else:
        scan_params = {
            "depth_topic": "/smartphone/depth",
            "scan_frame_id": "base_link",
            "inverse_depth": True,
            "min_range": 0.15,
            "obstacle_max_range": 3.0,
            "clearing_max_range": 3.5,
            # MiDaS depth is relative; anchor the nearest visible surface
            # at this distance instead of min_range so walls are not
            # permanently reported as bumper-distance obstacles.
            "near_range_anchor": 2.00,
        }

    depth_to_scan = Node(
        package="indoor_nav_costmap",
        executable="depth_to_scan",
        output="screen",
        parameters=[
            {
                "scan_topic": "/scan",
                **scan_params,
                "use_sim_time": True,
            }
        ],
    )

    map_server = Node(
        package="nav2_map_server",
        executable="map_server",
        name="map_server",
        output="screen",
        parameters=[
            {
                "yaml_filename": map_file,
                "use_sim_time": True,
            }
        ],
    )

    amcl_params = [
        params_file,
        {"set_initial_pose": True, "initial_pose.x": initial_pose[0], "initial_pose.y": initial_pose[1]},
    ]
    if depth_source == "gazebo":
        # Simulation-only AMCL tuning (phone mode keeps nav2_params.yaml).
        # Gazebo's odometry plugin reports the true pose (measured: /odom ==
        # ground truth), whereas the defaults (alpha 0.2, update every 0.25 m
        # / 0.2 rad) are sized for real wheel slip. With them the particle
        # cloud spread to 1-sigma 0.23 m (x) / 0.34 m (y) over a 2.5 m drive,
        # more than the 0.15 m goal requirement.
        amcl_params.append(
            {
                # Motion-model noise 10x below default: small, not zero, so
                # the filter can still absorb residual model/TF timing error.
                "alpha1": 0.02,   # rotation noise from rotation
                "alpha2": 0.02,   # rotation noise from translation
                "alpha3": 0.02,   # translation noise from translation
                "alpha4": 0.02,   # translation noise from rotation
                # Correct every 5 cm / ~3 deg instead of 25 cm / 11 deg.
                "update_min_d": 0.05,
                "update_min_a": 0.05,
                # 5x more filter updates: resample every 2nd update to avoid
                # particle depletion from repeated, correlated scan weights.
                "resample_interval": 2,
                # Measured scan error vs the world: median 1.2 cm, p95 4.4 cm;
                # map resolution 5 cm. 0.2 m makes the likelihood too flat to
                # pull the estimate onto walls; 0.1 m is still 2 map cells.
                "sigma_hit": 0.1,
            }
        )

    amcl = Node(
        package="nav2_amcl",
        executable="amcl",
        name="amcl",
        output="screen",
        parameters=amcl_params,
        remappings=[("scan", "/scan")],
    )

    # Report Stage 3 + 4: depth -> 3D point cloud -> filtering -> 2D
    # occupancy grid. This is the report-defined perception representation.
    depth_pipeline = Node(
        package="indoor_nav_costmap",
        executable="depth_pipeline_node",
        output="screen",
        parameters=[
            {
                "depth_topic": "/smartphone/depth",
                "pointcloud_topic": "/camera/depth/points",
                "grid_topic": "/depth_occupancy_grid",
                "frame_id": "camera_depth_frame",
                "use_sim_time": True,
            }
        ],
    )

    # Report representation -> Nav2: republishes the depth-derived occupancy
    # grid as /smartphone_map (static-layer wire format + updates stream) so
    # both costmaps consume the report pipeline's map instead of /scan.
    grid_bridge = Node(
        package="indoor_nav_costmap",
        executable="pointcloud_costmap_layer",
        output="screen",
        parameters=[
            {
                "grid_topic": "/depth_occupancy_grid",
                "pointcloud_topic": "/camera/depth/points",
                "map_topic": "/smartphone_map",
                "use_sim_time": True,
            }
        ],
    )

    localization_manager = Node(
        package="nav2_lifecycle_manager",
        executable="lifecycle_manager",
        name="lifecycle_manager_localization",
        output="screen",
        parameters=[
            {
                "autostart": True,
                "node_names": ["map_server", "amcl"],
                "use_sim_time": True,
            }
        ],
    )

    return LaunchDescription(
        [
            depth_bridge,
            depth_to_scan,
            depth_pipeline,
            grid_bridge,
            map_server,
            amcl,
            localization_manager,
        ]
    )
