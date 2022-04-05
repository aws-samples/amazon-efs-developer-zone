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

# S3_PYTHON_SCRIPT must be a S3 URI for a Python3 script 
[[ -z "${S3_PYTHON_SCRIPT}" ]] && echo "S3_PYTHON_SCRIPT variable is required" && exit 1
aws s3 cp $S3_PYTHON_SCRIPT ${S3_PYTHON_SCRIPT##*/}  

CONFIG_ARGS=''
# S3_JSON_CONFIG is an optional S3 URI to a JSON config file
if [[ ! -z "${S3_JSON_CONFIG}" ]] 
then
	aws s3 cp $S3_JSON_CONFIG ${S3_JSON_CONFIG##*/}
	CONFIG_ARGS="--config ${S3_JSON_CONFIG##*/}"
fi

# S3_BASH_SCRIPT is an optional S3 URI to a setup bash script
if [[ ! -z "${S3_BASH_SCRIPT}" ]]
then
	aws s3 cp $S3_BASH_SCRIPT ${S3_BASH_SCRIPT##*/}
	source ${S3_BASH_SCRIPT##*/}
fi

# S3_REQUIREMENTS_TXT is an optional S3 URI to a 'requirements.txt' file
if [[ ! -z "${S3_REQUIREMENTS_TXT}" ]] 
then
	aws s3 cp $S3_REQUIREMENTS_TXT ${S3_REQUIREMENTS_TXT##*/}
	pip3 install -r ${S3_REQUIREMENTS_TXT##*/}
fi

ARGS="$@"
python3 ${S3_PYTHON_SCRIPT##*/} $CONFIG_ARGS $ARGS

