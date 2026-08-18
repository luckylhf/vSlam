from setuptools import find_packages, setup

package_name = 'audio_http_pkg'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml', 'LICENSE']),
    ],
    install_requires=['setuptools', 'aiohttp', 'sounddevice', 'numpy'],
    zip_safe=True,
    maintainer='Tianhong Huang',
    maintainer_email='tianhong.huang@ubtrobot.com',
    description='语音交互节点：录制语音并通过 HTTP 与大模型服务交互',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'audio_http_node = audio_http_pkg.audio_http_node:main'
        ],
    },
)
