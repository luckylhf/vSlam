import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
import subprocess
import datetime
import time
import sys
class ImuTimeSyncNode(Node):
    def __init__(self):
        super().__init__('imu_time_sync_node')
        
        # 订阅IMU话题，默认话题名为/imu/data，可根据实际情况修改
        self.subscription = self.create_subscription(
            Imu,
            '/imu',
            self.imu_callback,
            1)
        self.subscription  # 防止未使用变量警告
        self.time_num = 0
        # 标记是否已同步时间
        self.time_synchronized = False
        
        self.get_logger().info('IMU时间同步节点已启动，等待IMU数据...')

    def imu_callback(self, msg):
        # 如果已经同步过时间，不再处理
        if self.time_synchronized:
            return
        self.time_num = self.time_num + 1
        if self.time_num < 3000:
            return     
        try:
            # 从IMU消息中获取时间戳
            imu_time = msg.header.stamp
            
            # 将ROS时间戳转换为datetime对象
            # 1. 先转换秒数部分
            dt = datetime.datetime.fromtimestamp(imu_time.sec)
            # 2. 处理纳秒部分：转换为微秒（1微秒=1000纳秒）
            # 注意：timedelta的microseconds参数最大值为999999
            microseconds = (imu_time.nanosec // 1000) % 1000000
            dt += datetime.timedelta(microseconds=microseconds)
            
            self.get_logger().info(f'接收到IMU时间戳: {dt.strftime("%Y-%m-%d %H:%M:%S.%f")}')
            
            # 格式化时间字符串，用于设置系统时间
            # 格式: "YYYY-MM-DD HH:MM:SS"
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            
            # 同步系统时间
            self.set_system_time(time_str)
            
            # 同步硬件时钟
            self.sync_hardware_clock()
            
            self.time_synchronized = True
            self.get_logger().info('系统时间已成功同步到IMU时间戳')
            #rclpy.shutdown()     # 关闭ROS客户端库 
            sys.exit(0)
        except Exception as e:
            self.get_logger().error(f'处理IMU时间戳时出错: {str(e)}')

    def set_system_time(self, time_str):
        """设置系统时间"""
        try:
            subprocess.run(
                ['sudo', '-n', 'date', '-s', time_str],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            self.get_logger().info(f'系统时间已设置为: {time_str}')
        except subprocess.CalledProcessError as e:
            self.get_logger().error(f'设置系统时间失败: {e.stderr}')
            raise

    def sync_hardware_clock(self):
        """将系统时间同步到硬件时钟"""
        try:
            subprocess.run(
                ['sudo', '-n', 'hwclock', '--systohc'],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            self.get_logger().info('系统时间已同步到硬件时钟')
        except subprocess.CalledProcessError as e:
            self.get_logger().error(f'同步硬件时钟失败: {e.stderr}')
            raise

def main(args=None):
    rclpy.init(args=args)
    
    imu_time_sync_node = ImuTimeSyncNode()
    
    try:
        rclpy.spin(imu_time_sync_node)
    except KeyboardInterrupt:
        imu_time_sync_node.get_logger().info('用户中断，程序退出')
    finally:
        imu_time_sync_node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
