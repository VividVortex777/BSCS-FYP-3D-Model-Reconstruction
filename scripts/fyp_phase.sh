#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/fyp_env.sh"
# Launch one phase of the FYP stack in its own detached session.
# Usage: fyp_phase.sh <"ros2 launch args"> <logfile>
source /opt/ros/lyrical/setup.bash
source "$FYP_ROOT/ros2_ws/install/setup.bash"
export GZ_SIM_RESOURCE_PATH="$GZ_SIM_RESOURCE_PATH:$FYP_ROOT/ros2_ws/src/indoor_nav_gazebo/models"
# Pin Gazebo Transport discovery to loopback: a DOWN ethernet interface can
# otherwise be selected for multicast and silently drop all gz<->ROS data.
export GZ_IP=127.0.0.1
cd "$FYP_ROOT"
exec ros2 launch "$@"
