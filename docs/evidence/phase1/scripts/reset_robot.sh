#!/bin/bash
# Put fyp_robot back at the spawn pose (0, -2, yaw 0) and re-initialise AMCL there.
source /opt/ros/lyrical/setup.bash
export GZ_IP=127.0.0.1 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
timeout 10 gz service -s /world/indoor_world/set_pose --reqtype gz.msgs.Pose --reptype gz.msgs.Boolean \
  --timeout 3000 --req 'name: "fyp_robot", position: {x: 0.0, y: -2.0, z: 0.30}, orientation: {w: 1.0}'
sleep 6   # let it settle onto its wheels/casters
timeout 10 ros2 topic pub --once /initialpose geometry_msgs/msg/PoseWithCovarianceStamped \
  "{header: {frame_id: map}, pose: {pose: {position: {x: 0.0, y: -2.0}, orientation: {w: 1.0}},
    covariance: [0.0025,0,0,0,0,0, 0,0.0025,0,0,0,0, 0,0,0,0,0,0, 0,0,0,0,0,0, 0,0,0,0,0,0, 0,0,0,0,0,0.0003]}}" > /dev/null
sleep 3
timeout 10 gz topic -e -t /world/indoor_world/pose/info -n 1 2>/dev/null | grep -A6 'name: "fyp_robot"' | grep -E ' x:| y:' | head -2 | tr '\n' ' '
echo
