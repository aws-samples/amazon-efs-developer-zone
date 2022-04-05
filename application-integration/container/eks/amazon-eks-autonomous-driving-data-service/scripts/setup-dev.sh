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
 
scripts_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DIR=$scripts_dir/..

# check to see if kubectl is already configured
kubectl get svc || $scripts_dir/configure-eks-auth.sh

# set aws region
aws_region=$(aws configure get region)
[[ -z "${aws_region}" ]] && echo "aws_region env variable is required" && exit 1
[[ -z "${s3_bucket_name}" ]] && echo "s3_bucket_name env variable is required" && exit 1
[[ -z "${redshift_cluster_host}" ]] && echo "redshift_cluster_host variable required" && exit 1
[[ -z "${redshift_cluster_port}" ]] && echo "redshift_cluster_port variable required" && exit 1
[[ -z "${redshift_cluster_username}" ]] && echo "redshift_cluster_username variable required" && exit 1
[[ -z "${redshift_cluster_dbname}" ]] && echo "redshift_cluster_dbname variable required" && exit 1
[[ -z "${redshift_cluster_password}" ]] && echo "redshift_cluster_password variable required" && exit 1
[[ -z "${msk_cluster_arn}" ]] && echo "msk_cluster_arn variable required" && exit 1
[[ -z "${eks_pod_sa_role_arn}" ]] && echo "eks_pod_sa_role_arn variable required" && exit 1
[[ -z "${eks_node_role_arn}" ]] && echo "eks_node_role_arn variable required" && exit 1

