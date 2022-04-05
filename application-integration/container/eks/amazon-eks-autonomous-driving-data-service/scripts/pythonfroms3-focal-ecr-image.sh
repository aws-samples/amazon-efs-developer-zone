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

# This script builds 'pythonfroms3' image with 'focal' tag 

# set region
region=$(aws configure get region)
  
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

image=pythonfroms3
tag=focal

# Get the account number associated with the current IAM credentials
account=$(aws sts get-caller-identity --query Account --output text)

if [ $? -ne 0 ]
then
    exit 255
fi

fullname="${account}.dkr.ecr.${region}.amazonaws.com/${image}:${tag}"

# If the repository doesn't exist in ECR, create it.
aws ecr describe-repositories --region ${region} --repository-names "${image}" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    aws ecr create-repository --region ${region} --repository-name "${image}" > /dev/null
fi

# Build the docker image locally with the image name and then push it to ECR
# with the full name.
docker build  -t ${image} -f $DIR/Dockerfile-pythonfroms3-focal $DIR
docker tag ${image} ${fullname}

# Get the login command from ECR and execute it directly
aws ecr get-login-password --region ${region} \
                | docker login --username AWS --password-stdin ${account}.dkr.ecr.${region}.amazonaws.com
docker push ${fullname}
if [ $? -eq 0 ]; then
	export PYTHON_FROM_S3_IMAGE=$fullname
else
	echo "Error: Image build and push failed"
	exit 1
fi
