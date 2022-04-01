# Amazon EFS with Amazon EC2 instances

In this section we will see how we can make an Amazon EFS file system accessed from multiple Amazon EC2 instances 
You can create an EC2 instance before hand and keep the Security Group ID the instance associated with handy as we will need that information later on which creating mount target. 

## Create a file system 

We are going to use [`awscli`](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) to create this file system. So, make sure you have `awscli` installed in your workstation. 

We can create an Amazon EFS file system using `create-file-system` command

```
aws efs create-file-system \
    --performance-mode generalPurpose \
    --throughput-mode bursting \
    --encrypted \
    --tags Key=Name,Value=myfs1

```

This will return the file system ID (`FileSystemId`)

```
{
    "OwnerId": "507922848584",
    "CreationToken": "da7c634b-67c4-43e8-88b9-d65f1916be10",
    "FileSystemId": "fs-05fd384d477476c66",
    "FileSystemArn": "arn:aws:elasticfilesystem:us-east-1:507922848584:file-system/fs-05fd384d477476c66",
    "CreationTime": "2022-03-28T18:12:00+00:00",
    "LifeCycleState": "creating",
    "Name": "myfs1",
    "NumberOfMountTargets": 0,
    "SizeInBytes": {
        "Value": 0,
        "ValueInIA": 0,
        "ValueInStandard": 0
    },
    "PerformanceMode": "generalPurpose",
    "Encrypted": true,
    "KmsKeyId": "arn:aws:kms:us-east-1:507922848584:key/68503779-4395-457a-ac1c-e9f8922189bd",
    "ThroughputMode": "bursting",
    "Tags": [
        {
            "Key": "Name",
            "Value": "myfs1"
        }
    ]
}

```

Now, we can check the state of the file-system(`myfs1`) using `describe-file-systems` 

```
aws efs describe-file-systems \
    --file-system-id fs-05fd384d477476c66
```

We can now see the file system got created as the `LifeCycleState` changed from `creating` to `available` and at this point you can create one or more mount targets for the file system in our VPC. 

```
{
    "FileSystems": [
        {
            "OwnerId": "507922848584",
            "CreationToken": "da7c634b-67c4-43e8-88b9-d65f1916be10",
            "FileSystemId": "fs-05fd384d477476c66",
            "FileSystemArn": "arn:aws:elasticfilesystem:us-east-1:507922848584:file-system/fs-05fd384d477476c66",
            "CreationTime": "2022-03-28T18:12:00+00:00",
            "LifeCycleState": "available",
            "Name": "myfs1",
            "NumberOfMountTargets": 0,
            "SizeInBytes": {
                "Value": 6144,
                "ValueInIA": 0,
                "ValueInStandard": 6144
            },
            "PerformanceMode": "generalPurpose",
            "Encrypted": true,
            "KmsKeyId": "arn:aws:kms:us-east-1:507922848584:key/68503779-4395-457a-ac1c-e9f8922189bd",
            "ThroughputMode": "bursting",
            "Tags": [
                {
                    "Key": "Name",
                    "Value": "myfs1"
                }
            ]
        }
    ]
}
```

## Create mount targets 

Before we create `mount targets` we need to create a subnet wherein we can define which resources can access the File System. In our case since we want this file system to be used by an EC2 instance, we can mention the subnet details which is associated with our EC2 instances under the Inbound Rules for this new Security Group. In our case that security group is happen to be `sg-0a96bb662337cdf7d` or `myEC2-sg` as we can see bellow

![](/application-integration/ec2/img/1.png)

Now, we can create 3 mount targets in 3 different AZs in three different subnets and mentioned the newly created security group (`sg-0dca469f9305ecd95`)

```
# Mount Target 1 
aws efs create-mount-target \
    --file-system-id fs-05fd384d477476c66 \
    --subnet-id subnet-e39eb2cd\
    --security-groups sg-0dca469f9305ecd95
    
# Mount Target 2
aws efs create-mount-target \
    --file-system-id fs-05fd384d477476c66 \
    --subnet-id subnet-0499bb58\
    --security-groups sg-0dca469f9305ecd95

# Mount Target 3 
aws efs create-mount-target \
    --file-system-id fs-05fd384d477476c66 \
    --subnet-id subnet-483a4e76\
    --security-groups sg-0dca469f9305ecd95

```

## Mounting the File System 

Finally we can mount the file system on our EC2 instance. We can login to the EC2 instance and install [`amazon-efs-utils`](https://docs.aws.amazon.com/efs/latest/ug/using-amazon-efs-utils.html) if its not installed 

```
$ sudo yum install -y amazon-efs-utils

```

Then we can mount the file system as follows, all we need is the file system ID 

```
[ec2-user@ip-172-31-90-4 ~]$ mkdir efs
[ec2-user@ip-172-31-90-4 ~]$
[ec2-user@ip-172-31-90-4 ~]$ sudo mount -t efs -o tls fs-05fd384d477476c66:/ efs
[ec2-user@ip-172-31-90-4 ~]$
[ec2-user@ip-172-31-90-4 ~]$ df -h
Filesystem      Size  Used Avail Use% Mounted on
devtmpfs        3.8G     0  3.8G   0% /dev
tmpfs           3.8G     0  3.8G   0% /dev/shm
tmpfs           3.8G  556K  3.8G   1% /run
tmpfs           3.8G     0  3.8G   0% /sys/fs/cgroup
/dev/nvme0n1p1  8.0G  1.6G  6.5G  19% /
tmpfs           760M     0  760M   0% /run/user/1000
tmpfs           760M     0  760M   0% /run/user/0
127.0.0.1:/     8.0E     0  8.0E   0% /home/ec2-user/efs
[ec2-user@ip-172-31-90-4 ~]$
[ec2-user@ip-172-31-90-4 ~]$

```

## Writing data to the EFS file system 

Now, we can write data from this EC2 instance which is mounted at `/home/ec2-user/efs` directory and the same data can be access via some other compute resources(not only EC2 instances) at the same time. 

