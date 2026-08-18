#!/bin/bash
# ============================================================================
# 机器人初始位姿发布脚本
#
# 配置说明：
#   ARM_WS_DIR ：ARM 端工作空间根目录，默认 ~/code
#                通过环境变量配置，避免硬编码路径
#
# 注意：以下 X/Y/Z/W 为初始定位坐标，请通过 RViz 查看实际场地坐标后修改。
# ============================================================================

ARM_WS_DIR="${ARM_WS_DIR:-$HOME/code}"

# 切换到工作空间
cd "${ARM_WS_DIR}" || {
    echo "ERROR: 无法进入 ${ARM_WS_DIR} 目录"
    exit 1
}

# 加载ROS2环境
source install/setup.bash || {
    echo "ERROR: 无法加载ROS2环境"
    exit 1
}

# 定义初始定位参数（请根据实际场地通过 RViz 查看后修改）
X=-3.762               # x坐标（米）
Y=2.439               # y坐标（米）
W=0.6848917             # 航向角四元数 w 分量（cos(yaw/2)）
Z=-0.7286448             # 航向角四元数 z 分量（sin(yaw/2)）
FRAME_ID="map"      # 坐标系（通常为map）
TIMEOUT=5           # 超时时间（秒）

# 发布初始位姿消息
timeout 5s ros2 topic pub -1 /initialpose geometry_msgs/msg/PoseWithCovarianceStamped "
header:
  stamp:
    sec: $(date +%s)
    nanosec: 0
  frame_id: '$FRAME_ID'
pose:
  pose:
    position:
      x: $X
      y: $Y
      z: 0.0
    orientation:
      x: 0.0
      y: 0.0
      z: $Z  # 计算z分量（sin(yaw/2)）
      w: $W  # 计算w分量（cos(yaw/2)）
  covariance: [0.25, 0.0, 0.0, 0.0, 0.0, 0.0,
               0.0, 0.25, 0.0, 0.0, 0.0, 0.0,
               0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
               0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
               0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
               0.0, 0.0, 0.0, 0.0, 0.0, 0.0685]
"

# 检查发布是否成功
if [ $? -eq 0 ]; then
    echo "初始化定位位置已成功发送"
else
    echo "ERROR: 发送初始化定位位置失败"
    exit 1
fi
