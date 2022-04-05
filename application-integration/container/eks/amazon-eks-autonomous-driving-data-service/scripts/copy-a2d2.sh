#!/bin/bash
#Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# 
#Permission is hereby granted, free of charge, to any person obtaining a copy of this
#software and associated documentation files (the "Software"), to deal in the Software
#without restriction, including without limitation the rights to use, copy, modify,
#merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
#permit persons to whom the Software is furnished to do so.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
#INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
#PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
#HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
#OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# WARNING: THIS FILE IS DEPRECATED AND IS NOT USED 

# set s3 bucket name
[[ -z "${s3_bucket_name}" ]] && echo "s3_bucket_name env variable is required" && exit 1
echo "S3 Bucket Name: $s3_bucket_name"

dst_bucket=$s3_bucket_name

date
a2d2_bucket=aev-autonomous-driving-dataset
dst_bucket_prefix=a2d2
files=$(aws s3 ls s3://$a2d2_bucket/ | awk '{ print $4 }')
for filename in $files
do
  echo "Downloading: $filename"
  aws s3 cp --quiet s3://$a2d2_bucket/$filename $filename 
  extension="${filename##*.}"  
  if [ "$extension" == "tar" ]
  then
	  rm -rf /tmp/$filename
	  mkdir /tmp/$filename
	  echo "Extracting:$filename"
	  tar -C /tmp/$filename -xf $filename
  	  aws s3 cp --quiet --recursive /tmp/$filename s3://$dst_bucket/$dst_bucket_prefix/
	  rm -rf /tmp/$filename
  else
	  aws s3 cp --quiet $filename s3://$dst_bucket/$dst_bucket_prefix/$filename
  fi
  rm $filename
done
date
