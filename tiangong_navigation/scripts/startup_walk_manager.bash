#!/bin/bash
# ============================================================================
# 程序自启动脚本（ARM 端）
#
# 配置说明：
#   ARM_WS_DIR ：ARM 端工作空间根目录，默认 ~/code
#                通过环境变量配置，避免硬编码路径
#
# 本脚本依次启动：
#   1. time_sync.py    - x86/arm 时间同步
#   2. audio_http_node - 语音交互节点
#   3. ros_client.py   - arm 客户端，与 x86 server 和规控程序交互
# ============================================================================

sleep 10

ARM_WS_DIR="${ARM_WS_DIR:-$HOME/code}"

if [ -d "${ARM_WS_DIR}" ]; then
  cd "${ARM_WS_DIR}" || { echo "无法进入目录 ${ARM_WS_DIR}"; exit 1; }
  export ROS_HOME=${ARM_WS_DIR}
  source /opt/ros/humble/setup.bash
  source install/setup.bash || { echo "安装目录下无setup.bash"; exit 1; }

  if [ "${ENABLE_TIME_SYNC:-0}" = "1" ]; then
    python3 "${ARM_WS_DIR}/time_sync.py" &
  fi
  ros2 run audio_http_pkg audio_http_node &
  PID1=$!
  sleep 2
  python3 "${ARM_WS_DIR}/ros_client.py" > "${HOME}/ros_client.log" 2>&1 &
  PID2=$!

  wait $PID1 $PID2
  kill -9 $PID2
fi
