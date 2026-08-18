#!/bin/bash
# ============================================================================
# 动作脚本：打招呼
# 配置说明：X86_WS_DIR 为 x86 工作空间根目录，默认 ~/ros2ws
# ============================================================================

X86_WS_DIR="${X86_WS_DIR:-$HOME/ros2ws}"

cd "${X86_WS_DIR}" || {
    echo "无法进入 ${X86_WS_DIR} 目录"
    exit 1
}

source install/setup.bash || {
    echo "无法加载install/setup.bash"
    exit 1
}

timeout 10s ros2 service call /hric/motion/set_motion_number hric_msgs/srv/SetMotionNumber "{is_motion: true, motion_number: 1}"
