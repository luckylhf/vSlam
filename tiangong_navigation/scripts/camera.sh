#!/bin/bash
# ============================================================================
# 相机启动脚本
#
# 配置说明：
#   ORBBEC_WS_DIR ：Orbbec 相机驱动工作空间，默认 ~/orbbec_camera_ros2
#                   通过环境变量配置，避免硬编码路径
# ============================================================================

ORBBEC_WS_DIR="${ORBBEC_WS_DIR:-$HOME/orbbec_camera_ros2}"
ORBBEC_LAUNCH_FILE="${ORBBEC_LAUNCH_FILE:-slam_330.launch.py}"

# 执行setup脚本
if [ ! -f "${ORBBEC_WS_DIR}/install/setup.bash" ]; then
    echo "Orbbec 工作空间未编译: ${ORBBEC_WS_DIR}" >&2
    exit 1
fi
source /opt/ros/humble/setup.bash
source "${ORBBEC_WS_DIR}/install/setup.bash"
ros2 launch orbbec_camera "${ORBBEC_LAUNCH_FILE}"
