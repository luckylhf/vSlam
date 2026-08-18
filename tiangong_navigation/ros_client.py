import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32
import sounddevice as sd  
import math
import numpy as np
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseWithCovarianceStamped
from action_msgs.msg import GoalStatus
from rclpy.action import ActionClient
import subprocess
import os
import wave

# ============================================================================
# 配置说明：
#   1. ARM_WS_DIR：ARM 端工作空间根目录，默认使用环境变量 ARM_WS_DIR（例如 ~/code），
#                  未设置时回退到 ~/code。
#   2. WAV_DIR：讲解词音频文件目录，默认为相对当前工作目录的 wav/，可通过环境变量
#               WAV_DIR 覆盖。
#   3. 下方 goal_positions 中的坐标为示例值，请根据实际建图结果在 RViz 中查看并修改。
# ============================================================================

# ARM 端工作空间根目录
ARM_WS_DIR = os.environ.get("ARM_WS_DIR", os.path.expanduser("~/code"))
# ARM 端脚本目录（注意原拼写错误 scrips 已修正为 scripts）
ARM_SCRIPTS_DIR = os.path.join(ARM_WS_DIR, "scripts")
# 讲解词音频目录
WAV_DIR = os.environ.get("WAV_DIR", os.path.join(os.getcwd(), "wav"))