MSK_SERVERS=$(aws kafka --region ${aws_region} get-bootstrap-brokers \
        	--cluster-arn ${msk_cluster_arn} | \
            grep \"BootstrapBrokerString\"  | \
            awk '{split($0, a, " "); print a[2]}')

# update helm charts values.ymal and example client config files
sed -i -e "s/\"servers\": .*/\"servers\": $MSK_SERVERS/g" \
    -e "s/\"host\": .*/\"host\": \"${redshift_cluster_host}\",/g" \
    -e "s/\"port\": .*/\"port\": \"${redshift_cluster_port}\",/g" \
    -e "s/\"user\": .*/\"user\": \"${redshift_cluster_username}\",/g" \
    -e "s/\"password\": .*/\"password\": \"${redshift_cluster_password}\",/g" \
    -e "s/\"rosbag_bucket\": .*/\"rosbag_bucket\": \"${s3_bucket_name}\",/g" \
    -e "s/\"cal_bucket\": .*/\"cal_bucket\": \"${s3_bucket_name}\",/g" \
    -e "s|roleArn:.*|roleArn: ${eks_pod_sa_role_arn}|g" \
    $DIR/a2d2/charts/a2d2-data-service/values.yaml

# update helm charts values.ymal and example client config files
sed -i -e "s/\"host\": .*/\"host\": \"${redshift_cluster_host}\",/g" \
    -e "s/\"port\": .*/\"port\": \"${redshift_cluster_port}\",/g" \
    -e "s/\"user\": .*/\"user\": \"${redshift_cluster_username}\",/g" \
    -e "s/\"password\": .*/\"password\": \"${redshift_cluster_password}\",/g" \
    -e "s/\"cal_bucket\": .*/\"cal_bucket\": \"${s3_bucket_name}\",/g" \
    -e "s|roleArn:.*|roleArn: ${eks_pod_sa_role_arn}|g" \
    $DIR/a2d2/charts/a2d2-rosbridge/values.yaml
    
sed -i -e "s/\"servers\": .*/\"servers\": $MSK_SERVERS/g" \
        $DIR/a2d2/config/c-config-ex1.json
                  
sed -i -e "s/\"servers\": .*/\"servers\": $MSK_SERVERS/g" \
        $DIR/a2d2/config/c-config-ex2.json

sed -i -e "s/\"servers\": .*/\"servers\": $MSK_SERVERS/g" \
        $DIR/a2d2/config/c-config-ex3.json

sed -i -e "s/\"servers\": .*/\"servers\": $MSK_SERVERS/g" \
        $DIR/a2d2/config/c-config-ex4.json

sed -i -e "s/\"servers\": .*/\"servers\": $MSK_SERVERS/g" \
        $DIR/a2d2/config/c-config-lidar.json
             
# Create kafka.config 
DATE=`date +%s`
cat >$DIR/a2d2/config/kafka.config <<EOL
{
    "config-name": "${cfn_stack_name}-${DATE}",
    "config-description": "${cfn_stack_name} Kafka configuration",
    "cluster-arn": "${msk_cluster_arn}",
    "cluster-properties": "$DIR/a2d2/config/kafka-cluster.properties"
}
EOL
chown ubuntu:ubuntu $DIR/a2d2/config/kafka.config

#Update MSK cluster config
echo "Update MSK cluster configuration"
python3 $scripts_dir/update-kafka-cluster-config.py --config $DIR/a2d2/config/kafka.config

# Update yaml files for creating EFS and FSx persistent-volume
sed -i -e "s/volumeHandle: .*/volumeHandle: ${efs_id}/g" \
    $DIR/a2d2/efs/pv-efs-a2d2.yaml

sed -i -e "s/volumeHandle: .*/volumeHandle: ${fsx_id}/g" \
    -e "s/dnsname: .*/dnsname: ${fsx_id}.fsx.${aws_region}.amazonaws.com/g" \
    -e "s/mountname: .*/mountname: ${fsx_mount_name}/g"  \
	$DIR/a2d2/fsx/pv-fsx-a2d2.yaml

# Update eks pod sa role in yaml files used for staging data
sed -i -e "s|eks\.amazonaws\.com/role-arn:.*|eks.amazonaws.com/role-arn: ${eks_pod_sa_role_arn}|g" \
    -e "s|value:[[:blank:]]\+$|value: ${s3_bucket_name}|g" $DIR/a2d2/fsx/stage-data-a2d2.yaml

sed -i -e "s|eks\.amazonaws\.com/role-arn:.*|eks.amazonaws.com/role-arn: ${eks_pod_sa_role_arn}|g" \
    -e "s|value:[[:blank:]]\+$|value: ${s3_bucket_name}|g" $DIR/a2d2/efs/stage-data-a2d2.yaml

# create a2d2 namespace
kubectl create namespace a2d2

# deploy AWS EFS CSI driver
echo "Deploy AWS EFS CSI Driver"
$scripts_dir/deploy-efs-csi-driver.sh
kubectl apply -f $DIR/a2d2/efs/efs-sc.yaml

# deploy AWS FSx CSI driver
echo "Deploy AWS FSx CSI Driver"
$scripts_dir/deploy-fsx-csi-driver.sh

# create EFS persistent volume
echo "Create k8s persistent-volume and persistent-volume-claim for efs"
kubectl apply -n a2d2 -f $DIR/a2d2/efs/pv-efs-a2d2.yaml
kubectl apply -n a2d2 -f $DIR/a2d2/efs/pvc-efs-a2d2.yaml

# create FSx persistent volume
echo "Create k8s persistent-volume and persistent-volume-claim for fsx"
kubectl apply -n a2d2 -f $DIR/a2d2/fsx/pv-fsx-a2d2.yaml
kubectl apply -n a2d2 -f $DIR/a2d2/fsx/pvc-fsx-a2d2.yaml
kubectl get pv -n a2d2

# deploy metrics server
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# deploy eks cluster autoscaler
$scripts_dir/eks-cluster-autoscaler.sh

# Build ECR image
$scripts_dir/build-ecr-image.sh

# Build catkin_ws
cd $DIR/a2d2/catkin_ws && catkin_make
echo "source /home/ubuntu/amazon-eks-autonomous-driving-data-service/a2d2/catkin_ws/devel/setup.bash" >> /home/ubuntu/.bashrc