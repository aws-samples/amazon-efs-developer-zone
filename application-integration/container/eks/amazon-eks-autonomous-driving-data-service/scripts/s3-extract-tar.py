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

import os
import tarfile
import time
import json
import math
import sys

import boto3
from boto3.s3.transfer import TransferConfig
from multiprocessing import Process
from threading import Thread
import logging

logging.basicConfig(format='%(asctime)s:%(name)s:%(levelname)s:%(process)d:%(message)s', level=logging.INFO)

class DownloadProgress(Thread):
    def __init__(self, size):
        Thread.__init__(self)
        self._size = size
        self._seen_so_far = 0
        self._start = time.time()
        self._prev = 0.0
        self._perc = 0.0

    def run(self):
        last_seen = self._seen_so_far
        while self._perc < 100:
            time.sleep(120)
            if self._seen_so_far == last_seen:
                sys.exit("Abort download because it is not progressing for 120 seconds")
            else:
                last_seen = self._seen_so_far
            
    def __call__(self, bytes_amount):
        self._seen_so_far += bytes_amount
        self._perc = round((self._seen_so_far / self._size) * 100, 2)
        if ((self._perc > 95.0) or (self._perc - self._prev) > 5):
            self._prev = self._perc
            elapsed = time.time() - self._start
            S3TarExtractor.logger.info(f'percentage completed... {self._perc} in {elapsed} secs')