class CommandExecutorNode(Node):
    def __init__(self):
        super().__init__('command_executor_node')
        self._action_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        # 订阅名为"command"的Int32类型话题
        self.subscription = self.create_subscription(
            Int32,
            'udp_command_int',
            self.command_callback,
            10)
        self.int_pub = self.create_publisher(
            Int32,          
            '/action_command',  
            10             
        )
        self.pose_sub = self.create_subscription(
            PoseWithCovarianceStamped,
            '/localization_pose',  # RTAB-Map 的 map 坐标系位姿话题
            self.pose_callback,
            10
        )
        self.start_time = 0
        self.goal_handle = None  # 用于存储目标句柄
        self.goal_canceled = False  # 标记是否已取消目标，避免重复操作
        self.yaw_deg = 0.0  # 机器人当前朝向（角度制）
        self.yaw_goal = 0.0
        self.current_cmd = 2
        # 键为整数命令，值为对应的脚本路径
        # 说明：脚本路径基于 ARM_SCRIPTS_DIR，通过环境变量 ARM_WS_DIR 配置
        self.command_mapping = {
            88: os.path.join(ARM_SCRIPTS_DIR, 'start_robot.sh'),
            89: os.path.join(ARM_SCRIPTS_DIR, 'init_pose.sh'),
            90: os.path.join(ARM_SCRIPTS_DIR, 'camera.sh'),
        }
        self.running_processes = {}
        self.get_logger().info('Command executor node initialized. Waiting for commands...')

    def quaternion_to_yaw(self, quaternion):
        x, y, z, w = quaternion
        t0 = 2.0 * (w * z + x * y)
        t1 = 1.0 - 2.0 * (y * y + z * z)
        return math.atan2(t0, t1)
        
    def pose_callback(self, msg: PoseWithCovarianceStamped):
        # 确认坐标系为 map（RTAB-Map 通常默认发布到 map 坐标系）
        if msg.header.frame_id != 'map':
            self.get_logger().warn(f"收到的位姿坐标系不是 map，而是 {msg.header.frame_id}")
            return

        orientation = msg.pose.pose.orientation
        quaternion = [orientation.x, orientation.y, orientation.z, orientation.w]
        yaw = self.quaternion_to_yaw(quaternion)
        self.yaw_deg = math.degrees(yaw)

    def send_goal(self, cmd_id):
        # 根据指令ID映射到不同的导航目标点
        goal_positions = {
            0x11: (0.98, 2.66, 0.8192, -0.5736),   # 0x21对应的目标点（x,y,z,w）
            0x12: (-1.71, 9.97, 0.93968, -0.34205),  # 0x22对应的目标点
            0x13: (-1.71, 9.97, 0.8192, -0.5736),
            0x14: (7.22, 15.3, 0.9962, 0.0872),   
            0x15: (7.20, 15.3, 0.8192, -0.5736),  
            0x16: (12.91, 18.44, 0.8660, -0.5000),
            0x17: (12.91, 18.44, 0.9962, 0.0872),
            0x18: (1.83, 29.09, 0.0, 1.0),
            0x19: (1.83, 29.09, -0.2588, 0.9659)
        }
        self.get_logger().warn(f"指令 {cmd_id} 导航目标点")
        # 检查指令ID是否在预设目标中
        if cmd_id not in goal_positions:
            self.get_logger().warn(f"指令 {cmd_id} 无对应导航目标点")
            return
        self.current_cmd = cmd_id - 0x10 + 1
        x, y, z, w = goal_positions[cmd_id]
        # 构建 Nav2 目标消息
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = 'map'  # 参考坐标系
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        # 位置（2D导航z=0）
        goal_msg.pose.pose.position.x = x
        goal_msg.pose.pose.position.y = y
        goal_msg.pose.pose.position.z = 0.0
        # 姿态（四元数）
        goal_msg.pose.pose.orientation.x = 0.0
        goal_msg.pose.pose.orientation.y = 0.0
        goal_msg.pose.pose.orientation.z = z
        goal_msg.pose.pose.orientation.w = w
        quaternion = [0.0, 0.0, z, w]
        yaw = self.quaternion_to_yaw(quaternion)
        self.yaw_goal = math.degrees(yaw)

        # 发送目标并绑定回调
        self._send_goal_future = self._action_client.send_goal_async(
            goal_msg,
            feedback_callback=self.feedback_callback
        )
        self._send_goal_future.add_done_callback(
            lambda fut: self.goal_response_callback(fut, x, y, z, w)
        )
        self.is_navigating = True
        self.goal_canceled = False
        resp_msg = f"导航目标已发送：x={x:.2f}, y={y:.2f}, 姿态(z={z:.2f}, w={w:.2f})"
        self.get_logger().info(resp_msg)

    def goal_response_callback(self, future, x, y, z, w):
        try:
            self.goal_handle = future.result()
            if not self.goal_handle.accepted:
                err_msg = f"导航目标被拒绝：x={x:.2f}, y={y:.2f}"
                self.get_logger().warn(err_msg)
                self.is_navigating = False
                return
            else:
                if x != 7.22:
                    msg = Int32()
                    msg.data = 6
                    self.int_pub.publish(msg)
            self._get_result_future = self.goal_handle.get_result_async()
            self._get_result_future.add_done_callback(self.get_result_callback)
        except Exception as e:
            err_msg = f"目标响应处理出错：{str(e)}"
            self.get_logger().error(err_msg)
            self.is_navigating = False

    def get_result_callback(self, future):
        try:
            action_result = future.result()
            if not action_result:
                resp_msg = "未获取到导航结果"
                self.get_logger().error(resp_msg)
                return

            if action_result.status == GoalStatus.STATUS_SUCCEEDED:
                resp_msg = "导航成功！已到达目标点"
                msg = Int32()
                msg.data = 5
                self.int_pub.publish(msg)
            else:
                resp_msg = f"导航未成功，状态码：{action_result.status}"
            self.get_logger().info(resp_msg)
        except Exception as e:
            self.get_logger().error(f"处理结果时出错: {e}")

    def feedback_callback(self, feedback_msg):
        feedback = feedback_msg.feedback
        remaining_dist = feedback.distance_remaining
        if remaining_dist == 0.0:
            return
        diff = self.yaw_deg - self.yaw_goal
        feedback_msg = (f"导航中 | 剩余距离：{remaining_dist:.2f}米 | {diff:.2f}度")
        if remaining_dist < 1.5:
            if self.goal_canceled is not True:
                self.start_time = 0
                self.goal_canceled = True
            self.start_time = self.start_time + 1    
            if self.start_time > 800:
                self.get_logger().info(f"剩余距离小于2米（当前{remaining_dist:.2f}米），取消导航目标")
                if self.goal_handle is not None:
                    self.get_logger().info(f"剩余距离小于2米（当前{remaining_dist:.2f}米），取消导航目标222")
                    msg = Int32()
                    msg.data = 5
                    self.int_pub.publish(msg)
                    cancel_future = self.goal_handle.cancel_goal_async()
                    cancel_future.add_done_callback(self.cancel_callback)
                else:
                    msg = Int32()
                    msg.data = 5
                    self.int_pub.publish(msg)
                    self.get_logger().warn("无有效目标句柄，无法取消导航")
            # elif duration >= 10.0:
            #     msg = Int32()
            #     msg.data = 5
            #     self.int_pub.publish(msg)
            #     self.get_logger().warn("超时站立")

        self.get_logger().info(feedback_msg)

    def cancel_callback(self, future):
        try:
            cancel_response = future.result()
            if cancel_response.goals_canceling:
                self.get_logger().info("导航目标已成功取消")
            else:
                self.get_logger().warn(
                    f"导航目标取消失败，返回码：{cancel_response.return_code}"
                )
        except Exception as e:
            self.get_logger().error(f"取消回调处理错误：{str(e)}")

    def command_callback(self, msg):
        command = msg.data
        self.get_logger().info(f'Received command: {command}')
        
        if command in self.command_mapping:
            script_path = self.command_mapping[command]
            # 检查脚本是否存在
            if os.path.exists(script_path):
                self.get_logger().info(f'Executing script: {script_path}')
                if command not in self.running_processes:  # 启动相机和规控程序
                    log_file_90 = "camera_output.log"  # 90对应camera.sh的日志
                    err_file_90 = "camera_error.log"
                    log_file_89 = "init_pose_output.log"  # 89对应init_pose.sh的日志
                    err_file_89 = "init_pose_error.log"
                    script_90 = self.command_mapping.get(90)
                    f_out_90 = open(log_file_90, "a")  # "a"模式追加日志，而非覆盖
                    f_err_90 = open(err_file_90, "a")
                    process1 = subprocess.Popen(
                        [script_90],
                        stdout=f_out_90,
                        stderr=f_err_90,
                        text=True,
                        env=os.environ.copy()
                    )
                    f_out_89 = open(log_file_89, "a")
                    f_err_89 = open(err_file_89, "a")
                    process = subprocess.Popen(
                        [script_path],
                        stdout=f_out_89,
                        stderr=f_err_89,
                        text=True,
                        env=os.environ.copy()
                    )
                    self.running_processes[command] = process
                    self.get_logger().info(f'Script output: {process.stdout}')
                else: # 重定位
                    script_89 = self.command_mapping.get(89)
                    process = subprocess.Popen(
                        [script_89],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                #     self.get_logger().info(f'Script output: {process.stdout}')
            else:
                self.get_logger().error(f'Script not found: {script_path}')
        elif 1 <= command <= 10: # 讲解词播放
            try:
                audio_filename = os.path.join(WAV_DIR, f"{command}.wav")
                with wave.open(audio_filename, 'rb') as wf:
                    n_channels = wf.getnchannels()
                    samp_width = wf.getsampwidth()
                    frame_rate = wf.getframerate()
                    raw_data = wf.readframes(wf.getnframes())
            
                # 转换字节为NumPy数组
                dtype_map = {1: np.uint8, 2: np.int16, 4: np.int32}
                if samp_width not in dtype_map:
                    raise ValueError(f"不支持的采样宽度: {samp_width}字节")
                    
                audio_array = np.frombuffer(raw_data, dtype=dtype_map[samp_width])
                
                if n_channels > 1:
                    audio_array = audio_array.reshape(-1, n_channels)
                
                sd.play(audio_array, samplerate=frame_rate, blocksize=4096, latency=0.1)
                sd.wait()
                sd.stop()
                if command == 1:
                    msg = Int32()
                    msg.data = 2
                    self.int_pub.publish(msg)
            except Exception as e:
                self.get_logger().error(f"播放失败: {str(e)}")
        elif 0x11 <= command <= 0x19:
            self.send_goal(command)

def main(args=None):
    rclpy.init(args=args)
    command_executor_node = CommandExecutorNode()
    rclpy.spin(command_executor_node)
    
    # 关闭节点
    command_executor_node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
    
