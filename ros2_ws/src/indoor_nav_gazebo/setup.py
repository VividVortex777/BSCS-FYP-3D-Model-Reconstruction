from setuptools import find_packages, setup
from glob import glob
import os

package_name = 'indoor_nav_gazebo'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        (
            'share/ament_index/resource_index/packages',
            ['resource/' + package_name]
        ),
        (
            'share/' + package_name,
            ['package.xml']
        ),
        (
            os.path.join('share', package_name, 'launch'),
            glob('launch/*.py')
        ),
        (
            os.path.join('share', package_name, 'worlds'),
            glob('worlds/*.sdf')
        ),
        # data_files entries must list files only: setuptools cannot copy a
        # directory, so each model sub-folder gets its own entry.
        (
            os.path.join('share', package_name, 'models/fyp_robot'),
            [f for f in glob('models/fyp_robot/*') if os.path.isfile(f)]
        ),
        (
            os.path.join('share', package_name, 'models/fyp_robot/meshes'),
            glob('models/fyp_robot/meshes/*')
        ),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='hammad',
    maintainer_email='hammad@example.com',
    description='FYP indoor Gazebo simulation',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [],
    },
)
