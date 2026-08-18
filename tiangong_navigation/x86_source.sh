#!/usr/bin/env bash
# ============================================================================
# x86 端 ROS 2 环境加载脚本
#
# 配置说明（通过环境变量配置，避免硬编码绝对路径）：
#   X86_WS_DIR ：x86 端工作空间根目录，默认 ~/ros2ws
# ============================================================================

source /opt/ros/humble/setup.bash

X86_WS_DIR="${X86_WS_DIR:-$HOME/ros2ws}"
source "${X86_WS_DIR}/install/setup.bash"

echo "ROS environment loaded."
