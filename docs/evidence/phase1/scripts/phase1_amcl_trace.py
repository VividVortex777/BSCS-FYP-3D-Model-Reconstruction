"""Log every /amcl_pose update next to the true pose (/odom) at the same stamp."""
import bisect
import math
import sys
import time

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.parameter import Parameter

rclpy.init()
n = Node("phase1_amcl_trace", parameter_overrides=[Parameter("use_sim_time", Parameter.Type.BOOL, True)])
out = open(sys.argv[1], "w")
odom_t, odom = [], []


def yaw_pitch(q):
    yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
    pitch = math.asin(max(-1, min(1, 2 * (q.w * q.y - q.z * q.x))))
    return math.degrees(yaw), math.degrees(pitch)


def on_odom(m):
    t = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
    p = m.pose.pose.position
    y, pi = yaw_pitch(m.pose.pose.orientation)
    odom_t.append(t)
    odom.append((p.x, p.y, y, pi, m.twist.twist.linear.x, m.twist.twist.angular.z))


def on_amcl(m):
    t = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
    i = min(max(bisect.bisect_left(odom_t, t), 0), len(odom_t) - 1) if odom_t else None
    p, c = m.pose.pose.position, m.pose.covariance
    ay, _ = yaw_pitch(m.pose.pose.orientation)
    if i is None:
        return
    tx, ty, tyaw, tp, v, w = odom[i]
    out.write(f"t={t:7.2f} amcl=({p.x:6.3f},{p.y:6.3f},{ay:6.1f}) true=({tx:6.3f},{ty:6.3f},{tyaw:6.1f}) "
              f"err=({p.x - tx:+.3f},{p.y - ty:+.3f},{ay - tyaw:+.1f}deg) |err|={math.hypot(p.x - tx, p.y - ty):.3f} "
              f"sig=({math.sqrt(c[0]):.3f},{math.sqrt(c[7]):.3f}) pitch={tp:4.2f} v={v:+.2f} w={w:+.2f} dt_odom={odom_t[i] - t:+.3f}\n")
    out.flush()


n.create_subscription(Odometry, "/odom", on_odom, 50)
n.create_subscription(PoseWithCovarianceStamped, "/amcl_pose", on_amcl, 50)
end = time.time() + float(sys.argv[2])
while time.time() < end:
    rclpy.spin_once(n, timeout_sec=0.1)
