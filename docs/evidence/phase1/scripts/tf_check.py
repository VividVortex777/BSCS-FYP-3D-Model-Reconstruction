"""Check TF chains with a sim-time listener (waits up to 25 s)."""
import time

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from tf2_ros import Buffer, TransformListener

rclpy.init()
n = Node("phase1_tf_check", parameter_overrides=[Parameter("use_sim_time", Parameter.Type.BOOL, True)])
buf = Buffer()
TransformListener(buf, n)
pairs = [("odom", "base_link"), ("map", "odom"), ("map", "base_link"),
         ("base_link", "sim_depth_camera"), ("sim_depth_camera", "sim_depth_scan"),
         ("base_link", "sim_depth_scan"), ("map", "sim_depth_scan"),
         ("base_link", "camera_depth_frame")]
deadline = time.time() + 25
res = {}
while time.time() < deadline and len(res) < len(pairs):
    rclpy.spin_once(n, timeout_sec=0.2)
    for a, b in pairs:
        if (a, b) not in res and buf.can_transform(a, b, rclpy.time.Time()):
            t = buf.lookup_transform(a, b, rclpy.time.Time()).transform
            r = t.rotation
            res[(a, b)] = (f"OK  xyz=({t.translation.x:.3f},{t.translation.y:.3f},{t.translation.z:.3f}) "
                           f"q=({r.x:.4f},{r.y:.4f},{r.z:.4f},{r.w:.4f})")
for a, b in pairs:
    print(f"  {a:>16} -> {b:<18} {res.get((a, b), 'MISSING after 25 s')}")
