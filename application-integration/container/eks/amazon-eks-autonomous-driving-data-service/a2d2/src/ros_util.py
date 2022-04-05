'''
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

Permission is hereby granted, free of charge, to any person obtaining a copy of this
software and associated documentation files (the "Software"), to deal in the Software
without restriction, including without limitation the rights to use, copy, modify,
merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
'''
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import time
import numpy as np
import cv2

from sensor_msgs.msg import Image, PointCloud2, PointField
from a2d2_msgs.msg import Bus

class RosUtil(object):

    @classmethod
    def get_topics_types(cls, reader):
        topics = reader.get_type_and_topic_info()[1] 
        topic_types = dict() 

        for topic, topic_tuple in topics.items():
            topic_types[topic] = topic_tuple[0]
        
        return topic_types

    @classmethod
    def get_data_class(cls, data_type):
        data_class = None
        if data_type == 'sensor_msgs/Image':
            data_class = Image
        elif data_type == 'sensor_msgs/PointCloud2':
            data_class = PointCloud2
        elif data_type == 'a2d2_msgs/Bus':
            data_class = Bus
        else:
            raise ValueError("Data type not supported:" + str(data_type))

        return data_class

    @classmethod
    def set_ros_msg_received_time(cls, ros_msg):
        _ts = time.time()*1000000
        _stamp = divmod(_ts, 1000000 ) #stamp in micro secs
        
        ros_msg.header.stamp.secs = int(_stamp[0]) # secs
        ros_msg.header.stamp.nsecs = int(_stamp[1]*1000) # nano secs


    @classmethod
    def set_ros_msg_header(cls, ros_msg=None, ts=None, frame_id=None):
        ros_msg.header.frame_id = frame_id

        _stamp = divmod(ts, 1000000 ) #stamp in micro secs
        ros_msg.header.stamp.secs = int(_stamp[0]) # secs
        ros_msg.header.stamp.nsecs = int(_stamp[1]*1000) # nano secs

    @classmethod
    def bus_msg(cls, row=None, frame_id=None):
        msg = Bus()

        ts = row[2]
        cls.set_ros_msg_header(ros_msg=msg, ts=ts, frame_id=frame_id)

        # linear accel
        msg.vehicle_kinematics.acceleration.x = row[3]
        msg.vehicle_kinematics.acceleration.y = row[4]
        msg.vehicle_kinematics.acceleration.z = row[5]

        # accelerator control
        msg.control.accelerator_pedal = row[6]
        msg.control.accelerator_pedal_gradient_sign = row[7]

        # angular velocity
        msg.vehicle_kinematics.angular_velocity.omega_x = row[8]
        msg.vehicle_kinematics.angular_velocity.omega_y = row[9]
        msg.vehicle_kinematics.angular_velocity.omega_z = row[10]

        # brake pressure
        msg.control.brake_pressure = row[11]

        # distance pulse
        msg.distance_pulse.front_left = row[12]
        msg.distance_pulse.front_right = row[13]
        msg.distance_pulse.rear_left = row[14]
        msg.distance_pulse.rear_right = row[15]

        # geo location
        msg.geo_loction.latitude = row[16]
        msg.geo_loction.latitude_direction = row[17]
        msg.geo_loction.longitude = row[18]
        msg.geo_loction.longitude_direction = row[19]

        # angular orientation
        msg.vehicle_kinematics.angular_orientation.pitch_angle = row[20]
        msg.vehicle_kinematics.angular_orientation.roll_angle = row[21]

        # steering 
        msg.control.steeering_angle_calculated = row[22]
        msg.control.steering_angle_calculated_sign = row[23]

        # vehicle speed
        msg.vehicle_kinematics.vehicle_speed = row[24]

        return msg

    @classmethod
    def __point_field(cls, name, offset, datatype=PointField.FLOAT32, count=1):
        return PointField(name, offset, datatype, count)

    @classmethod
    def get_pcl_fields(cls):
        return [
            cls.__point_field('x', 0),
            cls.__point_field('y', 4),
            cls.__point_field('z', 8),
            cls.__point_field('r', 12),
            cls.__point_field('g', 16),
            cls.__point_field('b', 20)
        ]

    @classmethod
    def pcl_sparse_msg(cls, points=None, reflectance=None, rows=None, cols=None, ts=None, frame_id=None):
  
        rows = (rows + 0.5).astype(np.int)
        height= np.amax(rows) + 1
        
        cols = (cols + 0.5).astype(np.int)
        width=np.amax(cols) + 1

        colors = np.stack([reflectance, reflectance, reflectance], axis=1)
        pca = np.full((height, width, 3), np.inf)
        ca =np.full((height, width, 3), np.inf)
        assert(pca.shape == ca.shape)

        count = points.shape[0]
        for i in range(0, count):
            pca[rows[i], cols[i], :] = points[i]
            ca[rows[i], cols[i], : ] = colors[i]
            
        msg = PointCloud2()
        cls.set_ros_msg_header(ros_msg=msg, ts=ts, frame_id=frame_id)
        
        msg.width = width
        msg.height = height
        
        msg.fields = cls.get_pcl_fields()

        msg.is_bigendian = False
        msg.point_step = 24
        msg.row_step = msg.point_step * width
        msg.is_dense = False
        data_array = np.array(np.hstack([pca, ca]), dtype=np.float32)
        msg.data = data_array.tostring()

        return msg

    @classmethod
    def pcl_dense_msg(cls, points=None, reflectance=None, ts=None, frame_id=None):
  
        colors = np.stack([reflectance, reflectance, reflectance], axis=1)
        assert(points.shape == colors.shape)
    
        msg = PointCloud2()
        cls.set_ros_msg_header(ros_msg=msg, ts=ts, frame_id=frame_id)
        
        msg.width = points.shape[0]
        msg.height = 1
        
        msg.fields = msg.fields = cls.get_pcl_fields()

        msg.is_bigendian = False
        msg.point_step = 24
        msg.row_step = msg.point_step * msg.width
        msg.is_dense = True
        data_array = np.array(np.hstack([points, colors]), dtype=np.float32)
        msg.data = data_array.tostring()

        return msg

    @classmethod
    def undistort_image(cls, image=None, lens=None, dist_parms=None, intr_mat_dist=None, intr_mat_undist=None):
            
        if (lens == 'Fisheye'):
            return cv2.fisheye.undistortImage(image, intr_mat_dist,
                                        D=dist_parms, Knew=intr_mat_undist)
        elif (lens == 'Telecam'):
            return cv2.undistort(image, intr_mat_dist, 
                        distCoeffs=dist_parms, newCameraMatrix=intr_mat_undist)
        else:
            return image

    @classmethod
    def transform_points_frame(cls, points=None, trans=None):
        points_hom = np.ones((points.shape[0], 4))
        points_hom[:, 0:3] = points
        points_trans = (np.matmul(trans, points_hom.T)).T 
    
        return points_trans

    @classmethod
    def parse_pcl_npz(cls, npz=None, lidar_view=None, vehicle_transform_matrix=None):
        reflectance = npz["pcloud_attr.reflectance"]

        if lidar_view == "vehicle":
            points_trans = cls.transform_points_frame(points=npz["pcloud_points"], trans=vehicle_transform_matrix)
            points = points_trans[:,0:3]
        else:
            points = npz["pcloud_points"]

        return points, reflectance