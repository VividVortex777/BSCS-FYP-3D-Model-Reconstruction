"""Compare live /scan with a 2D ray-cast of indoor_world.sdf.

Usage: scan_vs_world.py <world.sdf> <seconds> [label]
Pose from /odom (the Gazebo odometry plugin reports the true world pose).
Camera = base_link + Rz(yaw) * (0.35, 0). Prints error statistics.
"""
import math
import sys
import time
import xml.etree.ElementTree as ET

import numpy as np
import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan

world, seconds = sys.argv[1], float(sys.argv[2])
label = sys.argv[3] if len(sys.argv) > 3 else ""

boxes = []  # (xmin, xmax, ymin, ymax) of every model taller than 0.4 m
for m in ET.parse(world).getroot().find("world").findall("model"):
    size = m.find(".//collision//box/size")
    if size is None:
        continue
    sx, sy, sz = map(float, size.text.split())
    px, py = map(float, (m.findtext("pose") or "0 0 0").split()[:2])
    if sz < 0.4:
        continue  # the floor slab
    boxes.append((px - sx / 2, px + sx / 2, py - sy / 2, py + sy / 2))


def raycast(ox, oy, ang, max_r):
    dx, dy = math.cos(ang), math.sin(ang)
    best = math.inf
    for x0, x1, y0, y1 in boxes:
        tmin, tmax = -math.inf, math.inf
        for o, d, lo, hi in ((ox, dx, x0, x1), (oy, dy, y0, y1)):
            if abs(d) < 1e-12:
                if not lo <= o <= hi:
                    tmin, tmax = 1, 0
                continue
            t1, t2 = (lo - o) / d, (hi - o) / d
            tmin, tmax = max(tmin, min(t1, t2)), min(tmax, max(t1, t2))
        if tmax >= tmin and tmin > 0:
            best = min(best, tmin)
    return best if best <= max_r else math.inf


rclpy.init()
node = Node("phase1_scan_vs_world",
            parameter_overrides=[Parameter("use_sim_time", Parameter.Type.BOOL, True)])
odom = []
scans = []
node.create_subscription(Odometry, "/odom", lambda m: odom.append(m), 50)
node.create_subscription(LaserScan, "/scan", lambda m: scans.append(m), qos_profile_sensor_data)
end = time.time() + seconds
while time.time() < end:
    rclpy.spin_once(node, timeout_sec=0.1)

errs, n_beams, false_short, missing, extra = [], 0, 0, 0, 0
frames, pitches = set(), []
for s in scans:
    st = s.header.stamp.sec + s.header.stamp.nanosec * 1e-9
    if not odom:
        break
    o = min(odom, key=lambda m: abs(m.header.stamp.sec + m.header.stamp.nanosec * 1e-9 - st))
    p, q = o.pose.pose.position, o.pose.pose.orientation
    yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
    pitches.append(math.degrees(math.asin(max(-1, min(1, 2 * (q.w * q.y - q.z * q.x))))))
    cx, cy = p.x + 0.35 * math.cos(yaw), p.y + 0.35 * math.sin(yaw)
    frames.add(s.header.frame_id)
    for i, r in enumerate(s.ranges):
        ang = yaw + s.angle_min + i * s.angle_increment
        exp = raycast(cx, cy, ang, s.range_max)
        n_beams += 1
        if math.isfinite(r) and math.isfinite(exp):
            errs.append(r - exp)
            if r < exp - 0.30:
                false_short += 1
        elif math.isfinite(exp) and not math.isfinite(r):
            missing += 1
        elif math.isfinite(r) and not math.isfinite(exp):
            extra += 1

e = np.abs(np.array(errs)) if errs else np.array([np.nan])
print(f"[{label}] scans={len(scans)} beams={n_beams} frame_id={sorted(frames)} "
      f"pitch range={min(pitches, default=float('nan')):.2f}..{max(pitches, default=float('nan')):.2f} deg")
if scans:
    s = scans[-1]
    print(f"  angle_min={s.angle_min:.4f} angle_max={s.angle_max:.4f} inc={s.angle_increment:.5f} "
          f"range_min={s.range_min} range_max={s.range_max} n={len(s.ranges)}")
print(f"  matched beams={len(errs)}  |error| median={np.median(e):.3f} m  p95={np.percentile(e, 95):.3f} m  "
      f"max={np.max(e):.3f} m  within 0.10 m: {100 * np.mean(e <= 0.10):.1f}%")
sg = np.array(errs) if errs else np.array([np.nan])
print(f"  signed (scan - world): median={np.median(sg):+.4f} m  mean={np.mean(sg):+.4f} m  p10={np.percentile(sg,10):+.4f} p90={np.percentile(sg,90):+.4f}")
print(f"  shorter than world by >0.30 m (floor/phantom): {false_short}  "
      f"missing (world wall, scan inf): {missing}  extra (scan hit, world empty): {extra}")
