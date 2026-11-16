#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/fyp_env.sh"
source /opt/ros/lyrical/setup.bash
source $FYP_ROOT/ros2_ws/install/setup.bash
export GZ_SIM_RESOURCE_PATH="$GZ_SIM_RESOURCE_PATH:$FYP_ROOT/ros2_ws/src/indoor_nav_gazebo/models"
cd "$FYP_ROOT"
setsid nohup ros2 launch indoor_nav_gazebo simulation.launch.py > /tmp/fyp_sim3.log 2>&1 &
sleep 25
setsid nohup ros2 launch indoor_nav_costmap localization.launch.py > /tmp/fyp_loc3.log 2>&1 &
sleep 35
setsid nohup ros2 launch indoor_nav_costmap navigation.launch.py > /tmp/fyp_nav3.log 2>&1 &
echo "bringup sequence launched"
