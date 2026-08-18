import rclpy
from sensor_msgs.msg import Imu
from nav_msgs.msg import Path
from geometry_msgs.msg import Point, Quaternion, PoseStamped
from std_msgs.msg import Int32MultiArray, Float32MultiArray
from rclpy.node import Node
from nav_msgs.msg import Odometry
from geometry_msgs.msg import TransformStamped  # TF变换消息类型
import tf2_ros  # TF2核心库
import numpy as np
from tf2_msgs.msg import TFMessage
import time
import math
from geometry_msgs.msg import Twist, PoseStamped  # Twist是/cmd_vel消息类型
from builtin_interfaces.msg import Time
from hric_msgs.msg import MotionStatus  # 替换为你的话题消息类名
from geometry_msgs.msg import Twist, TwistStamped

# if run this python script should remove .
# it is correct to add . when run in ros2

class Mon_subscriber(Node):
    def __init__(self,node_name):
        super().__init__(node_name)
        self.get_logger().info(f"start mon_sub:{node_name}")
        self.yaw_deg = 0.0
        self.global_x = 0.0
        self.global_y = 0.0
        self.callback_count = 0
        self.quaternion = None
        self.angular = None
        self.imu_timestamp = None
        self.img_timestamp = None
        self.last_vel_x = 0.0
        self.last_vel_y = 0.0
        self.yaw_offset = 0.0
        self.yaw_last = 0.0
        self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)
        self.rotation_matrix = np.eye(3)
        self.pose = np.zeros((3,1))
       
        # create path
        self.path = Path()
        self.path.header.frame_id = 'map'
        self.path_pub = self.create_publisher(Path,'traj', 10)
        self.imu_subscriber = self.create_subscription(Imu,'/imu',self.imu_callback,10)
        self.motion_status_sub = self.create_subscription(
            msg_type=MotionStatus,
            topic='/hric/motion/status',  # 自定义话题名
            callback=self.motion_status_callback,
            qos_profile=10
        )
        self.twist_sub = self.create_subscription(
            Twist,
            '/cmd_vel_nav',  # Nav2 原始速度话题
            self.twist_callback,
            10
        )
        self.odom_publisher = self.create_publisher(
            Odometry,
            '/odom',
            10
        )
        
        # 2. 创建发布者，发布转换后的 TwistStamped 类型话题
        self.twist_stamped_pub = self.create_publisher(
            TwistStamped,
            '/hric/robot/cmd_vel',  # 转换后的话题名
            10
        )
        

    def quaternion_to_yaw(self, x, y, z, w):
        siny_cosp = 2 * (w * z + x * y)
        cosy_cosp = 1 - 2 * (y * y + z * z)
        yaw = math.atan2(siny_cosp, cosy_cosp)
        return yaw

    def twist_callback(self, twist_msg: Twist):
        """将 Twist 消息转换为 TwistStamped 消息"""
        twist_stamped_msg = TwistStamped()
        # 填充头部信息（时间戳和坐标系）
        twist_stamped_msg.header.stamp = self.get_clock().now().to_msg()  # 当前时间戳
        twist_stamped_msg.header.frame_id = "base_link"  # 坐标系
        twist_stamped_msg.twist = twist_msg  # 直接赋值，两者结构一致
        if twist_stamped_msg.twist.linear.x == 0.0:
            self.callback_count += 1
        else:
            self.callback_count = 0
        twist_stamped_msg.twist.linear.x = twist_stamped_msg.twist.linear.x + 0.05
        self.twist_stamped_pub.publish(twist_stamped_msg)

    def imu_callback(self, msg):
        x = msg.orientation.x
        y = msg.orientation.y
        z = msg.orientation.z
        w = msg.orientation.w
        self.quaternion = msg.orientation
        self.angular = msg.angular_velocity
        self.imu_timestamp = msg.header.stamp
        # 计算yaw角（弧度）
        yaw_rad = self.quaternion_to_yaw(x, y, z, w)
        # 转换为角度（可选）
        self.yaw_deg = math.degrees(yaw_rad)
        

    def euler_to_quaternion(self, yaw, pitch, roll):
        half_yaw = yaw * 0.5
        half_pitch = pitch * 0.5
        half_roll = roll * 0.5
        
        # 计算三角函数值
        cos_yaw = math.cos(half_yaw)
        sin_yaw = math.sin(half_yaw)
        cos_pitch = math.cos(half_pitch)
        sin_pitch = math.sin(half_pitch)
        cos_roll = math.cos(half_roll)
        sin_roll = math.sin(half_roll)
        
        # 四元数计算公式 (Z-Y-X旋转顺序)
        w = cos_roll * cos_pitch * cos_yaw + sin_roll * sin_pitch * sin_yaw
        x = sin_roll * cos_pitch * cos_yaw - cos_roll * sin_pitch * sin_yaw
        y = cos_roll * sin_pitch * cos_yaw + sin_roll * cos_pitch * sin_yaw
        z = cos_roll * cos_pitch * sin_yaw - sin_roll * sin_pitch * cos_yaw
        return (x, y, z, w)

    def motion_status_callback(self, msg: MotionStatus):
        if self.imu_timestamp is None:
            return
        
        now = self.get_clock().now().to_msg()
        if self.img_timestamp is None:
            self.img_timestamp = now
            return
        
        time_offset = now.sec + now.nanosec * 1e-9 - (self.img_timestamp.sec + self.img_timestamp.nanosec * 1e-9)
    #    print(f"时间间隔 time_offset: {time_offset:.6f} 秒")
        self.img_timestamp = now  # 时间戳对象，包含 .sec 和 .nanosec 属性
        # 提取秒和纳秒（用于后续计算或存储）

        yaw = math.radians(self.yaw_deg)
        pitch = math.radians(0.0)
        roll = math.radians(0.0)
        self.yaw_currrent = yaw - self.yaw_offset
        if(msg.walk_mode > 4):    #站立模式下速度为0,位姿保持不变
            avg_vel = (msg.velocity.linear.x + self.last_vel_x) / 2.0# - 0.03171528
        else:
            avg_vel = 0.0
            self.yaw_offset = self.yaw_offset + yaw - self.yaw_last
            
        if msg.is_console_control == True and self.callback_count > 50:
            avg_vel = 0.0

        self.yaw_last = yaw
        #print(f"avg_vel: {avg_vel:.6f} M")
        translation_distance = avg_vel * time_offset
        self.last_vel_x = msg.velocity.linear.x
        self.last_vel_y = msg.velocity.linear.y
        dx_map = translation_distance * math.cos(yaw)
        dy_map = translation_distance * math.sin(yaw)
        self.global_x += dx_map
        self.global_y += dy_map

        tf_msg = TransformStamped()
        tf_msg.header.stamp = now  # 当前时间戳（必须实时更新）
        tf_msg.header.frame_id = "odom"             # 父坐标系名称（map）
        tf_msg.child_frame_id = "base_link"
        tf_msg.transform.translation.x = self.global_x  # x轴平移（动态变化）
        tf_msg.transform.translation.y = self.global_y  # y轴固定（无移动）
        tf_msg.transform.translation.z = 0.0  # z轴固定（相机高度0.5米）

         # 转换为四元数
        x, y, z, w = self.euler_to_quaternion(self.yaw_currrent, pitch, roll)
        tf_msg.transform.rotation.x = x
        tf_msg.transform.rotation.y = y
        tf_msg.transform.rotation.z = z
        tf_msg.transform.rotation.w = w
        self.tf_broadcaster.sendTransform(tf_msg)

        # 创建Odometry消息
        odom = Odometry()
        odom.header.stamp = now
        odom.header.frame_id = 'odom'  # 里程计的父坐标系
        odom.child_frame_id = "base_link"   # 里程计的子坐标系
        # 设置位置信息
        odom.pose.pose.position.x = self.global_x
        odom.pose.pose.position.y = self.global_y
        odom.pose.pose.position.z = 0.0
        # 设置姿态信息
        odom.pose.pose.orientation.x = x#self.quaternion.x
        odom.pose.pose.orientation.y = y#self.quaternion.y
        odom.pose.pose.orientation.z = z#self.quaternion.z
        odom.pose.pose.orientation.w = w#self.quaternion.w
        # 速度信息设置为0（如果需要更精确的速度，需要额外计算）
        odom.twist.twist = Twist()
        odom.twist.twist.linear.x = msg.velocity.linear.x * math.cos(yaw)
        odom.twist.twist.linear.y = msg.velocity.linear.x * math.sin(yaw)
        odom.twist.twist.angular.x = self.angular.x
        odom.twist.twist.angular.y = self.angular.y
        odom.twist.twist.angular.z = self.angular.z
        self.odom_publisher.publish(odom)

def main(args=None):
    rclpy.init(args=args)
    node = Mon_subscriber(node_name="Mon_subscributer")  
    rclpy.spin(node) 
    rclpy.shutdown()

if __name__=='__main__':
    main()
