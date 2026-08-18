#!/usr/bin/env bash
# ============================================================================
# ARM 端 ROS 2 环境加载脚本
#
# 配置说明（通过环境变量配置，避免硬编码绝对路径）：
#   ARM_WS_DIR          ：ARM 端工作空间根目录，默认 ~/code
#   ORBBEC_WS_DIR       ：Orbbec 相机驱动工作空间，默认 ~/orbbec_camera_ros2
#   ABCDVOICE_WS_DIR    ：语音相关包工作空间，默认 ~/Documents/abcdvoice/fish
# ============================================================================

source /opt/ros/humble/setup.bash

# ARM 工作空间
ARM_WS_DIR="${ARM_WS_DIR:-$HOME/code}"
source "${ARM_WS_DIR}/install/setup.bash"

# Orbbec 相机驱动工作空间
ORBBEC_WS_DIR="${ORBBEC_WS_DIR:-$HOME/orbbec_camera_ros2}"
if [ -f "${ORBBEC_WS_DIR}/install/setup.bash" ]; then
    source "${ORBBEC_WS_DIR}/install/setup.bash"
fi

# 语音相关包工作空间
ABCDVOICE_WS_DIR="${ABCDVOICE_WS_DIR:-$HOME/Documents/abcdvoice/fish}"
if [ -f "${ABCDVOICE_WS_DIR}/install/setup.bash" ]; then
    source "${ABCDVOICE_WS_DIR}/install/setup.bash"
fi

echo "ROS environment loaded."
