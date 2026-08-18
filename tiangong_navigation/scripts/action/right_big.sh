#!/bin/bash
# ============================================================================
# 动作脚本：大幅右转行走
# 配置说明：X86_WS_DIR 为 x86 工作空间根目录，默认 ~/ros2ws
# ============================================================================

X86_WS_DIR="${X86_WS_DIR:-$HOME/ros2ws}"

# 切换到工作空间目录
cd "${X86_WS_DIR}" || {
    echo "无法进入 ${X86_WS_DIR} 目录"
    exit 1
}

# 加载ROS2环境
source install/setup.bash || {
    echo "无法加载install/setup.bash"
    exit 1
}

timeout 5s ros2 service call /hric/motion/set_motion_mode hric_msgs/srv/SetMotionMode "{walk_mode_request: 4, is_need_swing_arm: false}"
sleep 1
ros2 topic pub -r 10 -t 210 /cmd_vel_nav geometry_msgs/msg/Twist "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: -0.3}}" --qos-reliability reliable --qos-durability volatile
ros2 topic pub -r 10 -t 20 /hric/robot/cmd_vel geometry_msgs/msg/TwistStamped "{header: {frame_id: 'base_link' }, twist: {linear: {x: 0.1, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}}"
timeout 5s ros2 service call /hric/motion/set_motion_mode hric_msgs/srv/SetMotionMode "{walk_mode_request: 3, is_need_swing_arm: false}"
