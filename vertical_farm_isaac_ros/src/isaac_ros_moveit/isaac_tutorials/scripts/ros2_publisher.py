#!/usr/bin/env python3

# Copyright (c) 2020-2022, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import numpy as np
import time


class TestROS2Bridge(Node):
    def __init__(self):

        super().__init__("test_ros2bridge")

        # Create the publisher. This publisher will publish a JointState message to the /joint_command topic.
        self.publisher_ = self.create_publisher(JointState, "joint_command", 10)

        # Create a JointState message
        self.joint_state = JointState()
        
        self.joint_state.name = [
            "ur_arm_shoulder_lift_joint",
            "ur_arm_elbow_joint",
            "ur_arm_wrist_1_joint",
            "ur_arm_wrist_2_joint",
            "ur_arm_wrist_3_joint",
        ]
        
        num_joints = len(self.joint_state.name)

        # make sure kit's editor is playing for receiving messages
        self.joint_state.position = np.array([0.1] * num_joints, dtype=np.float64).tolist()
        self.joint_state.effort = np.array([0.0] * num_joints, dtype=np.float64).tolist()
        self.default_joints = [0.1, 0.1, 0.2, 0.1, -0.0]
        #self.default_joints = [0.0]
        # limiting the movements to a smaller range (this is not the range of the robot, just the range of the movement
        self.max_joints = np.array(self.default_joints) + 0.5
        self.min_joints = np.array(self.default_joints) - 0.5

        # position control the robot to wiggle around each joint
        self.time_start = time.time()

        timer_period = 0.05  # seconds
        self.timer = self.create_timer(timer_period, self.timer_callback)
        
        self.timesteps = 0

    def timer_callback(self):
        self.timesteps += 1
        self.joint_state.header.stamp = self.get_clock().now().to_msg()

        joint_position = (
            np.array( self.default_joints
        ))
        if self.timesteps <= 10:
            joint_position[0] = (time.time() - self.time_start) * np.pi  
        self.joint_state.position = joint_position.tolist()
        print(self.joint_state.position)
        # Publish the message to the topic
        self.publisher_.publish(self.joint_state)


def main(args=None):
    rclpy.init(args=args)

    ros2_publisher = TestROS2Bridge()

    rclpy.spin(ros2_publisher)

    # Destroy the node explicitly
    ros2_publisher.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
