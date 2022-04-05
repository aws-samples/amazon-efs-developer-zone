## ECS with EFS Demo

### Purpose

The purpose of this repo is to showcase how you can run a stateful container on ECS Fargate. We will be using EFS for the persistent storage layer that the containers will share and use.

### Requirements

- AWS CLI
- AWS CDK
- Python3.6 +
- AWS Access Keys or an IAM role attached to the instance running with permissions to build the below resources.

```bash
pip install -r requirements.txt
```

This was tested on a Cloud9 instance.

### Step 1

#### What are we doing

Using the cdk, we will build all of the required components for our service to launch. This includes the following:

- VPC (including subnets, nat gateway, internet gateway, etc)
- Public facing Application Load Balancer
- EFS filesystem
- ECS Cluster
- Security Group controls

#### Build the environment

Navigate to step_1 directory

Run a diff to compare what exists in the environment currently, vs what we are proposing to build.

```bash
cdk diff
```

The output should show the creation of all the new resources for the environment. When you're done reviewing, time to deploy.

```bash
cdk deploy --require-approval never
```

Once the environment is built, move on to the step_2 directory.

### Step 2

#### What are we doing

Now that we have an environment up and running, we're going to deploy a stateful containerized service on [AWS Fargate](https://aws.amazon.com/efs/) with [AWS EFS](https://aws.amazon.com/efs/) as the stateful backend storage.

The service we are deploying is a cloud file manager, [Cloud Commander](https://cloudcmd.io/). Once deployed, we will add new files, and then terminate the task. The orchestrator will spawn a new task as it recognizes that the service is not meeting it's desired state. When the new task is spawned, we should see the files that we added remain! Let's get to it.

#### Set the environment variables from what we deployed in step 1

In order to deploy a service in the VPC, there are resources from the environment built that will need to be referenced. These include subnets, security groups, ECS cluster, EFS file system id, and so on. 

Run the following to export all of the resource values that we will need to reference:

```bash
export cloudformation_outputs=$(aws cloudformation describe-stacks --stack-name ecsworkshop-efs-fargate-demo | jq .Stacks[].Outputs)
export execution_role_arn=$(echo $cloudformation_outputs | jq -r '.[]| select(.ExportName | contains("ECSFargateEFSDemoTaskExecutionRoleARN"))| .OutputValue')
export fs_id=$(echo $cloudformation_outputs | jq -r '.[]| select(.ExportName | contains("ECSFargateEFSDemoFSID"))| .OutputValue')
export target_group_arn=$(echo $cloudformation_outputs | jq -r '.[]| select(.ExportName | contains("ECSFargateEFSDemoTGARN"))| .OutputValue')
export private_subnets=$(echo $cloudformation_outputs | jq -r '.[]| select(.ExportName | contains("ECSFargateEFSDemoPrivSubnets"))| .OutputValue')
export security_groups=$(echo $cloudformation_outputs | jq -r '.[]| select(.ExportName | contains("ECSFargateEFSDemoSecGrps"))| .OutputValue')
export load_balancer_url=$(echo $cloudformation_outputs | jq -r '.[]| select(.ExportName | contains("ECSFargateEFSDemoLBURL"))| .OutputValue')
export log_group_name=$(echo $cloudformation_outputs | jq -r '.[]| select(.ExportName | contains("ECSFargateEFSDemoLogGroupName"))| .OutputValue')
export cluster_name="ECS-Fargate-EFS-Demo"
export container_name="cloudcmd-rw"
```

#### Create the task definition

In ECS, the first step to getting a container (or containers) running is to define the task definition. The task definition will define our desired state of how we want to operate our docker containers. 

Feel free to review the file `task_definition.json`. In this task definition, we define how and where to log the container logs, memory/cpu requirements, port mappings, and most importantly (with regards to this workshop) our container mount point to the EFS mount. There's much more to review, but those are some high level items.

For more information on a task definition, see [here](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definitions.html).

First we need to populate some of the values in the definition from the environment we created in step 1.

```bash
  sed "s|{{EXECUTIONROLEARN}}|$execution_role_arn|g;s|{{TASKROLEARN}}|$task_role_arn|g;s|{{FSID}}|$fs_id|g;s|{{LOGGROUPNAME}}|$log_group_name|g" task_definition.json > task_definition.automated
```
  
Next, it's time to create the task definition. We export the output from the task definition into an environment variable that we will use when deploying the service.
```bash
  export task_definition_arn=$(aws ecs register-task-definition --cli-input-json file://"$PWD"/task_definition.automated | jq -r .taskDefinition.taskDefinitionArn)
```

#### Create the Service

With a Task Definition created, we can now create a service. The service will take that desired state of our container, and ensure that we always run `n` number of tasks, as well as placing the tasks behind the Load Balancer that we created in step 1.

For more information on services in ECS, see [here](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs_services.html).

Run the following command to create the service:

```bash
  aws ecs create-service \
  --cluster $cluster_name \
  --service-name cloudcmd-rw \
  --task-definition "$task_definition_arn" \
  --load-balancers targetGroupArn="$target_group_arn",containerName="$container_name",containerPort=8000 \
  --desired-count 1 \
  --platform-version 1.4.0 \
  --launch-type FARGATE \
  --deployment-configuration maximumPercent=100,minimumHealthyPercent=0 \
  --network-configuration "awsvpcConfiguration={subnets=["$private_subnets"],securityGroups=["$security_groups"],assignPublicIp=DISABLED}"
```

#### Open the service in your browser

Now that the service is created, we can access it via the load balancer url. Let's grab that and open it in our browser.

Open the Load Balancer URL in your browser, here's the command to get the url:

**NOTE**: It may take a couple of minutes before you can access the url

```bash
echo "http://$load_balancer_url"
```

#### Add a directory to the UI

The web interface should look something like this:

![ui](./cc-ui.png)

At the bottom of the interface, you should see `F7`, Click that, and name the directory `EFS_DEMO`

![bottom](./cc-bottom.png)

Now you should see a directory named `EFS_DEMO`. This file is stored on the EFS volume that is mounted to the container. To showcase this, let's go ahead and kill the task, and when the scheduler brings up a new one, we should see the same directory.


#### Stop the task and go back to the UI

To stop the task: 

```bash
task_arn=$(aws ecs list-tasks --cluster $cluster_name --service-name cloudcmd-rw | jq -r .taskArns[])
aws ecs stop-task --task $task_arn --cluster $cluster_name
```

When you go back to the Load Balancer URL in the browser, you should see a 503 error. 

#### Wait for the new task, and confirm the directory we created is showing

In a couple of minutes, head back to the URL and you should see the UI again. Also, you should see your directory `EFS_DEMO` listed.

That's it! You've successfully created a stateful service in Fargate and watched as a task died and was replaced with the same stateful backend storage layer.

#### Cleanup

```bash
aws ecs update-service --cluster $cluster_name --service cloudcmd-rw --desired-count 0
task_arn=$(aws ecs list-tasks --cluster $cluster_name --service-name cloudcmd-rw | jq -r .taskArns[])
aws ecs stop-task --task $task_arn --cluster $cluster_name
aws ecs delete-service --cluster $cluster_name --service cloudcmd-rw
cdk destroy -f
```