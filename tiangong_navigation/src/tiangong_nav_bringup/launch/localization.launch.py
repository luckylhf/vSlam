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
          'subscribe_depth': True,
          'subscribe_scan':True,
         # 'Reg/MaxCorrespondenceDistance': '20.1',
         # 'Reg/CorrespondenceRatio': '0.01',
          'use_action_for_goal':True,
          # RTAB-Map's parameters should be strings:
          'Reg/Strategy':'2',
          # 增大 ICP 收敛范围
        'Icp/MaxTranslation': '0.5',  # 从默认0.2增大到0.5米
        'Icp/MaxRotation': '1.0',     # 从默认0.78增大到1.0弧度
    #      'Vis/InlierDistance': '0.6',
    #      'Vis/MaxFeatures':'1000',
    #      'Vis/FeatureType': '3',
    #    'Vis/CorNNDR': '0.7',
    #    'Vis/GridRows': '2', 
    #    'Vis/GridCols': '2',
          'Vis/FeatureType': '2',          # 保持与建图一致，ORB特征
          'Vis/MaxFeatures': '1500',       # 增加特征点数量
          'Vis/CorNNDR': '0.9',            # 放宽匹配阈值
          'Vis/InlierDistance': '0.1',     # 内点筛选
          'Vis/EstimationType': '1',       # 3D->2D PnP，计算量更小
          'Vis/MinInliers': '10',          # 提高匹配内点门槛
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
          'approx_sync_max_interval': 0.5,  # 减少最大同步间隔
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
            'localization', default_value='true',
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

        # 头部相机障碍物检测
        Node(
            package='rtabmap_util', executable='obstacles_detection', output='screen',
            parameters=[{
                'frame_id': 'base_link',
                'Grid/NormalsSegmentation': 'true',
                'Grid/MaxGroundHeight': '0.1',
                'Grid/MaxObstacleHeight': '1.8',
            }],
            remappings=[('cloud', '/camera/cloud'),
                        ('obstacles', '/camera/obstacles'),
                        ('ground', '/camera/ground')]),
     #   Node(
     #       package='pcl_ros',
     #       executable='statistical_outlier_removal',
     #       name='statistical_filter',
     #       output='screen',
     #       parameters=[{
     #           'mean_k': 50,          # 考虑每个点周围50个邻居
     #           'std_dev_mul_thresh': 1.0  # 标准差阈值（超过1倍标准差的点被视为离群点）
     #       }],
     #       remappings=[
     #           ('input', '/camera/cloud_raw'),  # 订阅原始点云
     #           ('output', '/camera/cloud')      # 发布滤波后的点云（供RTAB-Map使用）
     #       ]
     #   ),
    ])
