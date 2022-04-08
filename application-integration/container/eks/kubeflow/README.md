# Machine Learning with Kubeflow on Amazon EKS with Amazon EFS 

Training any Deep Learning model on a large dataset often takes a lot of time, specially when the size of the data set for training is in the range of 100s of GBs. And running such machine learning model at scale on cloud demands a sophisticated mechanism. 

In this section, we will walk you through, how you can make use of [Kubeflow](https://www.kubeflow.org/), which is an open source toolkit that simplifies deploying machine learning workflows on Kubernetes on Amazon EKS and shall use Amazon EFS as a persistent storage in the backend, which will be used to staging the data for training, notebook and hosting the machine learning model. 

![](/application-integration/container/eks/img/15.png)

## Setting up the workspace

But before we go ahead, make sure you have already setup your workspace as per [this tutorial](/application-integration/container/eks/) on your AWS Cloud9 instance and the Amazon EKS cluster is up and running. 

Once that is all done, make sure we have everything installed and configured properly. 

```bash 
$ kubectl version

$ aws --version

$ jq --version

$ yq --version

```

Check the cluster nodes 

```bash 
$ kubectl get nodes
NAME                                           STATUS   ROLES    AGE     VERSION
ip-192-168-12-227.us-west-1.compute.internal   Ready    <none>   8m43s   v1.21.5-eks-9017834
ip-192-168-47-200.us-west-1.compute.internal   Ready    <none>   8m44s   v1.21.5-eks-9017834
ip-192-168-48-157.us-west-1.compute.internal   Ready    <none>   8m44s   v1.21.5-eks-9017834
ip-192-168-53-139.us-west-1.compute.internal   Ready    <none>   8m46s   v1.21.5-eks-9017834
ip-192-168-8-172.us-west-1.compute.internal    Ready    <none>   8m44s   v1.21.5-eks-9017834
```

## Installing Kubeflow 

Next, we need to install kubeflow in our cluster, and we are going to use [kustomize](https://github.com/kubernetes-sigs/kustomize/releases/tag/v3.2.0), its a command line tool to customize Kubernetes objects through a kustomization file. Let's first install it and verify. 

```bash
$ wget -O kustomize https://github.com/kubernetes-sigs/kustomize/releases/download/v3.2.0/kustomize_3.2.0_linux_amd64

$ chmod +x kustomize     

$ sudo mv -v kustomize /usr/local/bin

$ kustomize version
Version: {KustomizeVersion:3.2.0 GitCommit:a3103f1e62ddb5b696daa3fd359bb6f2e8333b49 BuildDate:2019-09-18T16:26:36Z GoOs:linux GoArch:amd64}
```

Lets clone this [amazon-efs-developer-zone repo](https://github.com/aws-samples/amazon-efs-developer-zone.git) and install `kubeflow` now using kustomize
This installation might take couple of minutes, as it will deploy many different Pods in your EKS cluster. 


```bash
$ git clone https://github.com/aws-samples/amazon-efs-developer-zone.git

Cloning into 'amazon-efs-developer-zone'...
remote: Enumerating objects: 4309, done.
remote: Counting objects: 100% (4309/4309), done.
...
...
Resolving deltas: 100% (1725/1725), done.

$ cd amazon-efs-developer-zone/application-integration/container/eks/kubeflow/manifests

$ while ! kustomize build example | kubectl apply -f -; do echo "Retrying to apply resources"; sleep 10; done

```

After installation, it will take some time for all `Pods` to become ready. Make sure all `Pods` are ready before trying to connect, otherwise you might get unexpected errors. To check that all Kubeflow-related `Pods` are **ready**, use the following commands(just make sure the STATUS for each Pod is in Running state before moving ahead):

```bash

$ kubectl get pods -n cert-manager
$ kubectl get pods -n istio-system
$ kubectl get pods -n auth
$ kubectl get pods -n knative-eventing
$ kubectl get pods -n knative-serving
$ kubectl get pods -n kubeflow
$ kubectl get pods -n kubeflow-user-example-com

```
So, now our Amazon EKS cluster is up and running with `kubeflow` installed, so the final setup would be to create an Amazon EFS file system and connect it with our EKS cluster so that `kubeflow` can make use of it

## Amazon EFS as Persistent Storage with Kubeflow

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
$ export CLUSTER_REGION=$AWS_REGION
$ export CLUSTER_NAME=efsworkshop-eksctl

$ cd distributions/aws/examples/storage/efs
$ pip install -r requirements.txt
$ python auto-efs-setup.py --region $CLUSTER_REGION --cluster $CLUSTER_NAME --efs_file_system_name myEFS1
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
efs-sc          efs.csi.aws.com         Delete          WaitForFirstConsumer   true                   96s
gp2 (default)   kubernetes.io/aws-ebs   Delete          WaitForFirstConsumer   false                  148m
```
5. We can see the EFS file system in the console as well 

![](/application-integration/container/eks/img/17.png)

6. If you see above, we have a shiny new `Storage Class` called `efs-sc` which kubeflow can use as a persistent storage. `gp2` is still the `Default` storage class, but we can always change the `Default` storage class from `gp2` to `efs-sc` 

```bash
$ kubectl patch storageclass gp2 -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"false"}}}'
storageclass.storage.k8s.io/gp2 patched

