# vSlam 1.2

面向 ROS 2 Humble 的人形机器人 RTAB-Map 建图/定位、Nav2 导航、动作和语音交互项目。
v1.2 保留了已运行老版中的机器人 Nav2 参数和 RTAB-Map 启动逻辑，但不内置完整上游源码。

## 运行前提

- Ubuntu 22.04 + ROS 2 Humble。
- `hric_msgs` 和机器人运动服务由机器人厂商提供。
- Orbbec 或兼容相机驱动由部署方提供，并满足下文话题/TF 契约。
- 定位前必须以实际建图产生的 `rtabmap.db` 替换仓库空占位库。

## 依赖与编译

```bash
sudo apt update
sudo apt install \
  ros-humble-navigation2 ros-humble-nav2-bringup \
  ros-humble-rtabmap-ros ros-humble-pointcloud-to-laserscan \
  python3-aiohttp python3-numpy python3-sounddevice

cd ~/code                         # 本目录（tiangong_navigation）
source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

若 Ubuntu/rosdep 源没有 `python3-sounddevice`，可在虚拟环境中执行
`python3 -m pip install -r requirements.txt`。不要将虚拟环境提交到仓库。

## 硬件接口契约

默认启动 `ros2 launch orbbec_camera slam_330.launch.py`。不同驱动的启动文件可通过
`ORBBEC_LAUNCH_FILE` 覆盖。驱动至少要提供：

- `/ob_camera_head/color/image_raw`
- `/ob_camera_head/color/camera_info`
- `/ob_camera_head/depth/image_raw`
- `/ob_camera_waist/color/camera_info`
- `/ob_camera_waist/depth/image_raw`
- 对应光学坐标系 `ob_camera_head_color_optical_frame` 和
  `ob_camera_waist_color_optical_frame`

机器人驱动要提供 `/imu`、`/hric/motion/status`、
`/hric/motion/set_motion_mode` 和动作服务。

## 环境配置

```bash
cp .env.example .env
# 修改路径、IP 和令牌后：
source .env
```

ARM 端默认认为本目录位于 `~/code`；x86 端默认位于 `~/ros2ws`。
使用其他路径时设置 `ARM_WS_DIR` / `X86_WS_DIR`。
`ENABLE_TIME_SYNC` 默认为 `0`；只有在为 `date`/`hwclock` 配置好无交互权限后才可启用。

## 建图

1. x86 端启动厂商驱动和里程计：

   ```bash
   cd "$X86_WS_DIR" && source install/setup.bash
   python3 odom.py
   ```

2. ARM 端启动相机、scan 转换和项目建图配置：

   ```bash
   cd "$ARM_WS_DIR" && source install/setup.bash
   bash scripts/camera.sh
   # 新终端
   ros2 launch depth2scan_pkg pointcloud_to_scan.launch.py
   # 新终端
   ros2 launch tiangong_nav_bringup mapping.launch.py
   ```

3. 建图完成后停止 RTAB-Map，再部署数据库：

   ```bash
   cp ~/.ros/rtabmap.db "$ARM_WS_DIR/rtabmap.db"
   ```

## 定位与导航

```bash
cd "$ARM_WS_DIR"
source install/setup.bash
bash scripts/start_robot.sh
```

`start_robot.sh` 会使用本项目安装的 `localization.launch.py`、
`navigation.launch.py` 和人形机器人专用 `nav2_params.yaml`，不会退回到上游默认参数。

初始位姿：

```bash
bash scripts/init_pose.sh
```

## 双机程序

x86：

```bash
cd "$X86_WS_DIR" && source install/setup.bash
python3 server.py
```

ARM：

```bash
cd "$ARM_WS_DIR" && source install/setup.bash
python3 ros_client.py
ros2 run audio_http_pkg audio_http_node   # 可选
```

`ros_client.py` 的导航点是场地数据，发布前必须按实际地图校准。
仓库已包含按 Apache-2.0 授权的 `wav/1.wav` 至 `wav/10.wav`；默认从当前工作目录的
`wav/` 读取，也可通过 `WAV_DIR` 指定其他已授权的音频目录。

## 发布前验收

```bash
bash -n arm_source.sh x86_source.sh scripts/*.sh scripts/action/*.sh
python3 -m compileall -q .
xmllint --noout src/*/package.xml
colcon build --symlink-install
colcon test
colcon test-result --verbose
```

机器人上还需确认 `/grid_prob_map`、`/localization_pose`、`/plan`、
`/camera/obstacles` 和 `/camera/chest_obstacles` 有稳定输出，再执行低速短距离导航测试。

## 许可证

项目原创部分按根目录 [Apache License 2.0](../LICENSE) 发布。
RTAB-Map 派生启动文件保留 BSD-3-Clause，Nav2 派生参数保留 Apache-2.0。
详见 [NOTICE](../NOTICE) 和 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。

项目所有者已确认原创代码以 Apache License 2.0 对外发布。
