## Static Provisioning
This example shows how to make a static provisioned EFS persistent volume (PV) mounted inside container.

### Create an EFS File System 
But before we go ahead, make sure you have already setup your workspace as per [this tutorial](/application-integration/container/eks/) on your AWS Cloud9 instance and the Amazon EKS cluster is up and running. First we need to create an EFS file system, you can do so using CLI, SDK, or AWS Console. 
Just make sure you use the right VPN and Security Group while creating the mount targets 

![](/application-integration/container/eks/img/30.png)

Once you create the file system, wait for the FS state to turn `Available` and take a note of the **File system ID** as this we would need next when we create the `Persistent Volume` 

![](/application-integration/container/eks/img/31.png)



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

## Deploy the Example Application

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

## Check EFS filesystem is used

After the objects are created, verify that pod is running:

```bash
$ kubectl get pods
```

Also you can verify that data is written onto EFS filesystem:

```bash
$ kubectl exec -ti efs-app -- tail -f /data/out.txt
```