$ kubectl patch storageclass efs-sc -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
storageclass.storage.k8s.io/efs-sc patched

$ kubectl get sc
NAME               PROVISIONER             RECLAIMPOLICY   VOLUMEBINDINGMODE      ALLOWVOLUMEEXPANSION   AGE
efs-sc (default)   efs.csi.aws.com         Delete          WaitForFirstConsumer   true                   9m48s
gp2                kubernetes.io/aws-ebs   Delete          WaitForFirstConsumer   false                  86m      
```

By changing the default storage class, when we now create workspace volumes for your notebooks, it will use your EFS storage class automatically. 

## Creating a Jupyter Notebook on Kubeflow 

1. Run the following to `port-forward` Istio's Ingress-Gateway to local port `8080`

```bash
$ kubectl port-forward svc/istio-ingressgateway -n istio-system 8080:80
Forwarding from 127.0.0.1:8080 -> 8080
Forwarding from [::1]:8080 -> 8080
...
...
```

2. In your Cloud9 environment, click **Tools > Preview > Preview Running Application** to access dashboard. You can click on Pop out window button to maximize browser into new tab.

![](/application-integration/container/eks/img/18.png)

- Leave the current terminal running because if you kill the process, you will loose access to the dashboard. Open new Terminal to follow rest of the demo
- Login to the Kubeflow dashboard with the default user's credential. The default email address is `user@example.com` and the default password is `12341234`

![](/application-integration/container/eks/img/19.png)

- Now, let’s create a Jupyter Notebook. For that click on **Notebook → New Server**
- Mention the notebook name as “notebook1”, rest all keep it as default and scroll down and click on **LAUNCH**

![](/application-integration/container/eks/img/20.png)

At this point the EFS CSI driver should create an `Access Point`, as this new notebook on Kubeflow will internally create a `Pod`, which will create a `PVC`, and that will call the storage from the storage class `efs-sc` (as that’s the default storage we have selected for this EKS cluster). Let’s wait for the notebook to come to ready state. 

![](/application-integration/container/eks/img/21.png)

3. Now we can check the `PV` , `PVC` using **kubectl** which got created under the hood
```bash
$ kubectl get pv
NAME                                       CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS   CLAIM                                           STORAGECLASS   REASON   AGE
pvc-3d1806bc-984c-404d-9c2a-489408279bad   20Gi       RWO            Delete           Bound    kubeflow/minio-pvc                              gp2                     52m
pvc-8f638f2c-7493-461c-aee8-984760e233c2   10Gi       RWO            Delete           Bound    kubeflow-user-example-com/workspace-nootbook1   efs-sc                  5m16s
pvc-940c8ebf-5632-4024-a413-284d5d288592   10Gi       RWO            Delete           Bound    kubeflow/katib-mysql                            gp2                     52m
pvc-a8f5e29f-d29d-4d61-90a8-02beeb2c638c   20Gi       RWO            Delete           Bound    kubeflow/mysql-pv-claim                         gp2                     52m
pvc-af81feba-6fd6-43ad-90e4-270727e6113e   10Gi       RWO            Delete           Bound    istio-system/authservice-pvc                    gp2                     52m

