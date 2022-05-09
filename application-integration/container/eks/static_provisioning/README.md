## Static Provisioning
This example shows how to make a static provisioned EFS persistent volume (PV) mounted inside container.

### Prerequisite 
But before we go ahead, make sure you have already setup your workspace as per [this tutorial](/application-integration/container/eks/) on your AWS Cloud9 instance and the Amazon EKS cluster is up and running. 

```bash

$ eksctl get cluster

2022-05-09 18:03:29 [ℹ]  eksctl version 0.96.0
2022-05-09 18:03:29 [ℹ]  using region us-east-2
NAME                    REGION          EKSCTL CREATED
efsworkshop-eksctl      us-east-2       True

$ kubectl get nodes

NAME                                           STATUS   ROLES    AGE   VERSION
ip-192-168-12-120.us-east-2.compute.internal   Ready    <none>   14m   v1.21.5-eks-9017834
ip-192-168-17-202.us-east-2.compute.internal   Ready    <none>   14m   v1.21.5-eks-9017834
ip-192-168-33-44.us-east-2.compute.internal    Ready    <none>   14m   v1.21.5-eks-9017834
ip-192-168-35-239.us-east-2.compute.internal   Ready    <none>   14m   v1.21.5-eks-9017834
ip-192-168-6-197.us-east-2.compute.internal    Ready    <none>   14m   v1.21.5-eks-9017834


```

Clone this [amazon-efs-developer-zone repo](https://github.com/aws-samples/amazon-efs-developer-zone.git). 

```bash

$ git clone https://github.com/aws-samples/amazon-efs-developer-zone.git

Cloning into 'amazon-efs-developer-zone'...
remote: Enumerating objects: 4309, done.
remote: Counting objects: 100% (4309/4309), done.
...
...
Resolving deltas: 100% (1725/1725), done.

```


### Amazon EFS as Persistent Storage

1. Now, we are going to make the setup for EFS, and we are going to use this script auto-efs-setup.py. The script automates all the Manual steps and use some default values for the file system name, performance mode etc. This script performs the following:

    * Create an OIDC provider for the cluster
    * Install the EFS CSI Driver
    * Create the IAM Policy for the CSI Driver
    * Create an EFS Filesystem 

   But before that, lets look at the exiting `Storage Class` 

```bash
$ kubectl get sc
NAME            PROVISIONER             RECLAIMPOLICY   VOLUMEBINDINGMODE      ALLOWVOLUMEEXPANSION   AGE
gp2 (default)   kubernetes.io/aws-ebs   Delete          WaitForFirstConsumer   false                  148m
```

2. Now, we can run the `auto-efs-setup.py`

```bash
$ cd /home/ec2-user/environment/amazon-efs-developer-zone/application-integration/container/eks/static_provisioning

$ pip install -r requirements.txt

$ python auto-efs-setup.py --region $AWS_REGION --cluster $CLUSTER_NAME --efs_file_system_name myEFSSP
=================================================================
                          EFS Setup
=================================================================
                   Prerequisites Verification
=================================================================
Verifying OIDC provider...
OIDC provider found
Verifying eksctl is installed...
eksctl found!
...
...
Setting up dynamic provisioning...
Editing storage class with appropriate values...
Creating storage class...
storageclass.storage.k8s.io/efs-sc created
Storage class created!
Dynamic provisioning setup done!
=================================================================
                      EFS Setup Complete
=================================================================
```

Once you create the file system, wait for the FS state to turn `Available` and take a note of the **File system ID** as this we would need next when we create the `Persistent Volume` 

![](/application-integration/container/eks/img/35.png)

## Create Persistent Volume

Edit the `PV` [manifest file](/application-integration/container/eks/static_provisioning/pv.yaml)

```yaml
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: my-efs-pv
spec:
  capacity:
    storage: 5Gi
  volumeMode: Filesystem
  accessModes:
    - ReadWriteOnce
  storageClassName: ""
  persistentVolumeReclaimPolicy: Retain
  csi:
    driver: efs.csi.aws.com
    volumeHandle: <Insert your File System ID>
```
Replace `VolumeHandle` value with `FileSystemId` of the EFS filesystem that needs to be mounted.

You can find it using AWS CLI:
```bash
$ aws efs describe-file-systems --query "FileSystems[*].FileSystemId"
```

### Deploy the Example Application

Create PV and persistent volume claim (PVC):
```sh
$ kubectl apply -f pv.yaml
$ kubectl apply -f pvc.yaml
$ kubectl apply -f pod.yaml

$ kubectl get pvc
NAME        STATUS   VOLUME      CAPACITY   ACCESS MODES   STORAGECLASS   AGE
efs-claim   Bound    my-efs-pv   5Gi        RWO  

$ kubectl get pod
NAME      READY   STATUS    RESTARTS   AGE
efs-app   1/1     Running   0          31s

```

### Check EFS filesystem is used

After the objects are created, verify that pod is running:

```bash
$ kubectl get pods
```

Also you can verify that data is written onto EFS filesystem:

```bash
$ kubectl exec -ti efs-app -- tail -f /data/out.txt
```

