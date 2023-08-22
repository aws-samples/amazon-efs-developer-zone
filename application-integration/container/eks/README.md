# Step by Step Guide for EFS and EKS configuration 

In this section we will setup our working environment for few of the demos around Amazon EFS and Amazon EKS. Once you are done with setting up the working environment, you may like to go ahead and pick the labs of your choice 

| Tutorial | Link
| --- | ---
| **Static Provisioning using Amazon EFS for Amazon EKS** | [![](/img/efs-tutorial-button.png)](/application-integration/container/eks/static_provisioning) |
| **Dynamic Provisioning using Amazon EFS for Amazon EKS** | [![](/img/efs-tutorial-button.png)](/application-integration/container/eks/dynamic_provisioning) |
| **Machine Learning at scale using Kubeflow on Amazon EKS with Amazon EFS** | [![](/img/efs-tutorial-button.png)](/application-integration/container/eks/kubeflow) |
| **Building a cloud file manager using Amazon ECS(Fargate) and Amazon EFS** | [![](/img/efs-tutorial-button.png)](/application-integration/container/ecs/ecs-efs-demo/) |
| **Bitcoin Blockchain with Amazon ECS and Amazon EFS** | [![](/img/efs-tutorial-button.png)](/application-integration/container/ecs/ecs-efs-bitcoin) |
| **Persistence Configuration with Amazon EFS on Amazon EKS using AWS Fargate** | [![](/img/efs-tutorial-button.png)](/application-integration/container/eks/eks-efs-share-within-fargate-master) |




## Setup the working Environment 

1. Launch Cloud9 in your closest region

![](/application-integration/container/eks/img/1.png)

- Select Create environment
- Name it efsworkshop, click Next.
- Choose `t3.small` or `m5.large` or any of the instance type of your choice which you would prefer for your development workspace, take all default values and click Create environment

2. Opening a new terminal tab in the main work area

![](/application-integration/container/eks/img/2.png)

3. Increase the disk size on the Cloud9 instance

```
Note: The following command adds more disk space to the root volume of the EC2 instance that Cloud9 runs on. Once the command completes, we reboot the instance and it could take a minute or two for the IDE to come back online. 
```

```python

$ pip3 install --user --upgrade boto3
$ export INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
$ export REGION=$(curl -s http://169.254.169.254/latest/dynamic/instance-identity/document | jq -r .region)
$ python -c "import boto3
import os
from botocore.exceptions import ClientError 
ec2 = boto3.client('ec2', region_name = os.getenv('REGION'))
volume_info = ec2.describe_volumes(
    Filters=[
        {
            'Name': 'attachment.instance-id',
            'Values': [
                os.getenv('INSTANCE_ID')
            ]
        }
    ]
)
volume_id = volume_info['Volumes'][0]['VolumeId']
try:
    resize = ec2.modify_volume(    
            VolumeId=volume_id,    
            Size=30
    )
    print(resize)
except ClientError as e:
    if e.response['Error']['Code'] == 'InvalidParameterValue':
        print('ERROR MESSAGE: {}'.format(e))"
if [ $? -eq 0 ]; then
    sudo reboot
fi


```

4. You can now see the `disk size` has been increased to 30GiB now.

![](/application-integration/container/eks/img/3.png)

## Installing Kubernetes Tools 

1. Install `kubectl`

```bash
$ sudo curl --silent --location -o /usr/local/bin/kubectl \
   https://amazon-eks.s3.us-west-2.amazonaws.com/1.21.2/2021-07-05/bin/linux/amd64/kubectl

$ sudo chmod +x /usr/local/bin/kubectl

```

2. Update `awscli` 

```bash
$ curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
$ unzip awscliv2.zip
$ sudo ./aws/install
$ sudo mv /usr/local/bin/aws /usr/bin/aws

```

3. Install `jq`, `envsubst` (from GNU gettext utilities) and `bash-completion`

```bash
$ sudo yum -y install jq gettext bash-completion moreutils
```

4. Install `yq` for yaml processing

```bash
$ echo 'yq() {
  docker run --rm -i -v "${PWD}":/workdir mikefarah/yq "$@"
}' | tee -a ~/.bashrc && source ~/.bashrc

```

5. Verify the binaries are in the `path` and executable

```bash
$ for command in kubectl jq envsubst aws
  do
    which $command &>/dev/null && echo "$command in path" || echo "$command NOT FOUND"
  done
```

6. Enable `kubectl bash_completion`

```bash 
$ kubectl completion bash >>  ~/.bash_completion
$ . /etc/profile.d/bash_completion.sh
$ . ~/.bash_completion
```

