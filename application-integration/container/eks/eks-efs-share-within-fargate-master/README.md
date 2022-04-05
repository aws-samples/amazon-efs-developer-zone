# Persistence Configuration with Amazon EFS on Amazon EKS using AWS Fargate

This pattern provides the step-by-step guidance for enabling **Amazon Elastic File System (EFS)** as storage for containers running on **Amazon Elastic Kubernetes Service (EKS)**, using **AWS Fargate (Fargate)**.

## Summary

### Overview

This pattern brings step-by-step guidance, and supporting code examples, for enabling an **Amazon Elastic File System (EFS)** as a storage device for containers running on **Amazon Elastic Kubernetes Service (EKS)**, using **AWS Fargate (Fargate)**.

Regarding security aspects and following best practices, by default, it brings security at rest, security in transit. When encrypting your EFS file system, it uses an AWS managed **Customer Master Key (CMK)**, but it is also possible to specify a key alias that will dispatch the process of creating a CMK, used by **AWS Key Management Service (KMS)** to encrypt your **EFS** file system.

Throughout the steps you will create the needed namespace and **Fargate** profile for PoC application, install the **Amazon EFS CSI driver** needed for the integration between **Kubernetes** cluster and **EFS**, configure the needed *Storage Class*, and deploy the PoC application.

At the end of this pattern, you are going to see a shared **EFS** file system among different **Kubernetes** workloads, running over **Fargate**.

### Business Use Cases

There are different business use cases in which this pattern applies to. Basically, any scenario that needs data persistence between instances, without any data loss, in scaling in or scaling out actions.

Some examples are described in the following sections:

#### DevOps Tools

It is common to have enterprises using their own DevOps strategies and tools.

One of the common scenarios is to see **Jenkins** being used as a CI/CD tool. In such scenario, a shared file system can be used, for example, to:
*  Store configuration among different instances of the CI/CD tool
*  Store cache, for example **Maven** repository, for stages of a pipeline, among different instances of the CI/CD tool

#### Web Server

It is common to have enterprises running their own web servers to expose static content.

One of the common scenarios is to see **Apache** being used as an HTTP web server. In such scenario, a shared file system can be used to store static files that are shared among different instances of the web server.

It is important to mention that in this example scenario, there is a need for on-going live modifications directly applied to the file system, instead of having the static files baked into a docker image.

## Prerequisites, limitations, and product versions

### Prerequisites 
*  An active AWS account
*  An existing EKS cluster with Kubernetes version 1.17
*  Configured permissions for cluster administration
*  Context configured to the desired EKS cluster

