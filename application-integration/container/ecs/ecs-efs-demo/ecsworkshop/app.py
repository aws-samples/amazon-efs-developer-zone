from aws_cdk import (
    aws_ecs as ecs,
    aws_ec2 as ec2,
    aws_elasticloadbalancingv2 as elbv2,
    aws_iam as iam,
    aws_efs as efs,
    aws_logs as logs,
    aws_servicediscovery as sd,
    core
)

from os import getenv


class ECSFargateEFSDemo(core.Stack):

    def __init__(self, scope: core.Stack, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        self.environment_name = 'ecsworkshop'

        ## Importing existing VPC and ECS Cluster ##
        self.vpc = ec2.Vpc.from_lookup(
            self, "VPC",
            vpc_name='{}-base/BaseVPC'.format(self.environment_name)
        )

        self.sd_namespace = sd.PrivateDnsNamespace.from_private_dns_namespace_attributes(
            self, "SDNamespace",
            namespace_name=core.Fn.import_value('NSNAME'),
            namespace_arn=core.Fn.import_value('NSARN'),
            namespace_id=core.Fn.import_value('NSID')
        )
        
        self.ecs_cluster = ecs.Cluster.from_cluster_attributes(
            self, "ECSCluster",
            cluster_name=core.Fn.import_value('ECSClusterName'),
            security_groups=[],
            vpc=self.vpc,
            default_cloud_map_namespace=self.sd_namespace
        )
        ## End VPC and ECS Cluster ##

        ## Load balancer for ECS service ##
        self.frontend_sec_grp = ec2.SecurityGroup(
            self, "FrontendIngress",
            vpc=self.vpc,
            allow_all_outbound=True,
            description="Frontend Ingress All port 80",
        )

        self.load_balancer = elbv2.ApplicationLoadBalancer(
            self, "ALB",
            security_group=self.frontend_sec_grp,
            internet_facing=True,
            vpc=self.vpc
        )

        self.target_group = elbv2.ApplicationTargetGroup(
            self, "ALBTG",
            port=8000,
            target_group_name="ECSDemoFargateEFS",
            vpc=self.vpc,
            target_type=elbv2.TargetType.IP
        )
        
        self.load_balancer.add_listener(
            "FrontendListener",
            default_target_groups=[
                self.target_group
            ],
            port=80
        )
        ## End Load balancer ##

        ## EFS Setup ##
        self.service_sec_grp = ec2.SecurityGroup(
            self, "EFSSecGrp",
            vpc=self.vpc,
            description="Allow access to self on NFS Port",
        )

        self.service_sec_grp.connections.allow_from(
            other=self.service_sec_grp,
            port_range=ec2.Port(protocol=ec2.Protocol.TCP, string_representation="Self", from_port=2049, to_port=2049)
        )
        
        # TODO: possibly create another sec grp for 8000
        self.service_sec_grp.connections.allow_from(
            other=self.frontend_sec_grp,
            port_range=ec2.Port(protocol=ec2.Protocol.TCP, string_representation="LB2Service", from_port=8000, to_port=8000)
        )

        self.shared_fs = efs.FileSystem(
            self, "SharedFS",
            vpc=self.vpc,
            security_group=self.service_sec_grp,
        )
        ## End EFS Setup ##

        ## TODO: IAM Role to access EFS access points for task ##

        # Task execution role
        self.task_execution_role = iam.Role(
            self, "TaskExecutionRole",
            assumed_by=iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
            description="Task execution role for ecs services",
            managed_policies=[
                iam.ManagedPolicy.from_managed_policy_arn(self, 'arn', managed_policy_arn='arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy')
            ]
        )

        ## END IAM ##
        
        ## Logging ##
        self.service_log_group = logs.LogGroup(self, "ECSEFSDemoLogGrp")
        ## END Logging ##
        
        # Cloudformation Outputs
        core.CfnOutput(
            self, "ExecutionRoleARN",
            value=self.task_execution_role.role_arn,
            export_name="ECSFargateEFSDemoTaskExecutionRoleARN"
        )

        core.CfnOutput(
            self, "EFSID",
            value=self.shared_fs.file_system_id,
            export_name="ECSFargateEFSDemoFSID"
        )

        core.CfnOutput(
            self, "LBName",
            value=self.load_balancer.load_balancer_name,
            export_name="ECSFargateEFSDemoLBName"
        )

        core.CfnOutput(
            self, "TargetGroupArn",
            value=self.target_group.target_group_arn,
            export_name="ECSFargateEFSDemoTGARN"
        )

        core.CfnOutput(
            self, "VPCPrivateSubnets",
            value=",".join([x.subnet_id for x in self.vpc.private_subnets]),
            export_name="ECSFargateEFSDemoPrivSubnets"
        )

        core.CfnOutput(
            self, "SecurityGroups",
            value="{},{}".format(self.frontend_sec_grp.security_group_id, self.service_sec_grp.security_group_id),
            export_name="ECSFargateEFSDemoSecGrps"
        )
        
        core.CfnOutput(
            self, "LBURL",
            value=self.load_balancer.load_balancer_dns_name,
            export_name="ECSFargateEFSDemoLBURL"
        )

        core.CfnOutput(
            self, "LogGroupName",
            value=self.service_log_group.log_group_name,
            export_name="ECSFargateEFSDemoLogGroupName"
        )


app = core.App()

_env = core.Environment(account=getenv('AWS_ACCOUNT_ID'), region=getenv('AWS_DEFAULT_REGION'))

ECSFargateEFSDemo(app, "ecsworkshop-efs-fargate-demo", env=_env)

app.synth()