$ kubectl get pvc -n kubeflow-user-example-com
NAME                  STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   AGE
workspace-nootbook1   Bound    pvc-8f638f2c-7493-461c-aee8-984760e233c2   10Gi       RWO            efs-sc         5m59s

```

4. And finally we can see the access point now in the **AWS console**

![](/application-integration/container/eks/img/22.png)

So, at this point you can make use of this Jupyter Notebook 

## Creating a PVC for sharing training dataset 

Now, we can create a PVC for your machine learning training dataset in `ReadWriteMany` mode meaning it can be used by many notebooks at the same time. You can go to the Kubeflow **Dashboard → Volumes →  New Volume** and create a new volume called dataset with efs-sc as the storage class

![](/application-integration/container/eks/img/23.png)

The volume would would be in `pending` state till it gets consumed by any of the `pod` and this is because when we create the `Storage Class` using the `auto-efs-setup.py` script, it used `volumeBindingMode` as `WaitForFirstConsumer`

```bash
$ kubectl get pvc -A
```
![](/application-integration/container/eks/img/24.png)

Lets now create another Jupyter notebook,  and call it as `notebook2` with a `Tensorflow image` as shown bellow and attached this newly created PVC as Data Volume 

![](/application-integration/container/eks/img/25.png)

![](/application-integration/container/eks/img/26.png)

Once this Notebook is ready, we can see the `PVC` is `bonded` with the `PV` and the respective EFS access point will also get created. 

```bash
$ kubectl get pvc -A
```
![](/application-integration/container/eks/img/27.png)

We can see 3 access points on the EFS file system, 1 for the dataset volume which we created and the other two are for the notebook home directory. And now we can open the notebook and use that shared storage volume dataset 

![](/application-integration/container/eks/img/28.png)


# Perform a Machine Learning Training 

1. Download the dataset from your notebook 


```python
import pathlib
import tensorflow as tf


dataset_url = "https://storage.googleapis.com/download.tensorflow.org/example_images/flower_photos.tgz"
!wget "https://storage.googleapis.com/download.tensorflow.org/example_images/flower_photos.tgz" 

!tar -xf flower_photos.tgz --directory /home/jovyan/dataset
!rm -rf flower_photos.tgz
```

![](/application-integration/container/eks/img/29.png)


2. Build and Push the Docker image

```bash

$ aws ecr create-repository \
>     --repository-name my-repo
{
    "repository": {
        "repositoryArn": "arn:aws:ecr:ap-southeast-1:123912348584:repository/my-repo",
        "registryId": "123912348584",
        "repositoryName": "my-repo",
        "repositoryUri": "123912348584.dkr.ecr.ap-southeast-1.amazonaws.com/my-repo",
        "createdAt": "2022-03-25T17:38:29+00:00",
        "imageTagMutability": "MUTABLE",
        "imageScanningConfiguration": {
            "scanOnPush": false
        },
        "encryptionConfiguration": {
            "encryptionType": "AES256"
        }
    }
}
```
3. Now, we can build the image locally in our Cloud9 instance and push it to our newly created ECR repository 

```bash
$ cd ..

$ pwd
/home/ec2-user/environment/kubeflow-manifests/distributions/aws/examples/storage

$ cd training-sample/

$ export IMAGE_URI=<repositoryUri:latest>

$ docker build .
Sending build context to Docker daemon  6.144kB
Step 1/3 : FROM public.ecr.aws/c9e4w0g3/notebook-servers/jupyter-tensorflow:2.6.0-cpu-py38
2.6.0-cpu-py38: Pulling from c9e4w0g3/notebook-servers/jupyter-tensorflow
7b1a6ab2e44d: Pulling fs layer 
31cd47bee782: Pulling fs layer  
...
...
Removing intermediate container 040429cfaecd
 ---> b3189c0564da