7.	Set the `AWS Load Balancer Controller` version

```bash
$ echo 'export LBC_VERSION="v2.3.0"' >>  ~/.bash_profile
.  ~/.bash_profile
```

## Create an IAM Role for your workspace

1. Follow [this link](https://us-east-1.console.aws.amazon.com/iam/home?region=us-east-1&skipRegion=true#/roles$new?step=review&commonUseCase=EC2%2BEC2&selectedUseCase=EC2&policies=arn:aws:iam::aws:policy%2FAdministratorAccess&roleName=efsworkshop-admin) to create an **IAM role** with Administrator access.

![](/application-integration/container/eks/img/4.png)

2. Confirm that **AWS service** is selected under `Trusted entity type` and EC2 are selected under `Use case`, then **click Next**.

![](/application-integration/container/eks/img/5.png)

3. Search for `AdministratorAccess` check the same checked, then click **Next**.

![](/application-integration/container/eks/img/6.png)

4. Enter `efsworkshop-admin` for the **Name**, and click **Create role**.

![](/application-integration/container/eks/img/7.png)

## Attach the IAM Role and update the IAM settings for your workspace

1. Click the grey `circle button` (in top right corner) and select **Manage EC2 Instance**.

![](/application-integration/container/eks/img/8.png)


2. Select the instance, then choose **Actions / Security / Modify IAM Role**

![](/application-integration/container/eks/img/9.png)

3. Choose `efsworkshop-admin` from the **IAM Role** drop down, and select **Save**

![](/application-integration/container/eks/img/10.png)

4. Next, we need to update the `IAM settings` in the **workspace**. 

    Cloud9 normally manages IAM credentials dynamically. This isn’t currently compatible with the EKS IAM authentication, so we will disable it and rely on the IAM role instead.

    To ensure temporary credentials aren’t already in place we will remove any existing credentials file as well as disabling AWS managed temporary credentials

```bash
$ aws cloud9 update-environment  --environment-id $C9_PID --managed-credentials-action DISABLE
$ rm -vf ${HOME}/.aws/credentials
```

5. Now, we should configure our `awscli` with our current region as default.

```bash
$ export ACCOUNT_ID=$(aws sts get-caller-identity --output text --query Account)
$ export AWS_REGION=$(curl -s 169.254.169.254/latest/dynamic/instance-identity/document | jq -r '.region')
$ export AZS=($(aws ec2 describe-availability-zones --query 'AvailabilityZones[].ZoneName' --output text --region $AWS_REGION))
```
6. Check if **AWS_REGION** is set to desired region

```bash
$ test -n "$AWS_REGION" && echo AWS_REGION is "$AWS_REGION" || echo AWS_REGION is not set
```

7. Let’s save these into `bash_profile`

```bash 
$ echo "export ACCOUNT_ID=${ACCOUNT_ID}" | tee -a ~/.bash_profile
$ echo "export AWS_REGION=${AWS_REGION}" | tee -a ~/.bash_profile
$ echo "export AZS=${AZS[@]}" | tee -a ~/.bash_profile
$ aws configure set default.region ${AWS_REGION}
$ aws configure get default.region
```

8. Lastly lets validate the **IAM role**

```bash
$ aws sts get-caller-identity --query Arn \
    | grep efsworkshop-admin -q  && echo "IAM role valid" || echo "IAM role NOT valid"
```

If the **IAM role** is not valid, **DO NOT PROCEED**. Go back and confirm the steps on this page.

![](/application-integration/container/eks/img/11.png)

## Create an AWS KMS Custom Managed Key (CMK) 

1. Create a `CMK` for the EKS cluster to use when encrypting your Kubernetes secrets

```bash
$ aws kms create-alias --alias-name alias/efsworkshop --target-key-id $(aws kms create-key --query KeyMetadata.Arn --output text)
```

2.	Let’s retrieve the `ARN of the CMK` to input into the create cluster command and set the `MASTER_ARN` environment variable to make it easier to refer to the KMS key later.

```bash
$ export MASTER_ARN=$(aws kms describe-key --key-id alias/efsworkshop --query KeyMetadata.Arn --output text)
$ echo "export MASTER_ARN=${MASTER_ARN}" | tee -a ~/.bash_profile
```

## Creating the EKS Cluster using eksctl 

In this section, we will use [eksctl](https://eksctl.io/) which is a tool jointly developed by **AWS and Weaveworks** that automates much of the experience of creating an **Amazon EKS clusters**.

1. Download the `eksctl` binary

```bash
$ curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp

$ sudo mv -v /tmp/eksctl /usr/local/bin
```

2. Check the `eksctl` version 
```bash
$ eksctl version
```

3. Enable `eksctl bash-completion`
```bash
$ eksctl completion bash >> ~/.bash_completion
$ . /etc/profile.d/bash_completion.sh
$ . ~/.bash_completion
```

4. Create an EKS Cluster 

```bash
$ cat << EOF > efsworkshop.yaml
---
apiVersion: eksctl.io/v1alpha5
kind: ClusterConfig

metadata:
  name: efsworkshop-eksctl
  region: ${AWS_REGION}
  version: "1.21"

availabilityZones: ["${AZS[0]}", "${AZS[1]}"]

managedNodeGroups:
- name: nodegroup
  minSize: 1
  desiredCapacity: 5
  maxSize: 10
  instanceType: m5.xlarge
  ssh:
    enableSsm: true

# To enable all of the control plane logs, uncomment below:
# cloudWatch:
#  clusterLogging:
#    enableTypes: ["*"]

secretsEncryption:
  keyARN: ${MASTER_ARN}
EOF
```

5. Now, we can use this file as the input for the `eksctl` to create the cluster. Launching EKS and all the dependencies will take approximately 15-20 minutes. 

```bash
$ eksctl create cluster -f efsworkshop.yaml
```

6. Let’s now test our EKS cluster 
```bash
$ kubectl get nodes
```
![](/application-integration/container/eks/img/12.png)

7. Lastly, lets export the worker `role name` for the rest of the workshop/demo

```bash
$ STACK_NAME=$(eksctl get nodegroup --cluster efsworkshop-eksctl -o json | jq -r '.[].StackName')

$ ROLE_NAME=$(aws cloudformation describe-stack-resources --stack-name $STACK_NAME | jq -r '.StackResources[] | select(.ResourceType=="AWS::IAM::Role") | .PhysicalResourceId')

$ echo "export ROLE_NAME=${ROLE_NAME}" | tee -a ~/.bash_profile
```
8. Now that the cluster is up and running, we just need to make sure we can see the nodes in the AWS Console as well. This step is optional. But, if you’d like full access to your workshop cluster in the EKS console this step is recommended.

    The EKS console allows you to see not only the configuration aspects of your cluster, but also to view Kubernetes cluster objects such as Deployments, Pods, and Nodes. For this type of access, the console IAM User or Role needs to be granted permission within the cluster.

    By default, the credentials used to create the cluster are automatically granted these permissions. Following along in the workshop, you’ve created a cluster using temporary IAM credentials from within Cloud9. This means that you’ll need to add your AWS Console credentials to the cluster.

![](/application-integration/container/eks/img/13.png)

9. Let’s Import the EKS Console credentials to the newly created cluster

```bash 
$ c9builder=$(aws cloud9 describe-environment-memberships --environment-id=$C9_PID | jq -r '.memberships[].userArn')
if echo ${c9builder} | grep -q user; then
    rolearn=${c9builder}
        echo Role ARN: ${rolearn}
elif echo ${c9builder} | grep -q assumed-role; then
        assumedrolename=$(echo ${c9builder} | awk -F/ '{print $(NF-1)}')
        rolearn=$(aws iam get-role --role-name ${assumedrolename} --query Role.Arn --output text) 
        echo Role ARN: ${rolearn}
fi
```

10.	With your `ARN` in hand, you can issue the command to create the identity mapping within the cluster.
```bash
$ eksctl create iamidentitymapping --cluster efsworkshop-eksctl --arn ${rolearn} --group system:masters --username admin
```
11.	Note that permissions can be restricted and granular but as this is a demo cluster, you’re adding the console credentials as administrator.

```bash
$ kubectl describe configmap -n kube-system aws-auth
```

12.	So, now if you look at the **AWS colsole**, you will be able to see all the nodes in your `EKS Cluster` 

![](/application-integration/container/eks/img/14.png)

At this point we are all set for next set of hands on activity:

| Tutorial | Link
| --- | ---
| **Static Provisioning using Amazon EFS for Amazon EKS** | [![](/img/efs-tutorial-button.png)](/application-integration/container/eks/static_provisioning) |
| **Dynamic Provisioning using Amazon EFS for Amazon EKS** | [![](/img/efs-tutorial-button.png)](/application-integration/container/eks/dynamic_provisioning) |
| **Machine Learning at scale using Kubeflow on Amazon EKS with Amazon EFS** | [![](/img/efs-tutorial-button.png)](/application-integration/container/eks/kubeflow) |


