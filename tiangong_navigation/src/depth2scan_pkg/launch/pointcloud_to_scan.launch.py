from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        # 点云转 LaserScan 节点
        Node(
            package='pointcloud_to_laserscan',
            executable='pointcloud_to_laserscan_node',
            name='pointcloud_to_laserscan',
            remappings=[
                ('cloud_in', '/camera/cloud'),  # 深度相机点云话题
                ('scan', '/scan')  # 输出的 2D 激光扫描话题
            ],
            parameters=[{
                # 激光扫描参数（需根据相机安装位置调整）
                'target_frame': 'base_link',  # 转换到机器人基坐标系
                'transform_tolerance': 0.01,
                'use_sim_time': False,
                'use_cloud_timestamp': True,
                'min_height': 0.0,  # 点云最小高度（过滤地面以下）
                'max_height': 1.5,  # 点云最大高度（过滤过高点）
                'angle_min': -2.5708,  # 扫描角度范围（左，单位：弧度，-90度）
                'angle_max': 2.5708,   # 扫描角度范围（右，单位：弧度，90度）
                'angle_increment': 0.0087,  # 角度分辨率（约 0.5 度）
                'scan_time': 0.033,  # 扫描周期（秒）
                'range_min': 0.2,  # 最小检测距离
                'range_max': 10.0,  # 最大检测距离
                'use_inf': True,   # 允许无限远值（超出最大距离时）
                'ros__parameters': {
                    'qos_overrides./scan.publisher.reliability': 'reliable'
                }
            }]
        )
    ])
