# SPDX-License-Identifier: BSD-3-Clause
# Derived from rtabmap_ros 0.22.0 rtabmap_demos and modified for this robot.
# Original copyright and license: see ../LICENSE-BSD-3-Clause.

# Example:
#
#   Bringup turtlebot3:
#     $ export TURTLEBOT3_MODEL=waffle
#     $ export LDS_MODEL=LDS-01
#     $ ros2 launch turtlebot3_bringup robot.launch.py
#
#   SLAM:
#     $ ros2 launch rtabmap_demos turtlebot3_rgbd_scan.launch.py
#
#   Navigation (install nav2_bringup package):
#     $ ros2 launch nav2_bringup navigation_launch.py
#     $ ros2 launch nav2_bringup rviz_launch.py
#
#   Teleop:
#     $ ros2 run turtlebot3_teleop teleop_keyboard

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition, UnlessCondition
from launch_ros.actions import Node


def generate_launch_description():

    use_sim_time = LaunchConfiguration('use_sim_time')
    localization = LaunchConfiguration('localization')

    parameters={
          'frame_id':'base_link',
          'use_sim_time':False,
          'subscribe_rgbd':False,
          'subscribe_scan':True,
         # 'Reg/MaxCorrespondenceDistance': '20.1',
         # 'Reg/CorrespondenceRatio': '0.01',
          'use_action_for_goal':True,
          # RTAB-Map's parameters should be strings:
          'Reg/Strategy':'2',
        #  'Vis/InlierDistance': '0.6',
        #  'Vis/MaxFeatures':'1200',
        #  'Vis/FeatureType': '3',
        #'Vis/CorNNDR': '0.7',
        #'Vis/GridRows': '2', 
        #'Vis/GridCols': '2',
        'Vis/FeatureType': '2',          # 保持与建图一致，ORB特征
        'Vis/MaxFeatures': '1500',       # 增加特征点数量
        'Vis/CorNNDR': '0.8',            # 放宽匹配阈值
        'Vis/InlierDistance': '0.1',     # 内点筛选
        'Vis/EstimationType': '1',       # 3D->2D PnP，计算量更小
        'Vis/MinInliers': '15',          # 提高匹配内点门槛
        'Vis/GridRows': '4',             # 强制特征分布在不同区域
        'Vis/GridCols': '4',             # 避免特征聚集
        'Reg/RobustKernel': 'true',  # 启用鲁棒核函数，过滤异常值
        'Mem/LoopSearchRadius': 6.0,  # 搜索半径（米），扩大范围寻找回环
          'Reg/Force3DoF':'true',
          'RGBD/NeighborLinkRefining':'True',
          'Grid/RayTracing':'true', # Fill empty space
          'Grid/3D':'false', # Use 2D occupancy
          'Grid/RangeMax':'6',
        'Reg/RobustKernel': 'true',  # 启用鲁棒核函数，过滤异常值
          'approx_sync': True,
          'approx_sync_max_interval': 0.3,  # 减少最大同步间隔
          'topic_queue_size': 50,
          'sync_queue_size': 100,
          'Grid/NormalsSegmentation':'true', # Use passthrough filter to detect obstacles
          'Grid/Sensor':'2', # Use both laser scan and camera for obstacle detection in global map
          'Grid/MaxGroundHeight':'0.1', # All points above 5 cm are obstacles
          'Grid/MaxObstacleHeight':'1.8',  # All points over 1 meter are ignored
          'Grid/RangeMin':'0.2', # ignore laser scan points on the robot itself
          'Optimizer/GravitySigma':'0.3' # Disable imu constraints (we are already in 2D)
    }

    remappings=[
          ('rgb/image', '/ob_camera_head/color/image_raw'),
          ('rgb/camera_info', '/ob_camera_head/color/camera_info'),
          ('depth/image', '/ob_camera_head/depth/image_raw'),
          ('scan', '/scan')]

    return LaunchDescription([

        # Launch arguments
        DeclareLaunchArgument(
            'use_sim_time', default_value='false',
            description='Use simulation (Gazebo) clock if true'),

        DeclareLaunchArgument(
            'localization', default_value='false',
            description='Launch in localization mode.'),

        # SLAM Mode:
        Node(
            condition=UnlessCondition(localization),
            package='rtabmap_slam', executable='rtabmap', output='screen',
            parameters=[parameters],
            remappings=remappings,
            arguments=['-d']),
        #Node(
        #    package='tf2_ros',
        #    executable='static_transform_publisher',
        #    output='screen',
        #    arguments=['0', '0', '0', '0', '0', '0', 'odom', 'base_link']
        #),

        # 添加第二个静态坐标变换: base_link -> ob_camera_head_link
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            output='screen',
            arguments=['0.1', '0', '1.1', '0', '0.51956', '0', 'base_link', 'ob_camera_head_link']
        ),
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            output='screen',
            arguments=['0', '0', '0.6', '0', '0', '0', 'base_link', 'imu']
        ),    