Successfully built b3189c0564da


$ docker build -t my-repo .

$ aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $IMAGE_URI

WARNING! Your password will be stored unencrypted in /home/ec2-user/.docker/config.json.
Configure a credential helper to remove this warning. See
https://docs.docker.com/engine/reference/commandline/login/#credentials-store

Login Succeeded

...
...

$ docker tag my-repo $IMAGE_URI

$ docker push $IMAGE_URI

$ cd -

$ pwd 
/home/ec2-user/environment/kubeflow-manifests/distributions/aws/examples/storage


```

4. Configure the `Tensorflow spec file`

Once the docker image is built and pushed to our ECR repo, we can now replace the the following in the tfjob.yaml file

* Docker Image URI (`IMAGE_URI`)
* Namespace (`PVC_NAMESPACE`)
* Claim Name (`CLAIM_NAME`)

```code
$ yq eval ".spec.tfReplicaSpecs.Worker.template.spec.containers[0].image = \"$IMAGE_URI\"" -i training-sample/tfjob.yaml

$ export CLAIM_NAME=dataset

$ yq eval ".spec.tfReplicaSpecs.Worker.template.spec.volumes[0].persistentVolumeClaim.claimName  = \"$CLAIM_NAME\"" -i training-sample/tfjob.yaml

$ export PVC_NAMESPACE=kubeflow-user-example-com

$ yq eval ".metadata.namespace = \"$PVC_NAMESPACE\"" -i training-sample/tfjob.yaml
```

5. Create the TFJob

Now, we are ready to train the model using the `training-sample/training.py` script and the data available on the shared volume with the Kubeflow TFJob operator as 

```bash
$ kubectl apply -f training-sample/tfjob.yaml
tfjob.kubeflow.org/image-classification-pvc created
```

In order to check that the training job is running as expected, you can check the events in the `TFJob` describe response as well as the job logs as:

```bash
$ kubectl describe tfjob image-classification-pvc -n $PVC_NAMESPACE
Name:         image-classification-pvc
Namespace:    kubeflow-user-example-com
Labels:       <none>
Annotations:  <none>
API Version:  kubeflow.org/v1
Kind:         TFJob
Metadata:
  Creation Timestamp:  2022-03-25T20:30:35Z
...
...
...
Events:
  Type    Reason                   Age                    From         Message
  ----    ------                   ----                   ----         -------
  Normal  SuccessfulCreatePod      7m2s                   tf-operator  Created pod: image-classification-pvc-worker-0
  Normal  SuccessfulCreatePod      7m2s                   tf-operator  Created pod: image-classification-pvc-worker-1
  Normal  SuccessfulCreateService  7m2s                   tf-operator  Created service: image-classification-pvc-worker-0
  Normal  SuccessfulCreateService  7m2s                   tf-operator  Created service: image-classification-pvc-worker-1
  Normal  ExitedWithCode           5m44s (x2 over 5m44s)  tf-operator  Pod: kubeflow-user-example-com.image-classification-pvc-worker-1 exited with code 0
  Normal  ExitedWithCode           5m44s                  tf-operator  Pod: kubeflow-user-example-com.image-classification-pvc-worker-0 exited with code 0
```

6. Lastly we can check the status of the training within the Pods itself

```bash

