
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

import sys, traceback
from multiprocessing import Process, Queue
import logging, time
import json
import cv2
import os
import threading
import numpy as np

import cv_bridge
import rosbag

from kafka import KafkaProducer
from util import random_string, get_s3_resource
from util import get_s3_client, mkdir_p, create_manifest
from util import read_images_from_fs, read_pcl_from_fs
from view import transform_from_to
from s3_reader import S3Reader
from ros_util import RosUtil

class Qmsg:
    def __init__(self, msg=None, ts=None):
        self.msg = msg
        self.ts = ts

class RosbagProducer(Process):

    SLEEP_INTERVAL = .000001 # seconds

    def __init__(self, dbconfig=None, servers=None,
                request=None, data_store=None, calibration=None):
        Process.__init__(self)
        logging.basicConfig(
            format='%(asctime)s.%(msecs)s:%(name)s:%(thread)d:%(levelname)s:%(process)d:%(message)s',
            level=logging.INFO)
        self.logger = logging.getLogger("rosbag_producer")

        self.servers = servers
        self.request = request

        self.data_store = data_store
        self.calibration = calibration
        self.tmp = os.getenv("TMP", default="/tmp")

        self.img_cv_bridge = cv_bridge.CvBridge()

        self.manifests = dict() 
        sensors = self.request['sensor_id']
        self.topic_dict = dict()
        self.topic_list = list()
        self.topic_active = dict()
        self.topic_index = 0
        self.round_robin = list()
        self.bus_topic = None

        for s in sensors:
            self.manifests[s] = create_manifest(request=request, dbconfig=dbconfig, sensor_id=s)
            _topic = self.request['ros_topic'][s]
            self.topic_dict[_topic] = []
            self.topic_list.append(_topic)
            self.topic_active[_topic] = True

        if len(sensors) > 1:
            self.bag_lock = threading.Lock()
        else:
            self.bag_lock = None

        self.bag = None
        self.bag_path = None
        self.bag_name = None

        self.multipart = 'multipart' in request['accept']

        if self.multipart:
            self.msg_count = 0

        self.accept = request['accept']
        if self.accept.startswith('s3/'):
            s3_config = self.data_store['s3']
            self.rosbag_bucket = s3_config['rosbag_bucket']
            self.rosbag_prefix = s3_config['rosbag_prefix']
            if not self.rosbag_prefix.endswith("/"):
                self.rosbag_prefix += "/"

        if self.multipart:
            self.chunk_count = len(self.topic_list)*2

        cal_obj = get_s3_resource().Object(calibration["cal_bucket"], calibration["cal_key"])
        cal_data = cal_obj.get()['Body'].read().decode('utf-8')
        self.cal_json = json.loads(cal_data) 

    def __create_bag_dir(self):
        if self.accept.startswith('s3/'):
            self.bag_dir = os.path.join(self.tmp, self.request['response_topic'])
        elif self.accept.startswith('fsx/'):
            fsx_config = self.data_store['fsx']
            self.bag_dir = os.path.join(fsx_config['rosbag'], self.request['response_topic'])
        elif self.accept.startswith('efs/'):
            efs_config = self.data_store['efs']
            self.bag_dir = os.path.join(efs_config['rosbag'], self.request['response_topic'])

        mkdir_p(self.bag_dir) 

    def __open_bag(self):
        if self.multipart:
            name = "input-{0}.bag".format(self.msg_count)
        else:
            name = "input.bag"

        self.bag_name = name
        self.bag_path = os.path.join(self.bag_dir, name)
        self.bag = rosbag.Bag(self.bag_path, 'w')

    def __close_bag(self, s3_client=None):
        if self.bag:
            self.bag.close()
            resp_topic = self.request['response_topic']
            if self.accept.startswith("s3/"):
                if s3_client == None:
                    s3_client = get_s3_client()
                prefix = self.rosbag_prefix + resp_topic + "/"
                key = prefix +  self.bag_name
                json_msg = { "output": "s3", "bag_bucket": self.rosbag_bucket, 
                        "bag_prefix": prefix, 
                        "bag_name": self.bag_name, "multipart": self.multipart} 
                with open(self.bag_path, 'rb') as data:
                    s3_client.upload_fileobj(data, self.rosbag_bucket, key)
                    data.close()
                    os.remove(self.bag_path)
            elif self.accept.startswith("fsx/"):
                json_msg = { "output": "fsx", "bag_path": self.bag_path , 
                    "multipart": self.multipart} 
            elif self.accept.startswith("efs/"):
                json_msg = { "output": "efs", "bag_path": self.bag_path , 
                    "multipart": self.multipart} 

            self.producer.send(resp_topic, json.dumps(json_msg).encode('utf-8'))

            self.bag = None
            self.bag_path = None

    def __write_ros_msg_to_bag(self, topic=None, msg=None, ts=None, s3_client=None, flush=False):

        if not self.bag:
            self.__open_bag()
        self.bag.write(topic, msg, ts)
                
        if not flush and topic != self.bus_topic:
            self.round_robin.append(topic)
            if self.multipart:
                self.msg_count += 1
                if self.msg_count % self.chunk_count == 0:
                    self.__close_bag(s3_client=s3_client)

    def __is_topic_alive(self, topic):
        return  self.topic_dict[topic] or self.topic_active[topic]
    
    def __next_round_robin_topic(self,  topic=None, msg=None, ts=None):
        # add message to topic queue
        self.topic_dict[topic].append(Qmsg(msg=msg, ts=ts))
                
        msg = None
        ts = None
        topic = None

        # round robin through topics
        _ntopics = len(self.topic_list)
        for _topic in self.topic_list:
            self.topic_index = (self.topic_index + 1) % _ntopics
            _topic = self.topic_list[ self.topic_index ]
            if _topic in self.round_robin and any([True for k in self.topic_active.keys() if not (k in self.round_robin) and self.__is_topic_alive(k)]):
                continue

            if self.topic_dict[_topic]:
                front = self.topic_dict[_topic].pop(0)
                msg = front.msg
                ts = front.ts
                topic = _topic
                break
        
        return topic, msg, ts

    def __flush_bag(self):
        try:
            if self.bag_lock:
                self.bag_lock.acquire()

            _ntopics = len(self.topic_list)
              
            msg = None
            ts = None
            topic = None

            _ntopics_flushed = 0
            # rotate through topics and flush them to bag
            self.logger.info("Flushing  ROS topics to bag")
            for _ in range(_ntopics):
                self.topic_index = (self.topic_index + 1) % _ntopics
                _topic = self.topic_list[ self.topic_index ]
                
                if self.topic_dict[_topic]:
                    front = self.topic_dict[_topic].pop(0)
                    msg = front.msg
                    ts = front.ts
                    topic = _topic
                else:
                    _ntopics_flushed += 1

                if topic and msg and ts:
                    self.__write_ros_msg_to_bag(topic=topic, msg=msg, ts=ts, s3_client=None, flush=True)
                
                if _ntopics == _ntopics_flushed:
                    break
            self.logger.info("Flushed ROS topics to bag")

        except Exception as _:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
            self.logger.error(str(exc_type))
            self.logger.error(str(exc_value))
            raise
        finally:    
            if self.bag_lock:
                self.bag_lock.release()
    

    def __topic_sleep(self, ros_topic=None):
        if self.bag_lock:
            factor = len(self.topic_dict[ros_topic]) + 1
            time.sleep(RosbagProducer.SLEEP_INTERVAL*factor)

    def __record_ros_msg(self, topic=None, msg=None, ts=None, s3_client=None):
        try:
            if self.bag_lock:
                self.bag_lock.acquire()

            topic, msg, ts = self.__next_round_robin_topic(topic=topic, msg=msg, ts=ts)
            if topic and msg and ts:
                self.__write_ros_msg_to_bag(topic=topic, msg=msg, ts=ts, s3_client=s3_client)

            sensor_topics = [k for k in self.topic_active.keys() if k != self.bus_topic and self.__is_topic_alive(k)]
            if (len(self.round_robin) >= len(sensor_topics)) and self.round_robin:
                self.round_robin.pop(0)
            
        except Exception as _:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
            self.logger.error(str(exc_type))
            self.logger.error(str(exc_value))
            raise
        finally:
            if self.bag_lock:
                self.bag_lock.release()

    
    def __record_image_msg(self, ros_topic=None, image=None, image_ts=None, frame_id=None, s3_client=None):
        try:
            ros_image_msg = self.img_cv_bridge.cv2_to_imgmsg(image)
            RosUtil.set_ros_msg_header( ros_msg=ros_image_msg, ts=image_ts, frame_id=frame_id)
            self.__record_ros_msg(topic=ros_topic, msg=ros_image_msg, ts=ros_image_msg.header.stamp, s3_client=s3_client)
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


    def __record_images_from_fs(self, manifest=None,  ros_topic=None, sensor=None, frame_id=None):

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

            count = read_images_from_fs(data_store=self.data_store, files=files, image_reader=image_reader, 
                image_data=image_data, image_ts=image_ts)
        
            for i in range(0, count):
                image_reader[i].join()
                if image_request == "undistorted":
                    image = RosUtil.undistort_image(image=image_data[i], lens=lens, dist_parms=dist_parms, 
                        intr_mat_dist=intr_mat_dist, intr_mat_undist=intr_mat_undist) 
                else:
                    image = image_data[i]
                self.__record_image_msg(ros_topic=ros_topic, image=image, image_ts=image_ts[i], frame_id=frame_id)

            if self.request['preview']:
                break

        self.topic_active[ros_topic] = False

    def __process_s3_image_files(self, ros_topic=None, files=None, resp=None, 
                                frame_id=None,  s3_client=None, image_request=None, lens=None, 
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
                self.__record_image_msg(ros_topic=ros_topic, image=image, image_ts=image_ts, 
                        frame_id=frame_id, s3_client=s3_client)
                os.remove(path)
            except BaseException as _:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
                self.logger.error(str(exc_type))
                self.logger.error(str(exc_value))

    def __record_images_from_s3(self, manifest=None,  ros_topic=None, sensor=None, frame_id=None):

        s3_client = get_s3_client()

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
                            s3_client=s3_client, image_request=image_request, 
                            lens=lens, dist_parms=dist_parms, intr_mat_dist=intr_mat_dist, intr_mat_undist=intr_mat_undist)

            if self.request['preview']:
                break

        req.put("__close__")
        s3_reader.join(timeout=2)
        if s3_reader.is_alive():
            s3_reader.terminate()
        
        self.topic_active[ros_topic] = False

    def __record_pcl_msg(self, ros_topic=None, points=None, reflectance=None, pcl_ts=None, frame_id=None, s3_client=None):
        try:
            ros_pcl_msg = RosUtil.pcl_dense_msg(points=points, reflectance=reflectance, ts=pcl_ts, frame_id=frame_id)
            self.__record_ros_msg(topic=ros_topic, msg=ros_pcl_msg, ts=ros_pcl_msg.header.stamp, s3_client=s3_client)
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
                                frame_id=None, s3_client=None,
                                lidar_view=None, vehicle_transform_matrix=None):
        for f in files:
            try:
                path = resp.get(block=True).split(" ", 1)[0]
                npz = np.load(path)
                pcl_ts= int(f[2])
                points, reflectance = RosUtil.parse_pcl_npz(npz=npz, lidar_view=lidar_view, 
                        vehicle_transform_matrix=vehicle_transform_matrix)
                if not np.isnan(points).any():
                    self.__record_pcl_msg(ros_topic=ros_topic, points=points, reflectance=reflectance, 
                        pcl_ts=pcl_ts, frame_id=frame_id, s3_client=s3_client)
                os.remove(path)
            except BaseException as _:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
                self.logger.error(str(exc_type))
                self.logger.error(str(exc_value))
        
    def __record_pcl_from_s3(self, manifest=None,  ros_topic=None, sensor=None, frame_id=None):

        s3_client = get_s3_client()

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
                    files=files, resp=resp, frame_id=frame_id, s3_client=s3_client,
                    lidar_view=lidar_view, vehicle_transform_matrix=vehicle_transform_matrix)

            if self.request['preview']:
                break

        req.put("__close__")
        s3_reader.join(timeout=2)
        if s3_reader.is_alive():
            s3_reader.terminate()

        self.topic_active[ros_topic] = False

    def __record_pcl_from_fs(self, manifest=None,  ros_topic=None, sensor=None, frame_id=None):

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

            count = read_pcl_from_fs(data_store=self.data_store, files=files, 
                pcl_reader=pcl_reader, pcl_ts=pcl_ts, npz=npz)
            for i in range(0, count):
                pcl_reader[i].join()
                points, reflectance = RosUtil.parse_pcl_npz(npz=npz[i], lidar_view=lidar_view, 
                    vehicle_transform_matrix=vehicle_transform_matrix)
                if not np.isnan(points).any():
                    self.__record_pcl_msg(ros_topic=ros_topic, points=points, reflectance=reflectance, 
                        pcl_ts=pcl_ts[i], frame_id=frame_id)

            if self.request['preview']:
                break

        self.topic_active[ros_topic] = False

    def __reecord_images(self, manifest=None,  ros_topic=None, sensor=None, frame_id=None):
        if self.data_store['input'] != 's3':
            self.__record_images_from_fs(manifest=manifest, ros_topic=ros_topic, sensor=sensor, frame_id=frame_id)
        else:
            self.__record_images_from_s3(manifest=manifest, ros_topic=ros_topic, sensor=sensor, frame_id=frame_id)

    def __record_pcl(self, manifest=None,  ros_topic=None, sensor=None, frame_id=None):
        if self.data_store['input'] != 's3':
            self.__record_pcl_from_fs(manifest=manifest, ros_topic=ros_topic, sensor=sensor, frame_id=frame_id)
        else:
            self.__record_pcl_from_s3(manifest=manifest, ros_topic=ros_topic, sensor=sensor, frame_id=frame_id)

    def __record_bus(self, manifest=None,  ros_topic=None, frame_id=None):

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
                    self.__record_ros_msg(topic=ros_topic, msg=ros_msg, ts=ros_msg.header.stamp)
                    self.__topic_sleep(ros_topic=ros_topic)
                except BaseException as _:
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
                    self.logger.error(str(exc_type))
                    self.logger.error(str(exc_value))

            if self.request['preview']:
                break
        
        self.topic_active[ros_topic] = False

    def __record_sensor(self, manifest=None, sensor=None, data_type=None, ros_topic=None, frame_id=None):
        try:
            if data_type ==  'sensor_msgs/Image':
                self.__reecord_images(manifest=manifest, ros_topic=ros_topic, sensor=sensor, frame_id=frame_id)
            elif data_type == 'sensor_msgs/PointCloud2':
                self.__record_pcl(manifest=manifest, ros_topic=ros_topic, sensor=sensor, frame_id=frame_id)
            elif data_type ==  'a2d2_msgs/Bus':
                self.__record_bus(manifest=manifest, ros_topic=ros_topic, frame_id=frame_id)
        except Exception as _:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
            self.logger.error(str(exc_type))
            self.logger.error(str(exc_value))

    def run(self):

        try:
            self.producer = KafkaProducer(bootstrap_servers=self.servers, 
                    client_id=random_string())

            self.__create_bag_dir()

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
                t = threading.Thread(target=self.__record_sensor, name=s,
                    kwargs={"manifest": manifest, "data_type": data_type, 
                            "ros_topic": ros_topic, "sensor":  s, "frame_id": frame_id})
                tasks.append(t)
                t.start()
                self.logger.info("Started thread:" + t.getName())

            for t in tasks:
                self.logger.info("Wait on thread:" + t.getName())
                t.join()
                self.logger.info("Thread finished:" + t.getName())

            self.logger.info("Flush ROS bag")
            self.__flush_bag()

            self.logger.info("Close ROS bag")
            self.__close_bag()

            json_msg = {"__close__": True} 
            resp_topic = self.request['response_topic']
            self.producer.send(resp_topic, json.dumps(json_msg).encode('utf-8'))

            self.producer.flush()
            self.producer.close()
            print("completed request:"+resp_topic)
        except Exception as _:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
            self.logger.error(str(exc_type))
            self.logger.error(str(exc_value))
        
