#!/usr/bin/env bash
# 定位 + 导航启动与看门脚本。相机驱动由部署方提供。

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

WORKSPACE_DIR="${ARM_WS_DIR:-$HOME/code}"
ROS_HOME_DIR="${ROS_HOME_DIR:-$HOME/.ros}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAP_SOURCE="${RTABMAP_DB:-$WORKSPACE_DIR/rtabmap.db}"
CHECK_TOPIC='/plan'
CHECK_MAP_TOPIC='/grid_prob_map'
LOCAL_TOPIC='/localization_pose'
TIMEOUT=8
TEMP_FILE="${TMPDIR:-/tmp}/vslam_topic_check.$$"

CAMERA_PID=''
LOCAL_PID=''
NAV_PID=''
SCAN_PID=''

cleanup() {
    printf '\n%b\n' "${YELLOW}正在终止所有节点...${NC}"
    for pid in "$CAMERA_PID" "$LOCAL_PID" "$SCAN_PID" "$NAV_PID"; do
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            kill -INT "$pid" 2>/dev/null || true
        fi
    done
    rm -f "$TEMP_FILE"
}
trap cleanup EXIT INT TERM

if [ ! -f /opt/ros/humble/setup.bash ]; then
    printf '%b\n' "${RED}未找到 ROS 2 Humble: /opt/ros/humble/setup.bash${NC}" >&2
    exit 1
fi
if [ ! -f "$WORKSPACE_DIR/install/setup.bash" ]; then
    printf '%b\n' "${RED}工作空间未编译: ${WORKSPACE_DIR}${NC}" >&2
    exit 1
fi
if [ ! -f "$MAP_SOURCE" ]; then
    printf '%b\n' "${RED}地图数据库不存在: ${MAP_SOURCE}${NC}" >&2
    exit 1
fi
if [ "$(wc -c < "$MAP_SOURCE")" -le 8192 ]; then
    printf '%b\n' "${RED}地图数据库仍是空占位文件，请先建图: ${MAP_SOURCE}${NC}" >&2
    exit 1
fi

source /opt/ros/humble/setup.bash
source "$WORKSPACE_DIR/install/setup.bash"

mkdir -p "$ROS_HOME_DIR"
cp -f "$MAP_SOURCE" "$ROS_HOME_DIR/rtabmap.db"

kill_nav2() {
    pkill -f 'tiangong_nav_bringup navigation.launch.py' >/dev/null 2>&1 || true
    pkill -f lifecycle_manag >/dev/null 2>&1 || true
}

kill_map() {
    pkill -f 'tiangong_nav_bringup localization.launch.py' >/dev/null 2>&1 || true
    pkill -f point_cloud_xyz >/dev/null 2>&1 || true
}

start_localization() {
    ros2 launch tiangong_nav_bringup localization.launch.py &
    LOCAL_PID=$!
}

start_navigation() {
    ros2 launch tiangong_nav_bringup navigation.launch.py &
    NAV_PID=$!
}

printf '%b\n' "${YELLOW}步骤1: 启动相机节点...${NC}"
bash "$SCRIPT_DIR/camera.sh" &
CAMERA_PID=$!

printf '%b\n' "${YELLOW}步骤2: 启动 RTAB-Map 定位...${NC}"
start_localization
ros2 launch depth2scan_pkg pointcloud_to_scan.launch.py &
SCAN_PID=$!
while true; do
    sleep 20
    if ros2 topic list 2>/dev/null | grep -q "^${CHECK_MAP_TOPIC}$"; then
        break
    fi
    printf '%s\n' 'RTAB-Map 未就绪，重启中...'
    kill_map
    start_localization
done

printf '%b\n' "${YELLOW}步骤3: 启动 Nav2...${NC}"
start_navigation
while true; do
    sleep 15
    if ros2 topic list 2>/dev/null | grep -q "^${CHECK_TOPIC}$"; then
        break
    fi
    printf '%s\n' 'Nav2 未就绪，重启中...'
    kill_nav2
    start_navigation
done

printf '%b\n' "${GREEN}========== 系统已成功启动 ==========${NC}"
printf '%b\n' "${YELLOW}按 Ctrl+C 终止所有节点${NC}"

while true; do
    if ! timeout "$TIMEOUT" ros2 topic echo --once "$LOCAL_TOPIC" >"$TEMP_FILE" 2>&1; then
        printf '%s\n' "话题 ${LOCAL_TOPIC} 无数据，重启定位和导航..."
        kill_map
        kill_nav2
        start_localization
        sleep 15
        start_navigation
    elif ! ros2 topic list 2>/dev/null | grep -q "^${CHECK_TOPIC}$"; then
        printf '%s\n' 'Nav2 话题消失，重启中...'
        kill_nav2
        start_navigation
    fi
    sleep 10
done
