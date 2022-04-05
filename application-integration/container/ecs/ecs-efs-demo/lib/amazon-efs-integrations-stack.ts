import { InstanceType, Port, SecurityGroup, Vpc } from '@aws-cdk/aws-ec2';
import { Cluster } from '@aws-cdk/aws-ecs';
import { FileSystem } from '@aws-cdk/aws-efs';
import { Construct, Stack, StackProps } from '@aws-cdk/core';
import { EfsAccessPoints } from './amazon-efs-integrations/efs-access-points';
import { EfsFileSystemPolicy } from './amazon-efs-integrations/efs-filesystem-policy';
import { EcsEfsIntegrationService, ServiceType } from './amazon-efs-integrations/ecs-service';
import { ApplicationLoadBalancedFargateService, ApplicationLoadBalancedEc2Service } from '@aws-cdk/aws-ecs-patterns';

export interface AmazonEfsIntegrationsStackProps extends StackProps {
  /**
   * Whether or not to create the ECS on EC2 service to show the EFS integration
   */
  readonly createEcsOnEc2Service: boolean;
  /**
   * Whether or not to create the ECS on EC2 service to show the EFS integration
   */
  readonly createEcsOnFargateService: boolean;
  /**
   * Whether or not to create the EFS filesystem to show the EFS integration
   */
  readonly createEfsFilesystem: boolean;

  /**
   * Whether or not to create the EFS access points to show the EFS integration
   */
  readonly createEfsAccessPoints: boolean;
}

export class AmazonEfsIntegrationsStack extends Stack {
  constructor(scope: Construct, id: string, props: AmazonEfsIntegrationsStackProps) {
    if (props.createEfsAccessPoints && !props.createEfsFilesystem) {
      throw new Error('`createEfsFileSystem` must be set to true if `createEfsAccessPoints` is true');
    }

    super(scope, id, props);

    const vpc = new Vpc(this, 'EfsIntegrationDemo', {maxAzs: 2});
    const efsSecurityGroup = new SecurityGroup(this, 'EfsSecurityGroup', {securityGroupName: 'efs-demo-fs', vpc});

    let fileSystem;
    let efsAccessPoints;

    if (props.createEfsFilesystem) {
      /* tslint:disable-next-line:no-unused-expression */
      fileSystem = new FileSystem(this, 'EfsIntegrationDemoFileSystem', {
        encrypted: true,
        fileSystemName: 'efs-demo-fs',
        securityGroup: efsSecurityGroup,
        vpc,
      });

      if (props.createEfsAccessPoints) {
        efsAccessPoints = new EfsAccessPoints(
          fileSystem,
          props.createEcsOnEc2Service,
          props.createEcsOnFargateService,
        );
      }
    }

    if (props.createEcsOnEc2Service || props.createEcsOnFargateService) {
      const cluster = new Cluster(this, 'EcsCluster', {vpc});
      let ecsOnEc2Service;
      let ecsOnFargateService;

      if (props.createEcsOnEc2Service) {
        cluster.addCapacity('DefaultAutoScalingGroup', {
          instanceType: new InstanceType('t2.large'),
          maxCapacity: 2,
          minCapacity: 2,
        });

        ecsOnEc2Service = EcsEfsIntegrationService.create(
          ServiceType.EC2,
          cluster,
          fileSystem,
          efsAccessPoints
        ) as ApplicationLoadBalancedEc2Service;
        efsSecurityGroup.connections.allowFrom(ecsOnEc2Service.service, Port.tcp(2049));
      }

      if (props.createEcsOnFargateService) {
        ecsOnFargateService = EcsEfsIntegrationService.create(
          ServiceType.FARGATE,
          cluster,
          fileSystem,
          efsAccessPoints
        ) as ApplicationLoadBalancedFargateService;
        efsSecurityGroup.connections.allowFrom(ecsOnFargateService.service, Port.tcp(2049));
      }

      if (props.createEfsAccessPoints && fileSystem && efsAccessPoints) {
        // tslint:disable-next-line: no-unused-expression
        new EfsFileSystemPolicy(
          fileSystem,
          efsAccessPoints,
          ecsOnEc2Service,
          ecsOnFargateService,
        );
      }
    }
  }
}