$ kubectl logs -n $PVC_NAMESPACE image-classification-pvc-worker-0 -f
Using deprecated annotation `kubectl.kubernetes.io/default-logs-container` in pod/image-classification-pvc-worker-0. Please use `kubectl.kubernetes.io/default-container` instead
2022-03-25 20:30:41.570601: W tensorflow/core/profiler/internal/smprofiler_timeline.cc:460] Initializing the SageMaker Profiler.
2022-03-25 20:30:41.570748: W tensorflow/core/profiler/internal/smprofiler_timeline.cc:105] SageMaker Profiler is not enabled. The timeline writer thread will not be started, future recorded events will be dropped.
2022-03-25 20:30:41.598012: W tensorflow/core/profiler/internal/smprofiler_timeline.cc:460] Initializing the SageMaker Profiler.
Found 3670 files belonging to 5 classes.
Using 2936 files for training.
2022-03-25 20:30:43.672514: I tensorflow/core/platform/cpu_feature_guard.cc:142] This TensorFlow binary is optimized with oneAPI Deep Neural Network Library (oneDNN) to use the following CPU instructions in performance-critical operations:  AVX512F
To enable them in other operations, rebuild TensorFlow with the appropriate compiler flags.
2022-03-25 20:30:43.682354: I tensorflow/core/common_runtime/process_util.cc:146] Creating new thread pool with default inter op setting: 2. Tune using inter_op_parallelism_threads for best performance.
Found 3670 files belonging to 5 classes.
Using 734 files for validation.
['daisy', 'dandelion', 'roses', 'sunflowers', 'tulips']
Model: "sequential"
_________________________________________________________________
Layer (type)                 Output Shape              Param #   
=================================================================
rescaling (Rescaling)        (None, 180, 180, 3)       0         
_________________________________________________________________
conv2d (Conv2D)              (None, 180, 180, 16)      448       
_________________________________________________________________
max_pooling2d (MaxPooling2D) (None, 90, 90, 16)        0         
_________________________________________________________________
conv2d_1 (Conv2D)            (None, 90, 90, 32)        4640      
_________________________________________________________________
max_pooling2d_1 (MaxPooling2 (None, 45, 45, 32)        0         
_________________________________________________________________
conv2d_2 (Conv2D)            (None, 45, 45, 64)        18496     
_________________________________________________________________
max_pooling2d_2 (MaxPooling2 (None, 22, 22, 64)        0         
_________________________________________________________________
flatten (Flatten)            (None, 30976)             0         
_________________________________________________________________
dense (Dense)                (None, 128)               3965056   
_________________________________________________________________
dense_1 (Dense)              (None, 5)                 645       
=================================================================
Total params: 3,989,285
Trainable params: 3,989,285
Non-trainable params: 0
_________________________________________________________________
Epoch 1/2
Extension horovod.torch has not been built: /usr/local/lib/python3.8/site-packages/horovod/torch/mpi_lib/_mpi_lib.cpython-38-x86_64-linux-gnu.so not found
If this is not expected, reinstall Horovod with HOROVOD_WITH_PYTORCH=1 to debug the build error.
Warning! MPI libs are missing, but python applications are still avaiable.
[2022-03-25 20:30:44.564 image-classification-pvc-worker-0:1 INFO utils.py:27] RULE_JOB_STOP_SIGNAL_FILENAME: None
[2022-03-25 20:30:44.749 image-classification-pvc-worker-0:1 INFO profiler_config_parser.py:111] Unable to find config at /opt/ml/input/config/profilerconfig.json. Profiler is disabled.
2022-03-25 20:30:45.282342: I tensorflow/compiler/mlir/mlir_graph_optimization_pass.cc:185] None of the MLIR Optimization Passes are enabled (registered 2)
92/92 [==============================] - 40s 338ms/step - loss: 1.3258 - accuracy: 0.4452 - val_loss: 1.1074 - val_accuracy: 0.5286
Epoch 2/2
92/92 [==============================] - 29s 314ms/step - loss: 1.0277 - accuracy: 0.5937 - val_loss: 1.0266 - val_accuracy: 0.6063
```

## Summary 

So, in this demo, we learnt how you can setup Kubeflow for your machine learning workflow on Amazon EKS and how we can leverage Amazon EFS as a shared filesystem to storing the training dataset. For more details you may like to explore these following links: 

* [Kubeflow official documentation](https://www.kubeflow.org/)
* [Amazon EFS Access Point](https://docs.aws.amazon.com/efs/latest/ug/efs-access-points.html) 
* [Amazon EKS](https://docs.aws.amazon.com/eks/latest/userguide/what-is-eks.html)
* [Amazon EFS CSI Driver](https://docs.aws.amazon.com/eks/latest/userguide/efs-csi.html)




