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

import boto3
import json
import io
import os
import time
import pandas as pd
import numpy as np
import math
import csv

def s3_bucket_keys(s3_client, bucket, prefix, suffix=None):
    """Generator for listing S3 bucket keys matching prefix and suffix"""

    kwargs = {'Bucket': bucket, 'Prefix': prefix}
    while True:
        resp = s3_client.list_objects_v2(**kwargs)
        for obj in resp['Contents']:
            key = obj['Key']
            if not suffix or key.endswith(suffix):
                yield key

        try:
            kwargs['ContinuationToken'] = resp['NextContinuationToken']
        except KeyError:
            break

def ts_data(data, ts):
    ret = None

    try:
        ret = data[ts]
    except KeyError:
        pass

    return ret

def extract_bus_data(config):

    bucket = config["s3_bucket"]
    input_prefix = config["s3_input_prefix"]
    input_suffix = config["s3_input_suffix"]
    tmp_dir = config["tmp_dir"]
    vehicle_id = config["vehicle_id"]
    output_prefix = config["s3_output_prefix"]

    dir_name = f"bus_{time.time()}"
    dir_path = os.path.join(tmp_dir, dir_name)
    os.makedirs(dir_path, mode=0o777, exist_ok=True)

    s3_client = boto3.client(service_name='s3')
    for key in s3_bucket_keys(s3_client, bucket=bucket, prefix=input_prefix, suffix=input_suffix):
       
        bus_signals = s3_client.get_object(Bucket=bucket, Key=key)
        print(f"Reading: {key}")
        pd_df = pd.read_json(io.BytesIO(bus_signals['Body'].read()))
        scene_id = key.split('/')[-3:-2][0].replace('_', '')

        print(f"Processing bus, vehicle_id: {vehicle_id}, scene_id: {scene_id}")
        data = dict()
        nrows = 0
        index_name = dict()
        for col_index,col in enumerate(pd_df.columns): 
            index_name[col_index] = col
            values = pd_df[col]['values']
            
            for value in values:
               
                ts = value[0]
                row = ts_data(data, ts)

                if row == None:
                    row = [np.nan]*len(pd_df.columns)
                    data[ts] = row
                    nrows+=1
            
                row[col_index] = value[1]

        ts_keys = list(data.keys())
        ts_keys.sort()

        nrows = len(ts_keys)
        print(f"Bus data rows: {nrows}")

        row_vectors = []
        for ts_key in ts_keys:
            row = data[ts_key]
            row_vectors.append(np.array(row, dtype=np.float32).reshape(1, len(row)))
        
        bus_data = np.concatenate(row_vectors, axis=0)

        print(f"Imputing missing data")
        impute_missing(bus_data, pd_df.columns)

        # opening the csv file in 'w+' mode
        file_path = os.path.join(dir_path, f"bus-{scene_id}.csv")
        print(f"Writing bus data to {file_path}")

        csv_file = open(file_path, 'w+', newline ='')
  
        # writing the data into the file
        with csv_file:    
            csv_writer = csv.writer(csv_file)
            header = ['vehicle_id', 'scene_id', 'data_ts'] + list(pd_df.columns)
            csv_writer.writerow(header)

            for index in range(0, nrows, 1):
                col_values = bus_data[index,:].tolist()
                for coli, col in enumerate(pd_df.columns):
                    if is_categorical(col):
                        col_values[coli] = int(col_values[coli])
                    else:
                        col_values[coli] = round(col_values[coli], 6)

                data_row = [vehicle_id, scene_id, ts_keys[index]] + col_values
                csv_writer.writerow(data_row)

            csv_file.close()
    
        key = f"{output_prefix}/{file_path.rsplit('/', 1)[1]}"
        print(f"Uploading {file_path} to {key}")
        s3_client.upload_file(file_path, bucket, key)
        print(f"Uploaded {file_path} to {key}")

        print(f"Removing {file_path}")
        os.remove(file_path)
        print(f"Removed {file_path}")

def _find_next(data, rowi, coli, nrows):
    for nrowi in range(rowi+1, nrows, 1):
        _next = data[nrowi, coli]
        if not math.isnan(_next):
            return (_next, nrowi)

    return (np.nan, nrows)

def _impute(data, _prev, _next, prowi, nrowi, coli):
    diff = _next - _prev

    for rowi in range(prowi+1, nrowi, 1):
        if not math.isnan(diff):
            data[rowi, coli] = _prev + ((rowi - prowi)/(nrowi - prowi))*diff
        else:
            _propagate(data, _prev, _next, prowi, nrowi, coli)
        assert( not math.isnan(data[rowi, coli]))

def _propagate(data, _prev, _next, prowi, nrowi, coli):
    for rowi in range(prowi+1, nrowi, 1):
        if not math.isnan(_prev):
            data[rowi, coli] =  _prev
        elif not math.isnan(_next):
            data[rowi, coli] =  _next
        assert( not math.isnan(data[rowi, coli]))


def is_categorical(col):
    return col in ["accelerator_pedal_gradient_sign" , "steering_angle_calculated_sign",
        "latitude_direction", "longitude_direction"]

def impute_missing(data, columns, missing_value=np.nan):
    nrows = data.shape[0]
   
    for coli, col in enumerate(columns):
        _prev=np.nan
        prowi = -1
        categorical = is_categorical(col)

        for rowi in range(0,nrows,1):
            _cur = data[rowi, coli]
            if not math.isnan(_cur):
                _prev = _cur
                prowi = rowi
            else:
                (_next, nrowi) = _find_next(data, rowi, coli, nrows)
                if not categorical:
                    _impute(data, _prev, _next, prowi, nrowi, coli)
                else:
                    _propagate(data, _prev, _next, prowi, nrowi, coli)

        assert(not np.isnan(np.sum(data[:,coli])))

def main(config):
    # extract bus data
    extract_bus_data(config)
    
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Extract bus data')
    parser.add_argument('--config', type=str,  help='Extract bus data', required=True)
    
    args = parser.parse_args()

    with open(args.config) as json_file:
        config = json.load(json_file)

    main(config)

