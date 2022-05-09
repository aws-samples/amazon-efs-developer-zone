## Dynamic Provisioning
This example shows how to create a dynamically provisioned volume created through [EFS access points](https://docs.aws.amazon.com/efs/latest/ug/efs-access-points.html) and Persistent Volume Claim (PVC) and consume it from a pod.

**Note**: this example requires Kubernetes v1.17+ and driver version >= 1.2.0.

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

1. Create an OIDC provider for the cluster

```bash
 $ export CLUSTER_NAME=efsworkshop-eksctl
 $ eksctl utils associate-iam-oidc-provider --cluster $CLUSTER_NAME --approve 
```

2. Now, we are going to make the setup for EFS, and we are going to use this script auto-efs-setup.py. The script automates all the Manual steps and is only for `Dynamic Provisioning` option. The script applies some default values for the file system name, performance mode etc. This script performs the following:

    * Install the EFS CSI Driver
    * Create the IAM Policy for the CSI Driver
    * Create an EFS Filesystem 
    * Creates a Storage Class  for the cluster 

   But before that, lets look at the exiting `Storage Class` 

```bash
$ kubectl get sc
NAME            PROVISIONER             RECLAIMPOLICY   VOLUMEBINDINGMODE      ALLOWVOLUMEEXPANSION   AGE
gp2 (default)   kubernetes.io/aws-ebs   Delete          WaitForFirstConsumer   false                  148m
```

3. Now, we can run the `auto-efs-setup.py`

```bash
$ cd /home/ec2-user/environment/amazon-efs-developer-zone/application-integration/container/eks/dynamic_provisioning

$ pip install -r requirements.txt
$ python auto-efs-setup.py --region $AWS_REGION --cluster $CLUSTER_NAME --efs_file_system_name myEFSDP
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

4. Now we can verify the `Storage Class` in the Kubernetes cluster 

```bash
$ kubectl get sc
NAME            PROVISIONER             RECLAIMPOLICY   VOLUMEBINDINGMODE      ALLOWVOLUMEEXPANSION   AGE
gp2 (default)   kubernetes.io/aws-ebs   Delete          WaitForFirstConsumer   false                  43m
my-efs-sc-1     efs.csi.aws.com         Delete          Immediate              false                  14s
```
5. We can see the EFS file system in the console as well 

![](/application-integration/container/eks/img/33.png)


### Storage Class 

If you would like to check the `Storage Class` defination in your cluster, you can check the [storageclass.yaml](/application-integration/container/eks/dynamic_provisioning/sc.yaml) file which the `auto-efs-setup.py` used in the previous step. 

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: my-efs-sc-1
provisioner: efs.csi.aws.com
parameters:
  directoryPerms: '700'
  fileSystemId: <your file system ID>
  provisioningMode: efs-ap

```

* `provisioningMode` - The type of volume to be provisioned by efs. Currently, only access point based provisioning is supported `efs-ap`.
* `fileSystemId` - The file system under which Access Point is created.
* `directoryPerms` - Directory Permissions of the root directory created by Access Point.
* `gidRangeStart (Optional)` - Starting range of Posix Group ID to be applied onto the root directory of the access point. Default value is 50000. 
* `gidRangeEnd (Optional)` - Ending range of Posix Group ID. Default value is 7000000.
* `basePath (Optional)` - Path on the file system under which access point root directory is created. If path is not provided, access points root directory are created under the root of the file system.

### Deploy the Example

Although the `auto-efs-setup.py` script has created the storage class, but if you would like to make any changes in the storage class definition as per your requirement, you can delete the automatically created storage class and create it again.  
```bash

$ kubectl delete -f sc.yaml

storageclass.storage.k8s.io "my-efs-sc-1" deleted

```
Next, you can edit this [storageclass.yaml](/application-integration/container/eks/dynamic_provisioning/sc.yaml) file and then create the storage class, persistent volume claim (PVC) and the pod which consumes PV:

```bash 
$ kubectl apply -f sc.yaml
storageclass.storage.k8s.io/my-efs-sc-1 created

$ kubectl apply -f pvc_pod.yaml
persistentvolumeclaim/efs-claim-1 created
pod/efs-app-1 created
```

### Check EFS filesystem is used
After the objects are created, verify that pod is running:

```bash
$ kubectl get pod 
NAME        READY   STATUS    RESTARTS   AGE
efs-app-1   1/1     Running   0          95s
```

Also you can verify that data is written onto EFS filesystem:

```sh
$ kubectl exec -ti efs-app-1 -- tail -f /data/out                           
Fri Apr 1 17:55:30 UTC 2022
Fri Apr 1 17:55:35 UTC 2022
```

And now we can see the access point as well which the EFS CSI driver created under the hood when we deployed this application 

![](/application-integration/container/eks/img/34.png)


