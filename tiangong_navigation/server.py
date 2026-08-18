import socket
import threading
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Int32
import subprocess
import os
import time

# ============================================================================
# 配置说明：
#   1. ACTION_DIR：动作脚本所在目录，默认使用环境变量 X86_WS_DIR（x86 工作空间根目录，
#                  例如 ~/ros2ws），未设置时回退到 ~/ros2ws。
#   2. UDP_PORT：UDP 指令监听端口，默认 5005，可通过环境变量 UDP_CMD_PORT 覆盖。
#   3. 指令映射表中的展区名称为通用占位，请根据实际场地在 COMMAND_MAP 中修改。
# ============================================================================

# 动作脚本目录：优先读环境变量 X86_WS_DIR，未设置则使用 ~/ros2ws
ACTION_DIR = os.environ.get("X86_WS_DIR", os.path.expanduser("~/ros2ws"))
ACTION_DIR = os.path.join(ACTION_DIR, "scripts", "action")

# UDP 监听端口：可通过环境变量 UDP_CMD_PORT 覆盖
UDP_PORT = int(os.environ.get("UDP_CMD_PORT", "5005"))

# 协议常量
HEADER = [0xAD, 0xEC]  # 包头标识

# 指令映射表
# 说明：展区名称为通用占位，请根据实际场地修改。
COMMAND_MAP = {
    0x01: "握手",
    0x02: "打招呼",
    0x03: "鞠躬",
    0x04: "跳舞",
    0x05: "停驻",
    0x06: "行走",
    0x07: "启动规控模块",
    # 展项讲解指令 (0x11-0x1A)
    0x11: "展项讲解（1）",
    0x12: "展项讲解（2）",
    0x13: "展项讲解（3）",
    0x14: "展项讲解（4）",
    0x15: "展项讲解（5）",
    0x16: "展项讲解（6）",
    0x17: "展项讲解（7）",
    0x18: "展项讲解（8）",
    0x19: "展项讲解（9）",
    0x1A: "展项讲解（10）",
    # 前往展区指令 (0x21-0x29)
    # 说明：以下展区名为通用占位，请根据实际场地修改
    0x21: "前往领导论述展区",
    0x22: "前往展区A",
    0x23: "前往展区B",
    0x24: "前往展区C",
    0x25: "前往展区D",
    0x26: "前往展区E",
    0x27: "前往展区F",
    0x28: "前往展区G",
    0x29: "前往展区H",
}

# 指令与脚本的映射（确保与COMMAND_MAP中的指令ID对应）
# 说明：脚本路径基于 ACTION_DIR，通过环境变量 X86_WS_DIR 配置根目录
COMMAND_SCRIPT_MAP = {
    0x01: [os.path.join(ACTION_DIR, "1.sh")],
    0x02: [os.path.join(ACTION_DIR, "2.sh")],
    0x03: [os.path.join(ACTION_DIR, "3.sh")],
    0x04: [os.path.join(ACTION_DIR, "4.sh")],
    0x05: [os.path.join(ACTION_DIR, "5.sh")],
    0x06: [os.path.join(ACTION_DIR, "6.sh")],
    0x23: [os.path.join(ACTION_DIR, "right.sh")],
    0x25: [os.path.join(ACTION_DIR, "left.sh")],
    0x27: [os.path.join(ACTION_DIR, "right_big.sh")],
    0x29: [os.path.join(ACTION_DIR, "rights.sh")],
    0x99: [os.path.join(ACTION_DIR, "right_data.sh")]
}