### Limitations
*  **EFS** file system needs to be created manually first, then it could be mounted inside container as a *persistent volume (PV)* using the driver.
*  There are important considerations around the usage of **EKS** over **Fargate**, like not being able to use Daemonsets, not support the execution of privileged containers, and others. For more details, visit [**AWS Fargate** considerations](https://docs.aws.amazon.com/eks/latest/userguide/fargate.html).
*  The code provided in the repository runs properly on workstations with Linux, or macOS.

### Product versions
*  AWS CLI version 2+
*  AWS EFS CSI driver 1.0
*  eksctl version 0.24.0+
*  jq version 1.6+
*  kubectl version 1.17+
*  Kubernetes version 1.17+

## Architecture

### Source technology stack
N/A

### Source Architecture
N/A

### Target technology stack

*  Amazon EFS
*  Amazon EKS
*  AWS KMS
*  Fargate
*  Kubernetes

### Target Architecture

The target architect utilizes the products specified in the target architecture stack section, and follows AWS Well-Architected Framework best practices.

## Tools

*  awscli 2
*  eksctl 0.24.0+
*  kubectl 1.17+
*  jq 1.6+

## Epics

### Create a Kubernetes namespace for application workloads, and a linked Fargate profile

|Story|Description|Skills required|
|---|---|---|
|Create a Kubernetes namespace for application workloads|Create a namespace for receiving the application workloads that interact with the EFS.|Kubernetes User with granted permissions|
|Create a custom Fargate Profile|Create a custom Fargate profile linked to the created namespace.|Kubernetes User with granted permissions|
<br/>

#### Supporting script

The script `create-k8s-ns-and-linked-fargate-profile.sh` is responsible for executing both stories related to this epic:
*  Creating the `namespace` that will receive the application this PoC
*  Creating the [Fargate](https://aws.amazon.com/fargate/) profile linked to the created namespace

The scripts supports parameters and environment variables as follows:

|Input|Description|Env. Variable|Parameter|Precedence Order|Default Value|Mandatory|
|---|---|---|---|---|---|---|
|K8S Cluster Name|Name of the k8s cluster where this will be executed.|`export K8S_CLUSTER_NAME=<MY_CLUSTER_NAME>`|`-c <MY_CLUSTER_NAME>`|Parameter over env variable.|No default value.|Yes, error if not provided.|
|Application Namespace|Namespace in which the application will be deployed in order to make usage of [EFS](https://aws.amazon.com/efs/).|`export K8S_APP_NAMESPACE=<MY_APP_NAMESPACE>`|`-n <MY_APP_NAMESPACE>`|Parameter over env variable.|*poc-efs-eks-fargate*|No.|

<br/>Execute the script as follows:
```sh
./scripts/epic01/create-k8s-ns-and-linked-fargate-profile.sh \
    -c "MY_CLUSTER_NAME" 
```

### Create an EFS for application workloads

|Story|Description|Skills required|
|---|---|---|
|Generate an unique token for EFS creation|The EFS file system creation requires a creation token in the request to Amazon EFS, which is used to ensure idempotent creation (calling the operation with same creation token has no effect). Due to this requirement, generate an unique token through an available technique, for instance, Universally unique identifier (UUID).|System Administrator|
|(Optionally) Create a [Customer Managed Customer Master Key (CMK)](https://docs.aws.amazon.com/kms/latest/developerguide/concepts.html#master_keys)|Create an unique customer managed customer master key (CMK), symmetric key, in your AWS account and chosen region, that is used by EFS creation process. By the default, this epic is enabling encryption at rest when creating the EFS. If CMK is created, this key is used for the EFS encryption.|System Administrator|
|Create an encrypted EFS File System|Create the EFS for receiving the data files that are read/written by the application workloads. As a best practice, encryption at rest is enabled, and is setup at EFS creation process.<br/>This story is mutually exclusive to "Create an non-encrypted EFS File System".|System Administrator|
|Create an non-encrypted EFS File System|In the scenario where encryption at rest is not needed (default is to be enabled), create the EFS for receiving the data files that are read/written by the application workloads.<br/>This story is mutually exclusive to "Create an encrypted EFS File System".|System Administrator|
|Create a Security Group for NFS|Create a security group to allow EKS cluster to access EFS File System.|System Administrator|
|Enable NFS protocol inbound rule for created security group|Update the inbound rules of the created security group in order to allow incoming traffic for the following setting: protocol tcp, port 2049, and source as the Kubernetes cluster VPC private subnets' CIDR block ranges.|System Administrator|
|Add a Mount Target for each private subnet|For each private subnet of the Kubernetes cluster, create a mount target for the EFS and the security group that have been created.|System Administrator|
<br/>

#### Supporting script

The script `create-efs.sh` is responsible for executing from the second story on related to this epic:
*  (Optionally) Create a Customer Managed Customer Master Key (CMK) for EFS File System encryption
*  Create an (encrypted/unencrypted) EFS File System that will be the storage for the application workloads
*  Create a Security Group for the EFS in order to restrict access from the Kubernetes cluster
*  Enable EFS protocol/port in the created Security Group for Kubernetes cluster's private subnets' CIDR block ranges
*  Add a Mount Target for each private subnet of Kubernetes cluster

The first story is not implemented inside the script, in order to not generate a new [EFS](https://aws.amazon.com/efs/) anytime it is executed.

The scripts supports parameters and environment variables as follows:

|Input|Description|Env. Variable|Parameter|Precedence Order|Default Value|Mandatory|
|---|---|---|---|---|---|---|
|K8S Cluster Name|Name of the k8s cluster where this will be executed.|`export K8S_CLUSTER_NAME=<MY_CLUSTER_NAME>`|`-c <MY_CLUSTER_NAME>`|Parameter over env variable.|No default value.|Yes, error if not provided.|
|File System Token|The token that is used by [AWS CLI](https://aws.amazon.com/cli/) to create an [EFS](https://aws.amazon.com/efs/).|`export FS_TOKEN=<MY_FILE_SYSTEM_TOKEN>`|`-t <MY_FILE_SYSTEM_TOKEN>`|Parameter over env variable.|No default value.|Yes, error if not provided.|
|Security Group Name|The name of the security group that is used to protect access to the created [EFS](https://aws.amazon.com/efs/) that is accessed only by the Kubernetes cluster VPC private subnets' CIDR block ranges.|`export SG_EFS_NAME=<MY_SECURITY_GROUP_NAME_FOR_EFS_K8S_CLUSTER>`|`-s <MY_SECURITY_GROUP_NAME_FOR_EFS_K8S_CLUSTER>`|Parameter over env variable.|*eks-<MY_CLUSTER_NAME>-efs-SecurityGroup*|No.|
|Disabled Encryption at Rest|Identifies if the [EFS](https://aws.amazon.com/efs/) is going to be created without enabled encryption.|None.|`-d`|N/A|Encryption at rest enabled.|No.|
|Customer Managed Customer Master Key (CMK) Key Alias|Identifies the key alias for [Customer Managed Customer Master Key (CMK)](https://docs.aws.amazon.com/kms/latest/developerguide/concepts.html#master_keys) creation. The generated key is used in the [EFS](https://aws.amazon.com/efs/) creation process.|`export KMS_ALIAS=<MY_KMS_CMK_KEY_ALIAS>`|`-k <MY_KMS_CMK_KEY_ALIAS>`|Parameter over env variable.|No default value.|No, and ignored if `-d` parameter is informed.|

<br/>Execute the script as follows (for encryption at rest enabled):
```sh
./scripts/epic02/create-efs.sh \
    -c "MY_CLUSTER_NAME" \
    -t "MY_EFS_CREATION_TOKEN"
```

<br/>Execute the script as follows (for encryption at rest enabled and CMK creation):
```sh
./scripts/epic02/create-efs.sh \
    -c "MY_CLUSTER_NAME" \
    -t "MY_EFS_CREATION_TOKEN" \
    -k "MY_CMK_KEY_ALIAS"
```

<br/>Execute the script as follows (for encryption at rest disabled):
```sh
./scripts/epic02/create-efs.sh -d \
    -c "MY_CLUSTER_NAME" \
    -t "MY_EFS_CREATION_TOKEN"
```

### Install Amazon EFS Components into Kubernetes cluster

|Story|Description|Skills required|
|---|---|---|
|Deploy the Amazon EFS CSI driver into the cluster|Deploy the Amazon EFS CSI driver into the cluster in order to let it provision storage according to Persistent Volume Claims created by applications.|Kubernetes User with granted permissions|
|Deploy the storage class into the cluster	|Deploy the storage class into the cluster for the EFS provisioner (efs.csi.aws.com).|Kubernetes User with granted permissions|
<br/>

#### Supporting script

The script `create-k8s-efs-csi-sc.sh` is responsible for executing both stories related to this epic:
*  Deploying the `csi driver` into the Kubernetes cluster
*  Deploying the `storage class` for [EFS](https://aws.amazon.com/efs/) provisioner into the Kubernetes cluster

There is no parameter, nor environment variable for this script.

<br/>Execute the script as follows:
```sh
./scripts/epic03/create-k8s-efs-csi-sc.sh
```

### Install PoC Application into Kubernetes cluster

|Story|Description|Skills required|
|---|---|---|
|Deploy the Persistent Volume needed by the application|Deploy the persistent volume (PV) needed by the application for writing/reading content, linking it to the created storage class, and also to the created EFS file system ID.<br/>The defined PV can have any size specified in the storage field. This is a Kubernetes required field, but since [EFS](https://aws.amazon.com/efs/)  is an elastic file system, it does not really enforce any file system capacity. The Amazon EFS CSI Driver enables encryption by default, as a best practice.<br/>This story is mutually exclusive to "Deploy the Persistent Volume, without encryption in transit, needed by the application".|Kubernetes User with granted permissions|
|Deploy the Persistent Volume, without encryption in transit, needed by the application|Deploy the persistent volume (PV) needed by the application for writing/reading content, linking it to the created storage class, and also to the created EFS file system ID. The defined PV can have any size specified in the storage field. This is a Kubernetes required field, but since EFS is an elastic file system, it does not really enforce any file system capacity. In this story, the PV is configured to disable encryption in transit (what is enabled by default by Amazon EFS CSI Driver).<br/>This story is mutually exclusive to "Deploy the Persistent Volume needed by the application".|Kubernetes User with granted permissions|
|Deploy the Persistent Volume Claim requested by the application|Deploy the persistent volume claim (PVC) requested by the application, linking it to the created storage class, and with the same access mode of the created persistent volume (PV).<br/>The defined PVC can have any size specified in the *storage* field. This is a Kubernetes required field, but since [EFS](https://aws.amazon.com/efs/)  is an elastic file system, it does not really enforce any file system capacity.|Kubernetes User with granted permissions|
|Deploy the workload 1 of the application|Deploy the pod that represents the workload 1 of the application, and that write content to the file "/data/out1.txt".|Kubernetes User with granted permissions|
|Deploy the workload 2 of the application|Deploy the pod that represents the workload 2 of the application, and that write content to the file "/data/out2.txt".|Kubernetes User with granted permissions|
<br/>

#### Supporting script

The script `deploy-poc-app.sh` is responsible for executing both stories related to this epic:
*  Deploying the `persistent volume` needed by the application
*  Deploying the `persistent volume claim` requested by the application
*  Deploying the representation of workload 1 for this PoC, that writes content to a specific file in the created [EFS](https://aws.amazon.com/efs/) 
*  Deploying the representation of workload 2 for this PoC, that writes content to a specific file in the created [EFS](https://aws.amazon.com/efs/) 

The scripts supports parameters and environment variables as follows:

|Input|Description|Env. Variable|Parameter|Precedence Order|Default Value|Mandatory|
|---|---|---|---|---|---|---|
|File System Token|The token that was used by [AWS CLI](https://aws.amazon.com/cli/) to create an [EFS](https://aws.amazon.com/efs/).|`export FS_TOKEN=<MY_FILE_SYSTEM_TOKEN>`|`-t <MY_FILE_SYSTEM_TOKEN>`|Parameter over env variable.|No default value.|Yes, error if not provided.|
|Application Namespace|Namespace in which the application will be deployed in order to make usage of [EFS](https://aws.amazon.com/efs/).|`export K8S_APP_NAMESPACE=<MY_APP_NAMESPACE>`|`-n <MY_APP_NAMESPACE>`|Parameter over env variable.|*poc-efs-eks-fargate*|No.|
|Disabled Encryption in Transit|Identifies if the [EFS](https://aws.amazon.com/efs/) is going to be used without enabled encryption in transit.|None.|`-d`|N/A|Encryption in transit enabled.|No.|

<br/>Execute the script as follows (for encryption in transit enabled):
```sh
./scripts/epic04/deploy-poc-app.sh -t "MY_EFS_CREATION_TOKEN"
```

<br/>Execute the script as follows (for encryption in transit disabled):
```sh
./scripts/epic04/deploy-poc-app.sh -d -t "MY_EFS_CREATION_TOKEN"
```

### Validate EFS persistence, durability, and shareability throughout the workloads of the application

|Story|Description|Skills required|
|---|---|---|
|Validate that workload 1 is writing to specific file in the EFS|Validate that workload 1 of the application is writing to /data/out1.txt file in the EFS.|Kubernetes User with granted permissions|
|Validate that workload 2 is writing to specific file in the EFS|Validate that workload 2 of the application is writing to /data/out2.txt file in the EFS.|Kubernetes User with granted permissions|
|Validate that workload 1 is able to read file written by workload 2|Validate that workload 1 of the application is able to read the file /data/out2.txt, written by workload 2 of the application, from the EFS.|Kubernetes User with granted permissions|
|Validate that workload 2 is able to read file written by workload 1|Validate that workload 2 of the application is able to read the file /data/out1.txt, written by workload 1 of the application, from the EFS.|Kubernetes User with granted permissions|
|Validade that after removing application components, files are kept in the EFS|Validade that after removing application components (persistent volume, persistent volume claim, and pods) the files are kept in the EFS, due to the nature of retaining.|Kubernetes User with granted permissions|
<br/>

#### Supporting commands

For this epic, its executing is made by standalone commands (considering that the created `namespace` is called **poc-efs-eks-fargate**), excepting per the last story that has a supporting script.<br/>

***Validate that workload 1 is writing to specific file in the EFS***

*  Execute the script as follows:
    ```sh
    kubectl exec -ti poc-app1 -n poc-efs-eks-fargate -- tail -f /data/out1.txt
    ```
*  The results will be similar to this:
    ```sh
    ...
    Thu Sep  3 15:25:07 UTC 2020 - PoC APP 1
    Thu Sep  3 15:25:12 UTC 2020 - PoC APP 1
    Thu Sep  3 15:25:17 UTC 2020 - PoC APP 1
    ...
    ```

***Validate that workload 2 is writing to specific file in the EFS***

*  Execute the script as follows:
    ```sh
    kubectl exec -ti poc-app2 -n poc-efs-eks-fargate -- tail -f /data/out2.txt
    ```
*  The results will be similar to this:
    ```sh
    ...
    Thu Sep  3 15:26:48 UTC 2020 - PoC APP 2
    Thu Sep  3 15:26:53 UTC 2020 - PoC APP 2
    Thu Sep  3 15:26:58 UTC 2020 - PoC APP 2
    ...
    ```

***Validate that workload 1 is able to read file written by workload 2***

*  Execute the script as follows:
    ```sh
    kubectl exec -ti poc-app1 -n poc-efs-eks-fargate -- tail -n 3 /data/out2.txt
    ```
*  The results will be similar to this:
    ```sh
    Thu Sep  3 15:28:48 UTC 2020 - PoC APP 2
    Thu Sep  3 15:28:53 UTC 2020 - PoC APP 2
    Thu Sep  3 15:28:58 UTC 2020 - PoC APP 2
    ```

***Validate that workload 2 is able to read file written by workload 1***

*  Execute the script as follows:
    ```sh
    kubectl exec -ti poc-app2 -n poc-efs-eks-fargate -- tail -n 3 /data/out1.txt
    ```
*  The results will be similar to this:
    ```sh
    ...
    Thu Sep  3 15:29:22 UTC 2020 - PoC APP 1
    Thu Sep  3 15:29:27 UTC 2020 - PoC APP 1
    Thu Sep  3 15:29:32 UTC 2020 - PoC APP 1
    ...
    ```

***Validade that after removing application components, files are kept in the EFS***

This is story is accompained by a supporting script called `validate-efs-content.sh`, and does the follows:
*  Undeploy the PoC application components
*  Deploying the `persistent volume` requested by the validation process
*  Deploying the `persistent volume claim` requested by the validation process
*  Deploying the `pod` requested by the validation process
*  Executes the `find \data` command in the deployed pod

The scripts supports parameters and environment variables as follows:

|Input|Description|Env. Variable|Parameter|Precedence Order|Default Value|Mandatory|
|---|---|---|---|---|---|---|
|File System ID|The ID of the file system previously created.|`export FS_ID=<MY_EFS_FILE_SYSTEM_ID>`|1st parameter when calling the script.|Parameter over env variable.|No default value.|Yes, but only if File System Token is not provided.|
|File System Token|The token that was used by [AWS CLI](https://aws.amazon.com/cli/) to create an [EFS](https://aws.amazon.com/efs/).|`export FS_TOKEN=<MY_FILE_SYSTEM_TOKEN>`|2nd parameter when calling the script.|Parameter over env variable.|No default value.|Yes, for finding [EFS](https://aws.amazon.com/efs/) File System ID, if that was not provided.|
|Application Namespace|Namespace in which the application will be deployed in order to make usage of [EFS](https://aws.amazon.com/efs/).|`export K8S_APP_NAMESPACE=<MY_APP_NAMESPACE>`|3rd parameter when calling the script.|Parameter over env variable.|*poc-efs-eks-fargate*|No.|

<br/>Execute the script as follows:
```sh
./scripts/epic05/validate-efs-content.sh \
    -t "MY_EFS_FILE_SYSTEM_ID"
```

After deleting the PoC application components at first stage of this script, and installing the validation process components on the subsequent stages, the final result is going to be the following:
```sh
pod/poc-app-validation created
Waiting for pod get Running state...
Waiting for pod get Running state...
Waiting for pod get Running state...
Results from execution of 'find /data' on validation process pod:
/data
/data/out2.txt
/data/out1.txt
```

### A Day-2 Operation

As part of day-2 operation, monitor **AWS** resources for metrics that shows status of your whole solution. In this pattern, the stories implemented in this epic are shown as links into the "Related resources / References" section, instead of a step by step configuration.

|Story|Description|Skills required|
|---|---|---|
|Monitor application logs|As part of a day-2 operation, monitor the application logs, shipping them to CloudWatch.|Kubernetes User with granted permissions and System Administrator|
|Monitor Amazon EKS and Kubernetes Containers with Container Insights|As part of a day-2 operation, monitor Amazon EKS and Kubernetes systems using Container Insights, which collects metrics in different dimensions. The details related to this story are listed in the [Related resources / References](https://github.com/ricardosouzamorais/efs-on-eks-fargate#references) section.|Kubernetes User with granted permissions and System Administrator|
|Monitor Amazon EFS with CloudWatch|As part of a day-2 operation, monitor file systems using Amazon CloudWatch, which collects and processes raw data from Amazon EFS into readable, near real-time metrics. The details related to this story are listed in the [Related resources / References](https://github.com/ricardosouzamorais/efs-on-eks-fargate#references) section.|System Administrator|
<br/>

### Clean up resources

|Story|Description|Skills required|
|---|---|---|
|Clean up all created resources for the pattern|Desiring to finish this pattern, cleaning up resources is a best practice for cost optimization.|Kubernetes User with granted permissions and System Administrator|
<br/>

#### Supporting script

The script `clean-up-resources.sh` is responsible for executing the storiy related to this epic:
*  Cleaning up all created resources for the pattern

The scripts supports parameters and environment variables as follows:

|Input|Description|Env. Variable|Parameter|Precedence Order|Default Value|Mandatory|
|---|---|---|---|---|---|---|
|K8S Cluster Name|Name of the k8s cluster where this will be executed.|`export K8S_CLUSTER_NAME=<MY_CLUSTER_NAME>`|`-c <MY_CLUSTER_NAME>`|Parameter over env variable.|No default value.|Yes, error if not provided.|
|File System Token|The token that is used by [AWS CLI](https://aws.amazon.com/cli/) to create an [EFS](https://aws.amazon.com/efs/).|`export FS_TOKEN=<MY_FILE_SYSTEM_TOKEN>`|`-t <MY_FILE_SYSTEM_TOKEN>`|Parameter over env variable.|No default value.|Yes, error if not provided.|
|Security Group Name|The name of the security group that was created to protect access to the created [EFS](https://aws.amazon.com/efs/) that is accessed only by the Kubernetes cluster VPC private subnets' CIDR block ranges.|`export SG_EFS_NAME=<MY_SECURITY_GROUP_NAME_FOR_EFS_K8S_CLUSTER>`|`-s <MY_SECURITY_GROUP_NAME_FOR_EFS_K8S_CLUSTER>`|Parameter over env variable.|*eks-<MY_CLUSTER_NAME>-efs-SecurityGroup*|No.|
|Application Namespace|Namespace in which the application was deployed.|`export K8S_APP_NAMESPACE=<MY_APP_NAMESPACE>`|`-n <MY_APP_NAMESPACE>`|Parameter over env variable.|*poc-efs-eks-fargate*|No.|
|Customer Managed Customer Master Key (CMK) Key Alias|Identifies the key alias for [Customer Managed Customer Master Key (CMK)](https://docs.aws.amazon.com/kms/latest/developerguide/concepts.html#master_keys) used during the [EFS](https://aws.amazon.com/efs/) creation process.|`export KMS_ALIAS=<MY_KMS_CMK_KEY_ALIAS>`|`-k <MY_KMS_CMK_KEY_ALIAS>`|Parameter over env variable.|No default value.|No.|

<br/>Execute the script as follows (if encryption at rest enabled and CMK Key Alias was not informed):
```sh
./scripts/epic06/clean-up-resources.sh \
    -c "MY_CLUSTER_NAME" \
    -t "MY_EFS_CREATION_TOKEN"
```

<br/>Execute the script as follows (if encryption at rest enabled and CMK Key Alias was informed):
```sh
./scripts/epic06/clean-up-resources.sh \
    -c "MY_CLUSTER_NAME" \
    -t "MY_EFS_CREATION_TOKEN" \
    -k "MY_CMK_KEY_ALIAS"
```

## Related resources

### References
*  [New – AWS Fargate for Amazon EKS now supports Amazon EFS](https://aws.amazon.com/blogs/aws/new-aws-fargate-for-amazon-eks-now-supports-amazon-efs/)
*  [How to capture application logs when using Amazon EKS on AWS Fargate](https://aws.amazon.com/blogs/containers/how-to-capture-application-logs-when-using-amazon-eks-on-aws-fargate/)
*  [Using Container Insights](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/ContainerInsights.html)
*  [Setting Up Container Insights on Amazon EKS and Kubernetes](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/deploy-container-insights-EKS.html)
*  [Amazon EKS and Kubernetes Container Insights](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Container-Insights-metrics-EKS.html)
*  [Monitoring EFS with Amazon CloudWatch](https://docs.aws.amazon.com/efs/latest/ug/monitoring-cloudwatch.html)

### Tutorials
*  [Static provisioning](https://github.com/kubernetes-sigs/aws-efs-csi-driver/blob/master/examples/kubernetes/static_provisioning/README.md)
*  [Encryption in transit](https://github.com/kubernetes-sigs/aws-efs-csi-driver/blob/master/examples/kubernetes/encryption_in_transit/README.md)
*  [Accessing the file system from multiple pods](https://github.com/kubernetes-sigs/aws-efs-csi-driver/blob/master/examples/kubernetes/multiple_pods/README.md)
*  [Consume EFS in StatefulSets](https://github.com/kubernetes-sigs/aws-efs-csi-driver/blob/master/examples/kubernetes/statefulset/README.md)
*  [Mount subpath](https://github.com/kubernetes-sigs/aws-efs-csi-driver/blob/master/examples/kubernetes/volume_path/README.md)
*  [Use Access Points](https://github.com/kubernetes-sigs/aws-efs-csi-driver/blob/master/examples/kubernetes/access_points/README.md)

### Required Tools
*  [Installing the AWS CLI version 2](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html)
*  [Installing eksctl](https://docs.aws.amazon.com/eks/latest/userguide/getting-started-eksctl.html)
*  [Installing kubectl](https://docs.aws.amazon.com/eks/latest/userguide/install-kubectl.html)
*  [Installing jq](https://stedolan.github.io/jq/download/)