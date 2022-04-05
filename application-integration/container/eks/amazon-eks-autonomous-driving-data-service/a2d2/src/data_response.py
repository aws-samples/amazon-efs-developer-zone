
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
from multiprocessing import Process
import logging, time
import json
import random
import string
import os
import threading

from manifest_producer import ManifestProducer
from rosbag_producer import RosbagProducer
from util import random_string

class DataResponse(Process):
    def __init__(self, dbconfig=None, servers=None,
                request=None, data_store=None, calibration=None):
        Process.__init__(self)
        logging.basicConfig(
            format='%(asctime)s.%(msecs)s:%(name)s:%(thread)d:%(levelname)s:%(process)d:%(message)s',
            level=logging.INFO)
        self.logger = logging.getLogger("data_response")

        self.dbconfig = dbconfig
        self.servers = servers
        self.request = request
        self.data_store = data_store
        self.calibration = calibration


    def rosbag_response(self):
        try:
            t = RosbagProducer(dbconfig=self.dbconfig, 
                    servers=self.servers, request=self.request,
                    data_store=self.data_store, calibration=self.calibration)

            t.start()
            t.join()
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
            self.logger.error(str(exc_type))
            self.logger.error(str(exc_value))

    def manifest_response(self):
        try:
            t = ManifestProducer(dbconfig=self.dbconfig, 
                    servers=self.servers, request=self.request)

            t.start()
            t.join()
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
            self.logger.error(str(exc_type))
            self.logger.error(str(exc_value))

    def run(self):
        accept = self.request['accept']
        if accept.endswith("manifest"):
            self.manifest_response()
        elif accept.endswith("rosbag"):
            self.rosbag_response()
        else:
            self.logger.error("unexpected accept type {0}".format(accept))
            raise ValueError() 
