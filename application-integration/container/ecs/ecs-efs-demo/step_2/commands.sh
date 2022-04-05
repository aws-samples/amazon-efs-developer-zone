#!/bin/bash

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

register_task_def() {
  sed "s|{{EXECUTIONROLEARN}}|$execution_role_arn|g;s|{{TASKROLEARN}}|$task_role_arn|g;s|{{FSID}}|$fs_id|g;s|{{LOGGROUPNAME}}|$log_group_name|g;s|{{REGION}}|$AWS_REGION|g" task_definition.json > task_definition.automated
  export task_definition_arn=$(aws ecs register-task-definition --cli-input-json file://"$PWD"/task_definition.automated | jq -r .taskDefinition.taskDefinitionArn)
}

create_service() {
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
}

#register_task_def
create_service

