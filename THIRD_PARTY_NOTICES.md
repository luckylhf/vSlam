# Third-party software and services

This repository does not vendor the following runtime dependencies. Install them
separately and follow their license terms.

| Dependency | Tested/base version | License | Use |
|---|---:|---|---|
| ROS 2 Humble | Humble | Apache-2.0 and per-package licenses | Runtime |
| Navigation2 | 1.1.18 | Mixed; the derived `nav2_bringup` file here is Apache-2.0 | Navigation |
| RTAB-Map / rtabmap_ros | 0.22.0 | BSD-3-Clause | Mapping/localization |
| pointcloud_to_laserscan | Humble distribution | BSD-3-Clause | Depth conversion |
| Orbbec ROS 2 driver | Deployment-specific | Apache-2.0 for the official driver | Camera driver |
| aiohttp | Deployment-resolved | Apache-2.0 | HTTP client |
| NumPy | Deployment-resolved | BSD-3-Clause | Numeric operations |
| python-sounddevice | Deployment-resolved | MIT | Audio playback |

Upstream sources:

- https://github.com/ros-navigation/navigation2
- https://github.com/introlab/rtabmap
- https://github.com/introlab/rtabmap_ros
- https://github.com/ros-perception/pointcloud_to_laserscan
- https://github.com/orbbec/OrbbecSDK_ROS2
- https://github.com/aio-libs/aiohttp
- https://github.com/numpy/numpy
- https://github.com/spatialaudio/python-sounddevice

`hric_msgs`, the robot motion services, the camera launch implementation and the
remote audio/LLM services are integration interfaces only and are not distributed
by this repository. Each robot vendor or deployer must supply and license them.

The files `tiangong_nav_bringup/launch/localization.launch.py` and
`mapping.launch.py` are derived from rtabmap_ros 0.22.0 and remain BSD-3-Clause.
The file `tiangong_nav_bringup/config/nav2_params.yaml` is derived from
Navigation2 1.1.18 nav2_bringup and remains Apache-2.0.

The prerecorded speech under `tiangong_navigation/wav/` is original project
material, not third-party content, and is licensed under Apache-2.0. Deployers
may override it with another authorized audio directory through `WAV_DIR`.
