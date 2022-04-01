## Dynamic Provisioning
This example shows how to create a dynamically provisioned volume created through [EFS access points](https://docs.aws.amazon.com/efs/latest/ug/efs-access-points.html) and Persistent Volume Claim (PVC) and consume it from a pod.

**Note**: this example requires Kubernetes v1.17+ and driver version >= 1.2.0.

### Create an EFS File System 
But before we go ahead, make sure you have already setup your workspace as per [this tutorial](/application-integration/container/eks/) on your AWS Cloud9 instance and the Amazon EKS cluster is up and running. First we need to create an EFS file system, you can do so using CLI, SDK, or AWS Console. 
Just make sure you use the right VPN and Security Group while creating the mount targets 

![](/application-integration/container/eks/img/30.png)

Once you create the file system, wait for the FS state to turn `Available` and take a note of the **File system ID** as this we would need next when we create the `Storage Class` 

![](/application-integration/container/eks/img/31.png)


### Create the Storage Class 

Now we can create the `Storage Class` in our cluster, for that first edit this [storageclass.yaml](/application-integration/container/eks/dynamic_provisioning/sc.yaml) file 

```yaml
kind: StorageClass
apiVersion: storage.k8s.io/v1
metadata:
  name: efs-sc
provisioner: efs.csi.aws.com
parameters:
  provisioningMode: efs-ap
  fileSystemId: <place your file system ID>
  directoryPerms: "700"
  gidRangeStart: "1000"
  gidRangeEnd: "2000"
  basePath: "/dynamic_provisioning"
```

* `provisioningMode` - The type of volume to be provisioned by efs. Currently, only access point based provisioning is supported `efs-ap`.
* `fileSystemId` - The file system under which Access Point is created.
* `directoryPerms` - Directory Permissions of the root directory created by Access Point.
* `gidRangeStart (Optional)` - Starting range of Posix Group ID to be applied onto the root directory of the access point. Default value is 50000. 
* `gidRangeEnd (Optional)` - Ending range of Posix Group ID. Default value is 7000000.
* `basePath (Optional)` - Path on the file system under which access point root directory is created. If path is not provided, access points root directory are created under the root of the file system.

### Deploy the Example

Create storage class, persistent volume claim (PVC) and the pod which consumes PV:
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

![](/application-integration/container/eks/img/32.png)


