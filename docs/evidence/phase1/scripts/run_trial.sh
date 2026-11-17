#!/bin/bash
# One independent repeatability trial: fresh stack -> checks -> goal (2,0) -> ground truth -> stop.
# Usage: run_trial.sh <run_number>     Appends one JSON line to results.jsonl.
N="$1"
S=/tmp/claude-1000/-home-muhammad-Projects/4e22b8f0-6118-47f0-bce3-83045ebbbdb8/scratchpad
R=~/Projects/fyp-smartphone-robot-navigation
D=$S/run$N; mkdir -p "$D"
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST FYP_DEPTH_SOURCE=gazebo GZ_IP=127.0.0.1
log() { echo "[run $N $(date +%T)] $*"; }

truth() {  # prints "x y" of fyp_robot from Gazebo's world pose
  timeout 10 gz topic -e -t /world/indoor_world/pose/info -n 1 2>/dev/null \
    | grep -A6 'name: "fyp_robot"' | grep -oE '^ +[xy]: -?[0-9.e-]+' | head -2 | awk '{printf "%s ", $2}'
}

log "clean state: stopping any previous stack"
bash $S/stop_stack.sh > "$D/stop_before.txt" 2>&1
ss -ltn | grep -q ':8000 ' && { log "port 8000 busy - abort"; exit 1; }

log "starting fresh stack (FYP_DEPTH_SOURCE=gazebo)"
cd $R && timeout 900 bash run_system.sh > "$D/run_system.out" 2>&1
cp /tmp/fyp_nav.launch.log "$D/nav_bringup.log" 2>/dev/null

source /opt/ros/lyrical/setup.bash
source $R/ros2_ws/install/setup.bash

log "pre-checks"
LIFE=""; ACTIVE=0
for n in map_server amcl controller_server planner_server behavior_server bt_navigator; do
  st=$(timeout 10 ros2 lifecycle get /$n 2>&1 | head -1); LIFE="$LIFE$n=$st;"
  echo "$st" | grep -q '^active' && ACTIVE=$((ACTIVE+1))
done
PARAMS=""
for p in alpha1 alpha2 alpha3 alpha4 update_min_d update_min_a resample_interval sigma_hit; do
  PARAMS="$PARAMS amcl.$p=$(timeout 8 ros2 param get /amcl $p 2>&1 | awk '{print $NF}')"
done
for p in general_goal_checker.xy_goal_tolerance general_goal_checker.yaw_goal_tolerance; do
  PARAMS="$PARAMS $p=$(timeout 8 ros2 param get /controller_server $p 2>&1 | awk '{print $NF}')"
done
RATES=$(/usr/bin/python3 $S/trial_probe.py rates 2>/dev/null)
TF=$(/usr/bin/python3 $S/tf_check.py 2>&1 | grep -cE '(odom -> base_link|map -> odom|base_link -> sim_depth_camera|sim_depth_camera -> sim_depth_scan) +OK')
INIT_TRUTH=$(truth)
INIT_AMCL=$(/usr/bin/python3 $S/amcl_cov.py 2>&1 | tail -1)
log "lifecycle active=$ACTIVE/6 tf_ok=$TF/4 rates=$RATES truth0=($INIT_TRUTH)"

READY=1
[ "$ACTIVE" -eq 6 ] || READY=0
[ "$TF" -eq 4 ] || READY=0

L0=$(wc -l < /tmp/fyp_nav.launch.log)
setsid nohup /usr/bin/python3 $S/phase1_amcl_trace.py "$D/amcl_trace.log" 400 > "$D/trace.err" 2>&1 < /dev/null &
sleep 3

log "sending goal (2.0, 0.0)"
T0=$(date +%s.%N)
timeout 400 bash $R/send_test_goal.sh > "$D/goal.out" 2>&1
GOAL_RC=$?
T1=$(date +%s.%N)
RESULT=$(grep -oE 'Goal finished with status: [A-Z]+' "$D/goal.out" | awk '{print $NF}')
log "action result=${RESULT:-none} rc=$GOAL_RC"

STOP=$(/usr/bin/python3 $S/trial_probe.py wait_stopped 90 2>/dev/null)
sleep 2
FINAL_TRUTH=$(truth)
FINAL_AMCL=$(/usr/bin/python3 $S/amcl_cov.py 2>&1 | tail -1)
tail -n +$((L0+1)) /tmp/fyp_nav.launch.log > "$D/nav_during_goal.log"
EV=$(grep -oE 'Running (spin|backup|wait|drive_on_heading)|Failed to make progress|Received request to clear entirely|Reached the goal!|Goal succeeded|Goal failed|aborted' "$D/nav_during_goal.log" | sort | uniq -c | awk '{c=$1; $1=""; printf "%s=%s;", substr($0,2), c}')
UPDATES=$(wc -l < "$D/amcl_trace.log")
cp "$D/amcl_trace.log" "$D/amcl_trace_at_end.log"

/usr/bin/python3 - "$N" "$READY" "$LIFE" "$PARAMS" "$RATES" "$TF" "$INIT_TRUTH" "$INIT_AMCL" "$RESULT" "$GOAL_RC" \
  "$T0" "$T1" "$STOP" "$FINAL_TRUTH" "$FINAL_AMCL" "$EV" "$UPDATES" >> $S/results.jsonl <<'EOF'
import json, math, re, sys
a = sys.argv[1:]
def xy(s):
    v = s.split(); return (float(v[0]), float(v[1])) if len(v) >= 2 else (None, None)
def amcl(s):
    m = re.search(r"amcl_pose \((-?[0-9.]+),(-?[0-9.]+)\).*x=([0-9.]+) m +y=([0-9.]+) m +yaw=([0-9.]+)", s)
    return tuple(float(g) for g in m.groups()) if m else (None,) * 5
ix, iy = xy(a[6]); fx, fy = xy(a[13]); ax, ay, sx, sy, syaw = amcl(a[14])
gt = math.hypot(fx - 2.0, fy - 0.0) if fx is not None else None
loc = math.hypot(ax - fx, ay - fy) if ax is not None and fx is not None else None
print(json.dumps({
    "run": int(a[0]), "ready": a[1] == "1", "lifecycle": a[2], "params": a[3].strip(), "rates": json.loads(a[4]) if a[4] else None,
    "tf_ok": int(a[5]), "init_truth": [ix, iy], "init_amcl": a[7], "result": a[8] or None, "goal_rc": int(a[9]),
    "duration_s": round(float(a[11]) - float(a[10]), 2), "stop": json.loads(a[12]) if a[12] else None,
    "final_truth": [fx, fy], "final_amcl": [ax, ay], "amcl_sigma": [sx, sy, syaw],
    "gt_dist_from_goal": round(gt, 4) if gt is not None else None, "loc_error": round(loc, 4) if loc is not None else None,
    "events": a[15], "amcl_updates": int(a[16]), "pass": gt is not None and gt <= 0.15}))
EOF
tail -1 $S/results.jsonl
log "stopping stack"
bash $S/stop_stack.sh > "$D/stop_after.txt" 2>&1
