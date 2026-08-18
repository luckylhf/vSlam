from glob import glob
from setuptools import find_packages, setup

package_name = 'tiangong_nav_bringup'

setup(
    name=package_name,
    version='1.2.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml',
                                   'LICENSE-Apache-2.0',
                                   'LICENSE-BSD-3-Clause']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Tianhong Huang',
    maintainer_email='tianhong.huang@ubtrobot.com',
    description='Robot-specific RTAB-Map and Nav2 bringup configuration.',
    license='Apache-2.0 AND BSD-3-Clause',
)
