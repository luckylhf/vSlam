#!/bin/bash
# ============================================================================
# 动作脚本：停驻
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

timeout 10s ros2 service call /hric/motion/set_motion_mode hric_msgs/srv/SetMotionMode "{walk_mode_request: 3, is_need_swing_arm: false}"
