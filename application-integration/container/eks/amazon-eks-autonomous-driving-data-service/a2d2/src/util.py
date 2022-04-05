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
import random
import string
import os
import stat
import errno

import boto3
import cv2
import numpy as np
import threading

from manifest_dataset import ManifestDataset
from bus_dataset import BusDataset

def get_s3_client():
    s3_client = None
    try:
        session = boto3.session.Session()
        s3_client = session.client('s3')
    except Exception as e:
        try:
            print(os.environ['AWS_WEB_IDENTITY_TOKEN_FILE'])
            print(os.environ['AWS_ROLE_ARN'])
            s3_client = boto3.client('s3')
        except Exception as e:
            _, _, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
            print(str(e))

    assert(s3_client != None)
    return s3_client

def get_s3_resource():
    s3_resource = None
    try:
        session = boto3.session.Session()
        s3_resource = session.resource('s3')
    except Exception as e:
        try:
            print(os.environ['AWS_WEB_IDENTITY_TOKEN_FILE'])
            print(os.environ['AWS_ROLE_ARN'])
            s3_resource = boto3.resource('s3')
        except Exception as e:
            _, _, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
            print(str(e))

    return s3_resource

def random_string(length=16):
    s = ''
    sel = string.ascii_lowercase + string.ascii_uppercase + string.digits
    for _ in range(0, length):
        s += random.choice(sel)
    return s

def is_close_msg(json_msg):
    close = False

    try:
        close = json_msg['__close__']
    except KeyError:
        pass

    return close

def mkdir_p(path):
    try:
        os.makedirs(path)
        os.chmod(path, stat.S_IROTH|stat.S_IWOTH|stat.S_IXOTH|stat.S_IRUSR|stat.S_IWUSR|stat.S_IXUSR|stat.S_IRGRP|stat.S_IWGRP|stat.S_IXGRP)
    except OSError as e:
        if e.errno != errno.EEXIST or not os.path.isdir(path):
            raise

def validate_data_request(request):
    assert request["accept"]
    accept = request["accept"]

    if accept != "rosmsg":
        assert request["kafka_topic"]
        if "rosbag" in accept:
            output = accept.split("/", 1)[0]
            assert output in ["s3", "efs", "fsx"]

    assert request["vehicle_id"]
    assert request["scene_id"]
    assert request["sensor_id"]
    
    assert int(request["start_ts"]) > 0 
    assert int(request["stop_ts"]) > int(request["start_ts"]) 
    assert int(request["step"]) > 0

    if "ros" in accept:
        ros_topics = request["ros_topic"]
        data_types = request["data_type"]
        sensors = request["sensor_id"]
        for s in sensors:
            assert data_types[s]
            assert ros_topics[s]

def create_manifest(request=None, dbconfig=None, sensor_id=None):

    if sensor_id == 'bus':
        manifest = BusDataset(dbconfig=dbconfig, 
                        vehicle_id=request["vehicle_id"],
                        scene_id=request["scene_id"],
                        start_ts=int(request["start_ts"]), 
                        stop_ts=int(request["stop_ts"]),
                        step=int(request["step"]))
    else:
        manifest = ManifestDataset(dbconfig=dbconfig, 
                        vehicle_id=request["vehicle_id"],
                        scene_id=request["scene_id"],
                        sensor_id=sensor_id,
                        start_ts=int(request["start_ts"]), 
                        stop_ts=int(request["stop_ts"]),
                        step=int(request["step"]))

    return manifest

def fsx_read_image(data_store=None, id=None, img_path=None, image_data=None):
    ''' read image file from fsx file system '''
    fsx_config = data_store['fsx']
    fsx_root = fsx_config['root']
    image_data[id] = cv2.imread(os.path.join(fsx_root, img_path))
    
    
def fsx_read_pcl_npz(data_store=None, id=None, pcl_path=None, npz=None):
    ''' read pcl npz file from fsx file system '''
    fsx_config = data_store['fsx']
    fsx_root = fsx_config['root']
    pcl_path = os.path.join(fsx_root, pcl_path)
    npz[id] =  np.load(pcl_path)
        
def efs_read_image(data_store=None, id=None, img_path=None, image_data=None):
    ''' read image file from efs file system '''
    efs_config = data_store['efs']
    efs_root = efs_config['root']
    image_data[id] = cv2.imread(os.path.join(efs_root, img_path))
    
    
def efs_read_pcl_npz(data_store=None, id=None, pcl_path=None, npz=None):
    ''' read pcl npz file from efs file system '''
    efs_config = data_store['efs']
    efs_root = efs_config['root']
    pcl_path = os.path.join(efs_root, pcl_path)
    npz[id] =  np.load(pcl_path)

def read_images_from_fs(data_store=None, files=None, image_reader=None, image_data=None, image_ts=None):

    image_reader.clear() 
    image_data.clear()
    image_ts.clear()

    idx = 0
    for f in files:
        if data_store['input'] == 'fsx':
            img_path = f[1]
            image_reader[idx] = threading.Thread(target=fsx_read_image, 
                        kwargs={"data_store": data_store, "id": idx, "img_path": img_path, "image_data": image_data})
        elif data_store['input'] == 'efs':
            img_path = f[1]
            image_reader[idx] = threading.Thread(target=efs_read_image, 
                            kwargs={"data_store": data_store, "id": idx, "img_path": img_path, "image_data": image_data})

        image_reader[idx].start()
        image_ts[idx]= int(f[2])
        idx += 1

    return idx

def read_pcl_from_fs(data_store=None, files=None, pcl_reader=None, pcl_ts=None, npz=None ):
    pcl_reader.clear()
    pcl_ts.clear()
    npz.clear() 

    idx = 0
    for f in files:
        if data_store['input'] == 'fsx':
            pcl_path = f[1]
            pcl_reader[idx] = threading.Thread(target=fsx_read_pcl_npz, 
                            kwargs={"data_store": data_store, "id": idx, "pcl_path": pcl_path, "npz": npz})
        elif data_store['input'] == 'efs':
            pcl_path = f[1]
            pcl_reader[idx] = threading.Thread(target=efs_read_pcl_npz, 
                            kwargs={"data_store": data_store, "id": idx, "pcl_path": pcl_path, "npz": npz})

        pcl_reader[idx].start()
        pcl_ts[idx]= int(f[2])
        idx += 1
        
    return idx