# -------------------------- Nav2 导航目标发送类 --------------------------
class Nav2GoalSender(Node):
    def __init__(self):
        super().__init__('nav2_goal_sender_tcp')
        self.int_pub = self.create_publisher(
            Int32,          
            '/udp_command_int',  
            10)
        self.subscription = self.create_subscription(
            Int32,
            'action_command',
            self.command_callback,
            10)

    def command_callback(self, msg):
        self._execute_command(msg.data)

    def _execute_command(self, cmd_id):
        if cmd_id in COMMAND_SCRIPT_MAP:
            self.execute_script(COMMAND_SCRIPT_MAP[cmd_id])
        elif cmd_id == 0x07:
            msg = Int32()
            msg.data = 88
            self.int_pub.publish(msg)
        elif 0x11 <= cmd_id <= 0x29:
            int_value = cmd_id - 0x10 
            msg = Int32()
            msg.data = int_value
            #if cmd_id == 0x14
            #    self.execute_script(COMMAND_SCRIPT_MAP[0x99])
            self.int_pub.publish(msg)
            print(f"发布指令: {int_value}")

    def execute_script(self, script_args):
        try:
            # result = subprocess.run(
            #     script_args,
            #     check=True,
            #     stdout=subprocess.PIPE,
            #     stderr=subprocess.PIPE,
            #     text=True
            # )
            process = subprocess.Popen(
                script_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            print(f"脚本执行成功:\n{script_args}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"脚本执行失败 (退出码: {e.returncode}):")
            print(f"错误信息:\n{e.stderr}")
            return False
        except FileNotFoundError:
            print(f"错误: 脚本文件 '{script_args[0]}' 未找到")
            return False
        except PermissionError:
            print(f"错误: 脚本文件 '{script_args[0]}' 不可执行")
            return False

# -------------------------- UDP 服务端类 --------------------------
class EnhancedUDPCommandServer:
    def __init__(self, goal_sender, host='0.0.0.0', port=5005):
        self.host = host
        self.port = port
        self.running = False
        self.socket = None
        self.client_address = None  # 记录最后一个客户端地址，用于回复
        self.goal_sender = goal_sender  # 接收Nav2GoalSender实例

    def start(self):
        """启动UDP服务端"""
        self.running = True
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((self.host, self.port))
        print(f"增强版UDP指令服务端已启动，监听 {self.host}:{self.port}")
        print(f"等待符合协议({HEADER[0]:#04x} {HEADER[1]:#04x})的指令...")
        
        # 使用传入的goal_sender的logger
        self.goal_sender.get_logger().info(f"UDP 控制服务已启动：{self.host}:{self.port}")
        receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
        receive_thread.start()

    def receive_messages(self):
        while self.running:
            try:
                data, client_addr = self.socket.recvfrom(1024)  # 接收数据
                self.client_address = client_addr
                self._process_packet(data, client_addr)
            except Exception as e:
                if self.running:
                    print(f"接收数据出错: {e}")

    def _process_packet(self, data, client_addr):
        if len(data) != 3:
            print(f"来自 {client_addr} 的数据包格式错误，长度应为3字节，实际为{len(data)}字节")
            return
            
        header_byte1 = data[0]
        header_byte2 = data[1]
        cmd_id = data[2]
        
        if [header_byte1, header_byte2] != HEADER:
            print(f"来自 {client_addr} 的包头验证失败，接收:({header_byte1:#04x} {header_byte2:#04x}), 期望:({HEADER[0]:#04x} {HEADER[1]:#04x})")
            return
            
        if cmd_id in COMMAND_MAP:
            cmd_name = COMMAND_MAP[cmd_id]
            print(f"来自 {client_addr} 的有效指令: {cmd_name} (0x{cmd_id:02x})")
            self.goal_sender._execute_command(cmd_id)
        else:
            print(f"来自 {client_addr} 的未知指令: 0x{cmd_id:02x}")

    def stop(self):
        self.running = False
        if self.socket:
            self.socket.close()
        print("服务端已停止")


# -------------------------- 主程序入口 --------------------------
def main(args=None):
    rclpy.init(args=args)
    try:
        goal_sender = Nav2GoalSender()
        # 使用环境变量 UDP_CMD_PORT 配置端口，默认 5005
        udp_server = EnhancedUDPCommandServer(goal_sender, port=UDP_PORT)
        udp_server.start()
        # 运行ROS节点
        rclpy.spin(goal_sender)
    except KeyboardInterrupt:
        goal_sender.get_logger().info("\n收到终止指令，正在停止服务...")
    finally:
        if 'udp_server' in locals():
            udp_server.stop()
        rclpy.shutdown()
        print("所有服务已停止")

if __name__ == '__main__':
    main()
