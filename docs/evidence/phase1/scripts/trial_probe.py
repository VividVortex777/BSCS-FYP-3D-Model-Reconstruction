"""Readiness and stop detection for the repeatability trials.

  trial_probe.py rates           -> message rates of /odom, /scan, depth, /clock over 5 s (sim-time node)
  trial_probe.py wait_stopped T  -> wait until |v|,|w| < 0.01 for 3 s of sim time (timeout T wall s)
"""
import json
import sys
import time

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_sensor_data
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import Image, LaserScan

rclpy.init()
n = Node("phase1_trial_probe", parameter_overrides=[Parameter("use_sim_time", Parameter.Type.BOOL, True)])
mode = sys.argv[1]

if mode == "rates":
    count = {"odom": 0, "scan": 0, "depth": 0, "clock": 0}
    first_odom = {}

    def on_odom(m):
        count["odom"] += 1
        if not first_odom:
            t = m.twist.twist
            first_odom.update(v=t.linear.x, w=t.angular.z)

    n.create_subscription(Odometry, "/odom", on_odom, 10)
    n.create_subscription(LaserScan, "/scan", lambda m: count.__setitem__("scan", count["scan"] + 1), qos_profile_sensor_data)
    n.create_subscription(Image, "/rgbd_camera/depth_image", lambda m: count.__setitem__("depth", count["depth"] + 1), qos_profile_sensor_data)
    n.create_subscription(Clock, "/clock", lambda m: count.__setitem__("clock", count["clock"] + 1), qos_profile_sensor_data)
    t0 = time.time()
    while time.time() - t0 < 5.0:
        rclpy.spin_once(n, timeout_sec=0.05)
    print(json.dumps({k + "_hz": round(v / 5.0, 1) for k, v in count.items()} | {"odom_v0": first_odom.get("v"), "odom_w0": first_odom.get("w")}))

elif mode == "wait_stopped":
    state = {"since": None, "done": False, "t": None}

    def on_odom(m):
        t = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        tw = m.twist.twist
        still = abs(tw.linear.x) < 0.01 and abs(tw.angular.z) < 0.01
        if still:
            state["since"] = state["since"] if state["since"] is not None else t
            if t - state["since"] >= 3.0:
                state["done"], state["t"] = True, t
        else:
            state["since"] = None

    n.create_subscription(Odometry, "/odom", on_odom, 10)
    t0 = time.time()
    while not state["done"] and time.time() - t0 < float(sys.argv[2]):
        rclpy.spin_once(n, timeout_sec=0.05)
    print(json.dumps({"stopped": state["done"], "stopped_sim_t": state["t"], "wait_wall_s": round(time.time() - t0, 1)}))
