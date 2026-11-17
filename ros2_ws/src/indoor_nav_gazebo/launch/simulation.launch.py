"""Phase 1 — Gazebo simulation.

Starts the indoor world, the Gazebo <-> ROS bridge and spawns the robot.
Readiness gate for this phase (checked by run_system.sh): /odom and /clock
flowing, robot visible in /odom at the spawn pose.
"""

from pathlib import Path
import os

from launch import LaunchDescription
from launch.actions import ExecuteProcess
from launch_ros.actions import Node


def generate_launch_description():
    # Pin Gazebo Transport to loopback. Without this, gz transport can pick a
    # DOWN interface (e.g. unplugged ethernet) for its discovery multicast and
    # silently drop every gz->ROS message (no /clock, /odom, /tf).
    os.environ["GZ_IP"] = "127.0.0.1"

    pkg_dir = Path(__file__).resolve().parent.parent

    # FYP_WORLD=<absolute path to an .sdf world> overrides the default indoor
    # world, e.g. the real-room replica generated from the reconstruction:
    #   FYP_WORLD=$FYP_ROOT/ros2_ws/src/indoor_nav_gazebo/worlds/realroom_world.sdf
    world = Path(
        os.environ.get(
            "FYP_WORLD", pkg_dir / "worlds" / "indoor_world.sdf"
        )
    ).expanduser()
    robot = pkg_dir / "models" / "fyp_robot" / "fyp_robot.sdf"

    gazebo = ExecuteProcess(
        cmd=[
            "gz",
            "sim",
            "-r",
            "-s",
            str(world),
        ],
        additional_env={"GZ_IP": "127.0.0.1"},
        output="screen",
    )

    bridge_topics = [
        "/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist",
        "/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry",
        "/tf@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V",
        "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock",
    ]
    # FYP_DEPTH_SOURCE=gazebo: also bridge the robot's simulated depth camera
    # (metres, 32FC1) and its intrinsics so localization.launch.py can build
    # /scan from it. Bridged only on request: a 640x480 float image at 15 Hz
    # costs CPU.
    if os.environ.get("FYP_DEPTH_SOURCE", "phone") == "gazebo":
        bridge_topics += [
            "/rgbd_camera/depth_image@sensor_msgs/msg/Image[gz.msgs.Image",
            "/rgbd_camera/camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo",
        ]

    bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        arguments=bridge_topics,
        output="screen",
    )

    spawn_robot = Node(
        package="ros_gz_sim",
        executable="create",
        arguments=[
            "-name",
            "fyp_robot",
            "-file",
            str(robot),
            # Spawn in open floor (obstacle_1 is 0.5 m from the world origin,
            # too close for a start pose with robot_radius 0.40). z=0.05 puts
            # the wheel bottoms (0.28 below base_link origin, model pose +0.25)
            # just above the floor so the robot settles without a hard drop.
            # FYP_SPAWN="x,y" overrides for custom worlds (real-room replica).
            "-x",
            os.environ.get("FYP_SPAWN_X", "0"),
            "-y",
            os.environ.get("FYP_SPAWN_Y", "-2"),
            "-z",
            # just above the 0.28 resting height: gentle settle,
            # no deep floor penetration (buried spawns jam the solver)
            "0.30",
        ],
        output="screen",
    )

    # base_link -> sim_depth_camera: the simulated rgbd sensor's position in
    # fyp_robot.sdf (link pose 0.31 0 0.10 + sensor pose 0.04 0 0), with body
    # axes (x forward along the optical axis, y left, z up). In gazebo depth
    # mode depth_to_scan publishes the levelled scan frame sim_depth_scan as
    # a child of this frame for every depth image.
    sim_camera_tf = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="base_to_sim_depth_camera_static",
        arguments=[
            "--x", "0.35",
            "--y", "0.0",
            "--z", "0.10",
            "--roll", "0",
            "--pitch", "0",
            "--yaw", "0",
            "--frame-id", "base_link",
            "--child-frame-id", "sim_depth_camera",
        ],
        output="screen",
    )

    # base_link -> camera_depth_frame (the virtual smartphone mount).
    camera_tf = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="base_to_camera_static",
        arguments=[
            "--x", "0.3",
            "--y", "0.0",
            "--z", "0.2",
            "--roll", "0",
            "--pitch", "0",
            "--yaw", "0",
            "--frame-id", "base_link",
            "--child-frame-id", "camera_depth_frame",
        ],
        output="screen",
    )

    actions = [gazebo, bridge, camera_tf, spawn_robot]
    if os.environ.get("FYP_DEPTH_SOURCE", "phone") == "gazebo":
        actions.insert(3, sim_camera_tf)  # only gazebo depth mode uses it
    return LaunchDescription(actions)
