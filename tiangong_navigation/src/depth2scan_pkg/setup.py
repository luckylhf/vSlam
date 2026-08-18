from setuptools import setup
import os
from glob import glob

package_name = 'depth2scan_pkg'

setup(
    name=package_name,
    version='1.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml', 'LICENSE']),
        # 添加 launch 目录的安装配置
        (os.path.join('share', package_name, 'launch'), 
            glob(os.path.join('launch', '*launch.[pxy][yma]*')))
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Tianhong Huang',
    maintainer_email='tianhong.huang@ubtrobot.com',
    description='将深度相机点云转换为激光扫描的包',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            # 这里暂时不需要可执行脚本，保持默认即可
        ],
    },
)