#        Node(
#            package='rtabmap_sync', executable='rgbd_sync', output='screen',
#            parameters=[{'approx_sync':True,'queue_size': 20,'approx_sync_max_interval': 0.5,'use_sim_time':use_sim_time}],
#            remappings=remappings),
        # Localization mode:
        Node(
            condition=IfCondition(localization),
            package='rtabmap_slam', executable='rtabmap', output='screen',
            parameters=[parameters,
              {'Mem/IncrementalMemory':'False',
               'Mem/InitWMWithAllNodes':'True'}],
            remappings=remappings),

        
        # Obstacle detection with the camera for nav2 local costmap.
        # First, we need to convert depth image to a point cloud.
        # Second, we segment the floor from the obstacles.
        Node(
            package='rtabmap_util', executable='point_cloud_xyz', output='screen',
            parameters=[{'decimation': 4,
                         'max_depth': 5.0,
                         'voxel_size': 0.05}],
            remappings=[('depth/image', '/ob_camera_head/depth/image_raw'),
                        ('depth/camera_info', '/ob_camera_head/color/camera_info'),
                        ('cloud', '/camera/cloud')]),

        # 头部相机障碍物检测（用于 global_costmap）
        Node(
            package='rtabmap_util', executable='obstacles_detection', output='screen',
            parameters=[{
                'frame_id': 'base_link',
                'map_frame_id': 'map',
                'wait_for_transform': 0.2,
                'Grid/NormalsSegmentation': 'true',
                'Grid/MaxGroundHeight': '0.1',
                'Grid/MaxObstacleHeight': '1.8',
            }],
            remappings=[('cloud', '/camera/cloud'),
                        ('obstacles', '/camera/obstacles'),
                        ('ground', '/camera/ground')]),
        
        # 胸部相机点云
        Node(
            package='rtabmap_util', executable='point_cloud_xyz', output='screen',
            parameters=[{'decimation': 4,
                         'max_depth': 4.0,          # 胸部相机近距离
                         'voxel_size': 0.05}],
            remappings=[('depth/image', '/ob_camera_waist/depth/image_raw'),
                        ('depth/camera_info', '/ob_camera_waist/color/camera_info'),
                        ('cloud', '/camera/chest_cloud')]),

        # 胸部相机障碍物检测（用于 local_costmap，仅 rgbd_scan）
        Node(
            package='rtabmap_util', executable='obstacles_detection', output='screen',
            parameters=[{
                'frame_id': 'base_link',
                'map_frame_id': 'map',
                'wait_for_transform': 0.2,
                'Grid/NormalsSegmentation': 'true',
                'Grid/MaxGroundHeight': '0.1',
                'Grid/MaxObstacleHeight': '1.8',
            }],
            remappings=[('cloud', '/camera/chest_cloud'),
                        ('obstacles', '/camera/chest_obstacles'),
                        ('ground', '/camera/chest_ground')]),

    ])
