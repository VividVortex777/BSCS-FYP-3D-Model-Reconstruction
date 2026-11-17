import math, time, rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
from geometry_msgs.msg import PoseWithCovarianceStamped
rclpy.init(); n = Node("phase1_amcl_cov"); got = []
n.create_subscription(PoseWithCovarianceStamped, "/amcl_pose", got.append,
    QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL, reliability=ReliabilityPolicy.RELIABLE))
t0 = time.time()
while not got and time.time() - t0 < 10: rclpy.spin_once(n, timeout_sec=0.2)
c = got[-1].pose.covariance; p = got[-1].pose.pose.position
print(f"amcl_pose ({p.x:.3f},{p.y:.3f}) stamp={got[-1].header.stamp.sec}  1-sigma: x={math.sqrt(c[0]):.3f} m  y={math.sqrt(c[7]):.3f} m  yaw={math.degrees(math.sqrt(c[35])):.2f} deg")
