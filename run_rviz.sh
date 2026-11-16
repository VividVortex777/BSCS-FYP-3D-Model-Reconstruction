#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/scripts/fyp_env.sh"

# Launch RViz2 for visualization

set -e

cd "$FYP_ROOT"

# Source ROS2
source /opt/ros/lyrical/setup.bash
source ros2_ws/install/setup.bash

echo "======================================="
echo "Launching RViz2"
echo "======================================="
echo

echo "Add these displays in RViz2:"
echo "  - Map (topic: /map)"
echo "  - RobotModel (TF)"
echo "  - LaserScan (topic: /scan)"
echo "  - Path (topic: /plan)"
echo "  - LocalCostmap (topic: /local_costmap/costmap)"
echo "  - GlobalCostmap (topic: /global_costmap/costmap)"
echo

echo "Set Fixed Frame to: map"
echo

rviz2
