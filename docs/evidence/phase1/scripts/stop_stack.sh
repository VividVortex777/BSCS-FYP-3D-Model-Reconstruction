#!/bin/bash
# Stops the processes started by run_system.sh for this test, by PID.
patterns=(
  "ros2 launch indoor_nav" "simulation.launch.py" "localization.launch.py"
  "navigation.launch.py" "gz sim -r -s" "gz-sim-main" "ros_gz_bridge" "ros_gz_sim"
  "depth_bridge_node" "depth_to_scan" "depth_pipeline_node" "pointcloud_costmap_layer"
  "nav2_" "lifecycle_manager" "static_transform_publisher" "map_server" "amcl"
  "controller_server" "planner_server" "behavior_server" "bt_navigator"
  "test_backend_pipeline" "uvicorn backend.api.main:app" "depthimage_to_laserscan"
  "ros2 action send_goal" "phase1_pose_log.py" "phase1_amcl_trace.py" "trial_probe.py" "_ros2_daemon"
)
self=$$; parent=$PPID
pids=()
for p in "${patterns[@]}"; do
  while read -r pid; do
    [ -n "$pid" ] && [ "$pid" != "$self" ] && [ "$pid" != "$parent" ] && pids+=("$pid")
  done < <(pgrep -f -- "$p")
done
mapfile -t pids < <(printf '%s\n' "${pids[@]}" | sort -un)
[ ${#pids[@]} -eq 0 ] && { echo "nothing to stop"; exit 0; }
echo "stopping ${#pids[@]} processes"
kill -INT "${pids[@]}" 2>/dev/null; sleep 5
left=(); for pid in "${pids[@]}"; do kill -0 "$pid" 2>/dev/null && left+=("$pid"); done
[ ${#left[@]} -gt 0 ] && { kill -TERM "${left[@]}" 2>/dev/null; sleep 3; }
left=(); for pid in "${pids[@]}"; do kill -0 "$pid" 2>/dev/null && left+=("$pid"); done
[ ${#left[@]} -gt 0 ] && { kill -KILL "${left[@]}" 2>/dev/null; sleep 1; }
echo "remaining: $(for p in "${patterns[@]}"; do pgrep -f -- "$p"; done | grep -vx "$self" | grep -vx "$parent" | sort -u | wc -l)"