class S3TarExtractor(Process):
    # class variables
    logger = logging.getLogger("s3-extract-tar")
    P_CONCURRENT = 4
    FILE_CHUNK_COUNT = 20000
    GB = 1024**3
    S3_MAX_IO_QUEUE = 1000
    S3_IO_CHUNKSIZE = 262144
    PUT_RETRY = 5

    def __init__(self,
                config=None,
                index=None,
                count=None):

        Process.__init__(self)

        self.config = config
        self.__pindex = index
        self.__pcount = count

    def run(self):
        file_path = self.config['file_path']
        ext = os.path.splitext(file_path)[1]
        mode = "r:gz" if ext == ".gz" else "r:bz2" if ext == ".bz2" else "r:xz" if ext == ".xz" else "r"
        tar_file = tarfile.open(name=file_path, mode=mode)
        start = self.config['start']
        end = self.config['end']

        info_list = tar_file.getmembers()
        file_info_list = [ info for info in info_list if info.isfile()]
        file_info_list = file_info_list[start:end] if  end > start else file_info_list
        file_count = len(file_info_list)

        p_chunk = math.ceil(file_count/self.__pcount)
        p_start = self.__pindex * p_chunk
        p_end = min(p_start + p_chunk, file_count)

        file_info_list = file_info_list[p_start:p_end]
        file_count = len(file_info_list)

        start_time = time.time()
        files_extracted=0

        dest_bucket = self.config["dest_bucket"]
        dest_prefix = self.config["dest_prefix"]

        s3_client = boto3.client('s3') 
        self.logger.info(f"worker {self.__pindex}, start: {start+p_start}, end: {start+p_end}, count: {file_count}")
        for file_info in file_info_list:
            nattempt = 0
            while nattempt < self.PUT_RETRY:
                try:
                    file_reader = tar_file.extractfile(file_info)
                    file_key = self.__dest_key(dest_prefix, file_info.name)
                    
                    s3_client.put_object(Body=file_reader, 
                                Bucket=dest_bucket, 
                                Key = file_key)
                    file_reader.close()
                    files_extracted += 1
                    break
                except Exception as err:
                    self.logger.info(f"Exception: {err}")
                    nattempt += 1
                    time.sleep(nattempt)
            if nattempt >= self.PUT_RETRY:
                self.logger.info(f'worker {self.__pindex}, failed: {file_path}')
                sys.exit(1)

            if files_extracted % 100 == 0:
                elapsed = time.time() - start_time
                self.logger.info(f"worker {self.__pindex}: files extracted: {files_extracted}: {elapsed}s")

        elapsed = time.time() - start_time
        self.logger.info(f"worker {self.__pindex}: files extracted: {files_extracted}: {elapsed}s")

    @classmethod
    def __submit_batch_jobs(cls, config=None, total_file_count=None):

        batch_client = boto3.client('batch')
    
        # batch jobs
        jobs=[]
    
        s3_python_script = config['s3_python_script']
        s3_json_config = config['s3_json_config']
        file_path = config['file_path']
        aws_region = os.environ['AWS_DEFAULT_REGION']

        job_ts = str(time.time()).replace('.','-')
        for i in range(0, total_file_count, cls.FILE_CHUNK_COUNT):
            start = i
            end = min(i + cls.FILE_CHUNK_COUNT, total_file_count)

            response = batch_client.submit_job(
                jobName=f'extract-{start}-{end}-{job_ts}',
                jobQueue=config['job_queue'],
                jobDefinition=config['job_definition'],
                retryStrategy={'attempts': 2},
                containerOverrides={
                    'command': ['--file-path', f'{file_path}', '--start', f'{start}', '--end', f'{end}'],
                    'environment': [
                        {
                            'name': 'S3_PYTHON_SCRIPT',
                            'value': s3_python_script
                        },
                        {
                            'name': 'S3_JSON_CONFIG',
                            'value': s3_json_config
                        },
                        {
                            'name': 'AWS_DEFAULT_REGION',
                            'value': aws_region
                        }
                    ]
                })
            jobs.append(response["jobId"])

        succeeded=[]
        failed = []
        pending=[ job_id for job_id in jobs ]

        while pending:
            response = batch_client.describe_jobs(jobs=pending)
            pending = []

            for _job in response["jobs"]:
                if _job["status"] == 'SUCCEEDED':
                    succeeded.append(_job["jobId"])
                elif _job["status"] == 'FAILED':
                    failed.append(_job["jobId"])
                else:
                    pending.append(_job["jobId"])

            time.sleep(5)
        
        if failed:
            import sys
            sys.exit(f"Failed: batch jobs: {failed}")

    
    @classmethod
    def __dest_key(cls, dest_prefix, member_name):
        dest_key = member_name

        if dest_key.startswith("./"):
            dest_key = dest_key[2:]
        elif dest_key.startswith("/"):
            dest_key = dest_key[1:]
                
        return f'{dest_prefix}/{dest_key}'

    
    @classmethod
    def __is_tar_extracted(cls, s3_client=None, key=None, mdir=None, dest_bucket=None):
        file_name = key if key.find('/') == -1 else key.rsplit('/', 1)[1]
        file_path = os.path.join(mdir, file_name)

        mkey = f"manifests/{key}"
        with open(file_path, 'wb') as data:
            start_time = time.time()
            cls.logger.info(f"Download mainfest, if exists: s3://{dest_bucket}/{mkey} ")
            config = TransferConfig()

            try:
                s3_client.download_fileobj(dest_bucket, mkey, data, Config=config)
            except Exception as e:
                cls.logger.info(f"No mainfest found: s3://{dest_bucket}/{mkey} ")
                return None
            finally:
                data.close()

            elapsed = time.time() - start_time
            file_size = os.stat(file_path).st_size
            cls.logger.info(f"Manifest downloaded: {file_path}: {file_size} bytes in {elapsed} secs")
            return cls.__verify_manifest(s3_client=s3_client, manifest_path=file_path, dest_bucket=dest_bucket)
        

    @classmethod
    def __verify_manifest(cls, s3_client=None, manifest_path=None, dest_bucket=None):
        verified = True

        with open(manifest_path, 'r') as manifest:
            try:
                for line in manifest:
                    entry = line.split(' ', 1)
                    key = entry[0]
                    expected_size = int(entry[1])
                    actual_size = s3_client.head_object(Bucket=dest_bucket, Key=key).get('ContentLength')
                    if(expected_size != actual_size):
                        cls.logger.info(f"Manifest mismatch: s3://{dest_bucket}/{key}, expected: {expected_size}, actual:{actual_size}")
                        verified = False
                        break
            except Exception as e:
                verified = False
                cls.logger.warning(f"Verify manifest error: {e}")

    
            manifest.close()

        return verified

    @classmethod
    def __download_file(cls, s3_client=None, bucket_name=None, key=None, dir=None, mdir=None, dest_bucket=None):
        file_name = key if key.find('/') == -1 else key.rsplit('/', 1)[1]
        file_path = os.path.join(dir, file_name)
            
        with open(file_path, 'wb') as data:
            start_time = time.time()
                
            tar_size = s3_client.head_object(Bucket=bucket_name, Key=key).get('ContentLength')
            cls.logger.info(f"Begin download: s3://{bucket_name}/{key} : {tar_size} bytes")
            config = TransferConfig(multipart_threshold=cls.GB, 
                    multipart_chunksize=cls.GB,
                    max_io_queue=cls.S3_MAX_IO_QUEUE, 
                    io_chunksize=cls.S3_IO_CHUNKSIZE)
            try:
                _download_callback = DownloadProgress(tar_size)
                _download_callback.start()
                s3_client.download_fileobj(bucket_name, key, data, Config=config, Callback=_download_callback)
                
            except Exception as e:
                cls.logger.error(f"File download error: {e} ")
                sys.exit(1)
            finally:
                data.close()
                
            elapsed = time.time() - start_time
            file_size = os.stat(file_path).st_size
            cls.logger.info(f"Download completed: {file_path}: {file_size} bytes in {elapsed} secs")

        return file_path


    @classmethod
    def extract_tar(cls, config=None):

        key = config['key']
        manifest_path = None
        s3_client = boto3.client('s3')

        if key:
            tmp_dir = config["tmp_dir"]
            os.makedirs(tmp_dir, mode=0o777, exist_ok=True)

            mdir = os.path.join(tmp_dir, "manifests")
            os.makedirs(mdir, mode=0o777, exist_ok=True)
    
            source_bucket = config["source_bucket"]
            dest_bucket = config["dest_bucket"]
        
            dest_prefix = config["dest_prefix"]
            manifest_name = key if key.find('/') == -1 else key.rsplit('/', 1)[1]
            manifest_path = os.path.join(mdir, manifest_name)

            if cls.__is_tar_extracted(s3_client=s3_client, key=key, mdir=mdir, dest_bucket=dest_bucket):
                cls.logger.info(f"Tar is already extracted: {key}")
                sys.exit(0)

            _file_name = key if key.find('/') == -1 else key.rsplit('/', 1)[1]
            _file_path = os.path.join(tmp_dir, _file_name)

            if os.path.isfile(_file_path):
                file_size = os.stat(_file_path).st_size
                tar_size = s3_client.head_object(Bucket=source_bucket, Key=key).get('ContentLength')
                if file_size == tar_size:
                    cls.logger.info(f"Skipping download: s3://{source_bucket}/{key}, file exists: {_file_path}, size:{file_size}")
                else:
                    config['file_path'] = cls.__download_file(s3_client=s3_client, bucket_name=source_bucket, key=key, 
                        dir=tmp_dir, mdir=mdir, dest_bucket=dest_bucket)
            else:
                config['file_path'] = cls.__download_file(s3_client=s3_client, bucket_name=source_bucket, key=key, 
                    dir=tmp_dir, mdir=mdir, dest_bucket=dest_bucket)
        
        file_path = config['file_path']
        if not file_path:
            cls.logger.info("No file to be extracted")
            sys.exit(0)

        start_time = time.time()

        start = config['start']
        end = config['end']

        total_file_count = 0
        if not start and not end:
            ext = os.path.splitext(file_path)[1]
            mode = "r:gz" if ext == ".gz" else "r:bz2" if ext == ".bz2" else "r:xz" if ext == ".xz" else "r"
            tar_file = tarfile.open(name=file_path, mode=mode)
            info_list = tar_file.getmembers()
            file_info_list = [ info for info in info_list if  info.isfile()]
            total_file_count = len(file_info_list)

            with open(manifest_path, "w") as manifest:
                for file_info in file_info_list:
                    file_key = cls.__dest_key(dest_prefix, file_info.name)
                    file_size = file_info.size
                    manifest.write(f"{file_key} {file_size}\n")

                manifest.close()

        if total_file_count > cls.FILE_CHUNK_COUNT:
            cls.logger.info(f"submit batch jobs for {file_path} : {total_file_count}")
            cls.__submit_batch_jobs(config, total_file_count)
        else:
            _p_list = []
            for i in range(cls.P_CONCURRENT):
                p = S3TarExtractor(config=config, index=i, count=cls.P_CONCURRENT)
                _p_list.append(p)
                p.start()

            for _p in _p_list:
                _p.join()
    
        elapsed = time.time() - start_time
    
        if not start and not end:
            verified = cls.__verify_manifest(s3_client=s3_client, manifest_path=manifest_path, dest_bucket=dest_bucket)
            if verified:
                manifest_key = f"manifests/{key}"
                s3_client = boto3.client('s3')
                s3_client.upload_file(manifest_path, dest_bucket, manifest_key)
                os.remove(manifest_path)
                os.remove(file_path)
                cls.logger.info(f"Extraction completed: {elapsed} secs") 
            else:
                cls.logger.info(f"Extraction verification error: {elapsed} secs")
                sys.exit(1)

import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Extract archive from S3 to EFS')
    parser.add_argument('--config', type=str,  help='Configuration JSON file', required=True)
    parser.add_argument('--key', type=str,  default='', help='S3 key for Tar file', required=False)
    parser.add_argument('--file-path', type=str,  default='', help='File path for downloaded file', required=False)
    parser.add_argument('--start', type=int,  default=0, help='Start file index in the archive', required=False)
    parser.add_argument('--end', type=int,  default=0, help='End file index in the archive', required=False)
   
    args = parser.parse_args()

    with open(args.config) as json_file:
        config = json.load(json_file)

    config['key'] = args.key
    config['file_path'] = args.file_path

    config['start'] = args.start
    config['end'] = args.end
    
    S3TarExtractor.extract_tar(config=config)
