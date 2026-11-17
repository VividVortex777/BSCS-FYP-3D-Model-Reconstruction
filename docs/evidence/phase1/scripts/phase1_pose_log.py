"""Log /odom (true pose in this sim), /amcl_pose and /cmd_vel once per sim second."""
import math
import sys
import time

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.parameter import Parameter

rclpy.init()
n = Node("phase1_pose_log", parameter_overrides=[Parameter("use_sim_time", Parameter.Type.BOOL, True)])
out = open(sys.argv[1], "w")
state = {"amcl": None, "n_amcl": 0, "sig": (float("nan"),) * 3, "cmd": 0, "vmax": 0.0, "last": -1.0}


def on_amcl(m):
    p = m.pose.pose.position
    c = m.pose.covariance
    state["amcl"] = (p.x, p.y)
    state["n_amcl"] += 1
    state["sig"] = (math.sqrt(c[0]), math.sqrt(c[7]), math.degrees(math.sqrt(c[35])))


def on_cmd(m):
    state["cmd"] += 1
    state["vmax"] = max(state["vmax"], abs(m.linear.x))


def on_odom(m):
    t = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
    if t - state["last"] < 1.0:
        return
    state["last"] = t
    p, q = m.pose.pose.position, m.pose.pose.orientation
    pitch = math.degrees(math.asin(max(-1, min(1, 2 * (q.w * q.y - q.z * q.x)))))
    a = state["amcl"]
    err = math.hypot(a[0] - p.x, a[1] - p.y) if a else float("nan")
    out.write(f"t={t:7.1f} true=({p.x:6.3f},{p.y:6.3f}) pitch={pitch:5.2f} "
              f"amcl=({a[0]:6.3f},{a[1]:6.3f}) " if a else
              f"t={t:7.1f} true=({p.x:6.3f},{p.y:6.3f}) pitch={pitch:5.2f} amcl=(  none ) ")
    sx, sy, sth = state["sig"]
    out.write(f"amcl_err={err:5.3f} sig=({sx:.3f},{sy:.3f},{sth:.1f}deg) amcl_updates={state['n_amcl']} "
              f"cmd_msgs={state['cmd']} vmax={state['vmax']:.2f}\n")
    out.flush()


n.create_subscription(Odometry, "/odom", on_odom, 10)
n.create_subscription(PoseWithCovarianceStamped, "/amcl_pose", on_amcl, 10)
n.create_subscription(Twist, "/cmd_vel", on_cmd, 10)
end = time.time() + float(sys.argv[2])
while time.time() < end:
    rclpy.spin_once(n, timeout_sec=0.2)
