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
import re

import sys, traceback
import logging
import json
import os, time
import threading
import numpy as np

from util import random_string, validate_data_request, get_s3_resource
from util import create_manifest
from util import read_images_from_fs, read_pcl_from_fs
from view import transform_from_to
from s3_reader import S3Reader
from ros_util import RosUtil

import cv_bridge
from std_msgs.msg import String
import rospy
import subprocess


class RosDataNode:

    DATA_REQUEST_TOPIC = "/mozart/data_request"
    SLEEP_INTERVAL = .000001 # seconds

    def __init__(self, config=None):
        self.logger = logging.getLogger("ros_datanode")
        logging.basicConfig(
            format='%(asctime)s.%(msecs)s:%(name)s:%(thread)d:%(levelname)s:%(process)d:%(message)s',
            level=logging.INFO)

        self.logger.info(f"Start Rosbridge server")
        subprocess.Popen(["roslaunch", "rosbridge_server", "rosbridge_websocket.launch"])
       
        self.dbconfig=config['database']
        self.data_store=config['data_store']
        calibration=config['calibration']

        cal_obj = get_s3_resource().Object(calibration["cal_bucket"], calibration["cal_key"])
        cal_data = cal_obj.get()['Body'].read().decode('utf-8')
        self.cal_json = json.loads(cal_data)

        self.tmp = os.getenv("TMP", default="/tmp")
        self.img_cv_bridge = cv_bridge.CvBridge()

        node_name = "mozart_datanode_{0}".format(random_string(6))

        self.logger.info(f"Init ROS node: {node_name}, future log messages will be redirected to ROS node log")
        rospy.init_node(node_name)
        rospy.Subscriber(RosDataNode.DATA_REQUEST_TOPIC, String, self.data_request_cb)

        rospy.spin()
      

    def init_request(self, request):
        self.manifests = dict() 
        self.topic_dict = dict()
        self.topic_list = list()
        self.topic_active = dict()
        self.topic_index = 0
        self.round_robin = list()
        self.bus_topic = None

        self.request = request
        sensors = self.request['sensor_id']
        for s in sensors:
            self.manifests[s] = create_manifest(request=request, dbconfig=self.dbconfig, sensor_id=s)
            _topic = self.request['ros_topic'][s]
            self.topic_dict[_topic] = []
            self.topic_list.append(_topic)
            self.topic_active[_topic] = True

        self.ros_publishers = dict()

    def __handle_request(self, request):

        try:
            self.init_request(request)
            tasks = []

            sensors = self.request["sensor_id"]
            sensor_topics = self.request['ros_topic']
            sensor_data_types = self.request["data_type"]
            sensor_frame_id = self.request.get("frame_id", dict())

            for s in sensors:
                manifest = self.manifests[s]
                data_type = sensor_data_types[s]
                ros_topic = sensor_topics[s]
                frame_id = sensor_frame_id.get(s, "map")

                ros_data_class = RosUtil.get_data_class(data_type)
                self.ros_publishers[ros_topic] = rospy.Publisher(ros_topic, ros_data_class, queue_size=64)
                time.sleep(1)
                t = threading.Thread(target=self.__publish_sensor, name=s,
                    kwargs={"manifest": manifest, "data_type": data_type, 
                            "ros_topic": ros_topic, "sensor":  s, "frame_id": frame_id})
                tasks.append(t)
                t.start()
                self.logger.info("Started thread:" + t.getName())

            for t in tasks:
                self.logger.info("Wait on thread:" + t.getName())
                t.join()
                self.logger.info("Thread finished:" + t.getName())

            self.logger.info("Flush ROS topics")
            self.__flush_topics()
        except Exception as _:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
            self.logger.error(str(exc_type))
            self.logger.error(str(exc_value))

    def __publish_to_topic(self, topic=None, msg=None):
        self.ros_publishers[topic].publish(msg)

    def __is_topic_alive(self, topic):
        return  self.topic_dict[topic] or self.topic_active[topic]
    
    def __next_round_robin_topic(self,  topic=None, msg=None):
        # add message to topic queue
        self.topic_dict[topic].append(msg)
                
        msg = None
        topic = None

        # round robin through topics
        _ntopics = len(self.topic_list)
        for _topic in self.topic_list:
            self.topic_index = (self.topic_index + 1) % _ntopics
            _topic = self.topic_list[ self.topic_index ]
            if _topic in self.round_robin and any([True for k in self.topic_active.keys() if not (k in self.round_robin) and self.__is_topic_alive(k)]):
                continue

            if self.topic_dict[_topic]:
                msg = self.topic_dict[_topic].pop(0)
                topic = _topic
                break
        
        return topic, msg

    def __flush_topics(self):
        try:
            _ntopics = len(self.topic_list)
              
            msg = None
            topic = None

            _ntopics_flushed = 0
            # rotate through topics and flush them
            self.logger.info("Flushing  ROS topics")
            for _ in range(_ntopics):
                self.topic_index = (self.topic_index + 1) % _ntopics
                _topic = self.topic_list[ self.topic_index ]
                
                if self.topic_dict[_topic]:
                    front = self.topic_dict[_topic].pop(0)
                    msg = front.msg
                    topic = _topic
                else:
                    _ntopics_flushed += 1

                if topic and msg:
                    self.__publish_to_topic(topic=topic, msg=msg)
                
                if _ntopics == _ntopics_flushed:
                    break
            self.logger.info("Flushed ROS topics")

        except Exception as _:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
            self.logger.error(str(exc_type))
            self.logger.error(str(exc_value))
            raise

    def __topic_sleep(self, ros_topic=None):
        factor = len(self.topic_dict[ros_topic]) + 1
        time.sleep(RosDataNode.SLEEP_INTERVAL*factor)

    def __publish_ros_msg(self, topic=None, msg=None):
        try:
            topic, msg = self.__next_round_robin_topic(topic=topic, msg=msg)
            if topic and msg:
                self.__publish_to_topic(topic=topic, msg=msg)

            sensor_topics = [k for k in self.topic_active.keys() if k != self.bus_topic and self.__is_topic_alive(k)]
            if (len(self.round_robin) >= len(sensor_topics)) and self.round_robin:
                self.round_robin.pop(0)
            
        except Exception as _:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
            self.logger.error(str(exc_type))
            self.logger.error(str(exc_value))
            raise

    
    def __publish_image_msg(self, ros_topic=None, image=None, image_ts=None, frame_id=None):
        try:
            ros_image_msg = self.img_cv_bridge.cv2_to_imgmsg(image)
            RosUtil.set_ros_msg_header( ros_msg=ros_image_msg, ts=image_ts, frame_id=frame_id)
            self.__publish_ros_msg(topic=ros_topic, msg=ros_image_msg)
            self.__topic_sleep(ros_topic=ros_topic)
        except BaseException as _:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
            self.logger.error(str(exc_type))
            self.logger.error(str(exc_value))

    def __get_camera_info(self, sensor=None):
        cam_name = sensor.rsplit("/", 1)[1]
        # get parameters from calibration json 
       
        intr_mat_undist = np.asarray(self.cal_json['cameras'][cam_name]['CamMatrix'])
        intr_mat_dist = np.asarray(self.cal_json['cameras'][cam_name]['CamMatrixOriginal'])
        dist_parms = np.asarray(self.cal_json['cameras'][cam_name]['Distortion'])
        lens = self.cal_json['cameras'][cam_name]['Lens']

        return lens, dist_parms, intr_mat_dist, intr_mat_undist

    def __publish_images_from_fs(self, manifest=None,  ros_topic=None, sensor=None, frame_id=None):

        image_reader = dict()
        image_data = dict() 
        image_ts = dict()

        image_request = self.request.get("image", "original")
        if image_request == "undistorted":
            lens, dist_parms, intr_mat_dist, intr_mat_undist = self.__get_camera_info(sensor=sensor)
        
        while True:
            files = None
            while not files and manifest.is_open():
                files = manifest.fetch()
            if not files:
                break

            count = read_images_from_fs(data_store=self.data_store, files=files, 
                image_reader=image_reader, image_data=image_data, image_ts=image_ts)
        
            for i in range(0, count):
                image_reader[i].join()
                if image_request == "undistorted":
                    image = RosUtil.undistort_image(image=image_data[i], lens=lens, dist_parms=dist_parms, 
                        intr_mat_dist=intr_mat_dist, intr_mat_undist=intr_mat_undist) 
                else:
                    image = image_data[i]
                self.__publish_image_msg(ros_topic=ros_topic, image=image, image_ts=image_ts[i], frame_id=frame_id)

            if self.request['preview']:
                break

        self.topic_active[ros_topic] = False

    def __process_s3_image_files(self, ros_topic=None, files=None, resp=None, 
                                frame_id=None,  image_request=None, lens=None, 
                                dist_parms=None, intr_mat_dist=None, intr_mat_undist=None):
        for f in files:
            try:
                path = resp.get(block=True).split(" ", 1)[0]
                image_data = cv2.imread(path)
                if image_request == "undistorted":
                    image = RosUtil.undistort_image(image_data, lens=lens, dist_parms=dist_parms, 
                                intr_mat_dist=intr_mat_dist, intr_mat_undist=intr_mat_undist) 
                else:
                    image = image_data
                image_ts = int(f[2])
                self.__publish_image_msg(ros_topic=ros_topic, image=image, image_ts=image_ts, 
                        frame_id=frame_id)
                os.remove(path)
            except BaseException as _:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
                self.logger.error(str(exc_type))
                self.logger.error(str(exc_value))

    def __publish_images_from_s3(self, manifest=None,  ros_topic=None, sensor=None, frame_id=None):

        req = Queue()
        resp = Queue()

        s3_reader = S3Reader(req, resp)
        s3_reader.start()

        image_request = self.request.get("image", "original")
        lens, dist_parms, intr_mat_dist, intr_mat_undist = self.__get_camera_info(sensor=sensor) if image_request == "undistorted" else (None, None, None, None)

        while True:
            files = None
            while not files and manifest.is_open():
                files = manifest.fetch()
            if not files:
                break

            for f in files:
                bucket = f[0]
                key = f[1]
                req.put(bucket+" "+key)

            self.__process_s3_image_files(ros_topic=ros_topic, files=files, resp=resp, frame_id=frame_id, 
                            image_request=image_request, 
                            lens=lens, dist_parms=dist_parms, 
                            intr_mat_dist=intr_mat_dist, intr_mat_undist=intr_mat_undist)

            if self.request['preview']:
                break

        req.put("__close__")
        s3_reader.join(timeout=2)
        if s3_reader.is_alive():
            s3_reader.terminate()
        
        self.topic_active[ros_topic] = False

    def __publish_pcl_msg(self, ros_topic=None, points=None, reflectance=None, pcl_ts=None, frame_id=None):
        try:
            ros_pcl_msg = RosUtil.pcl_dense_msg(points=points, reflectance=reflectance, ts=pcl_ts, frame_id=frame_id)
            self.__publish_ros_msg(topic=ros_topic, msg=ros_pcl_msg)
            self.__topic_sleep(ros_topic=ros_topic)
        except BaseException as _:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
            self.logger.error(str(exc_type))
            self.logger.error(str(exc_value))


    def __sensor_to_vehicle_matrix(self, sensor):
        cam_name = sensor.rsplit("/", 1)[1]
        return transform_from_to(self.cal_json['cameras'][cam_name]['view'], self.cal_json['vehicle']['view'])
       
    def __process_s3_pcl_files(self, ros_topic=None, files=None, resp=None, 
                                frame_id=None, lidar_view=None, vehicle_transform_matrix=None):
        for f in files:
            try:
                path = resp.get(block=True).split(" ", 1)[0]
                npz = np.load(path)
                pcl_ts= int(f[2])
                points, reflectance = RosUtil.parse_pcl_npz(npz=npz, lidar_view=lidar_view, 
                        vehicle_transform_matrix=vehicle_transform_matrix)
                if not np.isnan(points).any():
                    self.__publish_pcl_msg(ros_topic=ros_topic, points=points, reflectance=reflectance, 
                        pcl_ts=pcl_ts, frame_id=frame_id)
                os.remove(path)
            except BaseException as _:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
                self.logger.error(str(exc_type))
                self.logger.error(str(exc_value))
        
    def __publish_pcl_from_s3(self, manifest=None,  ros_topic=None, sensor=None, frame_id=None):

        req = Queue()
        resp = Queue()

        s3_reader = S3Reader(req, resp)
        s3_reader.start()

        lidar_view = self.request.get("lidar_view", "camera")
        vehicle_transform_matrix = self.__sensor_to_vehicle_matrix(sensor=sensor) if lidar_view == "vehicle" else None
        
        while True:
            files = None
            while not files and manifest.is_open():
                files = manifest.fetch()
            if not files:
                break

            for f in files:
                bucket = f[0]
                key = f[1]
                req.put(bucket+" "+key)

            self.__process_s3_pcl_files(ros_topic=ros_topic, 
                    files=files, resp=resp, frame_id=frame_id,
                    lidar_view=lidar_view, vehicle_transform_matrix=vehicle_transform_matrix)

            if self.request['preview']:
                break

        req.put("__close__")
        s3_reader.join(timeout=2)
        if s3_reader.is_alive():
            s3_reader.terminate()

        self.topic_active[ros_topic] = False

    def __publish_pcl_from_fs(self, manifest=None,  ros_topic=None, sensor=None, frame_id=None):

        pcl_reader = dict() 
        pcl_ts = dict()
        npz = dict()
        
        lidar_view = self.request.get("lidar_view", "camera")
        vehicle_transform_matrix = self.__sensor_to_vehicle_matrix(sensor=sensor) if lidar_view == "vehicle" else None
        
        while True:
            files = None
            while not files and manifest.is_open():
                files = manifest.fetch()
            if not files:
                break

            count = read_pcl_from_fs(data_store=self.data_store, files=files, pcl_reader=pcl_reader, pcl_ts=pcl_ts, npz=npz)
            for i in range(0, count):
                pcl_reader[i].join()
                points, reflectance = RosUtil.parse_pcl_npz(npz=npz[i], lidar_view=lidar_view, 
                    vehicle_transform_matrix=vehicle_transform_matrix)
                if not np.isnan(points).any():
                    self.__publish_pcl_msg(ros_topic=ros_topic, points=points, reflectance=reflectance, 
                        pcl_ts=pcl_ts[i], frame_id=frame_id)

            if self.request['preview']:
                break

        self.topic_active[ros_topic] = False

    def __publish_images(self, manifest=None,  ros_topic=None, sensor=None, frame_id=None):
        if self.data_store['input'] != 's3':
            self.__publish_images_from_fs(manifest=manifest, ros_topic=ros_topic, sensor=sensor, frame_id=frame_id)
        else:
            self.__publish_images_from_s3(manifest=manifest, ros_topic=ros_topic, sensor=sensor, frame_id=frame_id)

    def __publish_pcl(self, manifest=None,  ros_topic=None, sensor=None, frame_id=None):
        if self.data_store['input'] != 's3':
            self.__publish_pcl_from_fs(manifest=manifest, ros_topic=ros_topic, sensor=sensor, frame_id=frame_id)
        else:
            self.__publish_pcl_from_s3(manifest=manifest, ros_topic=ros_topic, sensor=sensor, frame_id=frame_id)

    def __publish_bus(self, manifest=None,  ros_topic=None, frame_id=None):

        self.bus_topic = ros_topic 
        while True:
            rows = None
            while not rows and manifest.is_open():
                rows = manifest.fetch()
            if not rows:
                break
        
            for row in rows:
                try:
                    ros_msg = RosUtil.bus_msg(row=row, frame_id=frame_id)
                    self.__publish_ros_msg(topic=ros_topic, msg=ros_msg)
                    self.__topic_sleep(ros_topic=ros_topic)
                except BaseException as _:
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
                    self.logger.error(str(exc_type))
                    self.logger.error(str(exc_value))

            if self.request['preview']:
                break
        
        self.topic_active[ros_topic] = False

    def __publish_sensor(self, manifest=None, sensor=None, data_type=None, ros_topic=None, frame_id=None):
        try:
            if data_type ==  'sensor_msgs/Image':
                self.__publish_images(manifest=manifest, ros_topic=ros_topic, sensor=sensor, frame_id=frame_id)
            elif data_type == 'sensor_msgs/PointCloud2':
                self.__publish_pcl(manifest=manifest, ros_topic=ros_topic, sensor=sensor, frame_id=frame_id)
            elif data_type ==  'a2d2_msgs/Bus':
                self.__publish_bus(manifest=manifest, ros_topic=ros_topic, frame_id=frame_id)
        except Exception as _:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
            self.logger.error(str(exc_type))
            self.logger.error(str(exc_value))
            
    def data_request_cb(self, ros_msg):
        try:  
            self.logger.info("received ros message: {0}".format(ros_msg.data))
            
            request = json.loads(ros_msg.data)
            self.logger.info("validate data request: {0}".format(request))
            validate_data_request(request)

            self.logger.info("processing data request: {0}".format(request))
            self.__handle_request(request)

            self.logger.info("completed data request: {0}".format(request))
          
        except Exception as _:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
            self.logger.error(str(exc_type))
            self.logger.error(str(exc_value))

            
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Ros Datanode')
    parser.add_argument('--config', type=str,  help='configuration file', required=True)
    
    args = parser.parse_args()

    with open(args.config) as json_file:
        config = json.load(json_file)

    RosDataNode(config)