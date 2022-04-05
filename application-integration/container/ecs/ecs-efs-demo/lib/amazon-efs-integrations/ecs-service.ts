import { CfnService, ContainerImage, Cluster, Ec2TaskDefinition, FargatePlatformVersion, NetworkMode, Protocol, LogDriver } from '@aws-cdk/aws-ecs';
import { FileSystem } from '@aws-cdk/aws-efs';
import { Duration } from '@aws-cdk/core';
import { AwsCustomResource, AwsCustomResourcePolicy, PhysicalResourceId } from '@aws-cdk/custom-resources';
import { EfsAccessPoints } from './efs-access-points';
import {
  ApplicationLoadBalancedEc2ServiceProps,
  ApplicationLoadBalancedEc2Service,
  ApplicationLoadBalancedFargateService,
  ApplicationLoadBalancedFargateServiceProps
} from '@aws-cdk/aws-ecs-patterns';

export enum ServiceType {
  EC2 = 'Ec2',
  FARGATE = 'Fargate'
}

interface MountPoint {
  containerPath: string,
  sourceVolume: string
};

interface Volume {
  name: string,
  efsVolumeConfiguration?: {
    fileSystemId: string,
    authorizationConfig?: {
      iam: string,
      accessPointId: string,
    },
    transitEncryption: string,
  },
}

export class EcsEfsIntegrationService {
  static create(
    serviceType: ServiceType,
    cluster: Cluster,
    fileSystem?: FileSystem,
    efsAccessPoints?: EfsAccessPoints,
    props?: ApplicationLoadBalancedEc2ServiceProps | ApplicationLoadBalancedFargateServiceProps,
  ) {
    let service: ApplicationLoadBalancedEc2Service | ApplicationLoadBalancedFargateService;

    const containerImage = 'coderaiser/cloudcmd:14.3.10-alpine';
    if (serviceType === ServiceType.EC2) {
      /*
        Initial task definition with the 80:80 port mapping is needed here to ensure the ALB security
        group is created properly. This is not necessary for the Fargate service.
        @todo: Remove when CDK supports EFS for ECS fully.
      */
      const initialEc2TaskDefinition = new Ec2TaskDefinition(cluster, 'Ec2ServiceInitialTaskDefinition', {})
      const container = initialEc2TaskDefinition.addContainer('cloudcmd', {
        image: ContainerImage.fromRegistry(containerImage),
        logging: LogDriver.awsLogs({streamPrefix: 'ecs'}),
        memoryLimitMiB: 512,
      })
      container.addPortMappings({
        containerPort: 80,
        hostPort: 80,
        protocol: Protocol.TCP
      })
      service = new ApplicationLoadBalancedEc2Service(cluster.stack, 'Ec2Service', {
        cluster,
        desiredCount: 2,
        memoryLimitMiB: 512,
        taskDefinition: initialEc2TaskDefinition,
        ...props,
      });
    } else {
      service = new ApplicationLoadBalancedFargateService(cluster.stack, 'FargateService', {
        cluster,
        desiredCount: 2,
        platformVersion: FargatePlatformVersion.VERSION1_4,
        taskImageOptions: {
          containerName: 'cloudcmd',
          image: ContainerImage.fromRegistry(containerImage),
        },
        ...props
      });
    }

    // Required to run Cloud Commander from behind the ALB
    service.targetGroup.enableCookieStickiness(Duration.minutes(5));

    let mountPoints: MountPoint[] = [];
    let volumes: Volume[] = [];

    if (efsAccessPoints) {
      efsAccessPoints.forEach((ap: AwsCustomResource, name: string) => {
        // Don't add the "EcsPrivate" AP on the Fargate task (and vice-versa)
        if (
          (serviceType === ServiceType.EC2 && name === 'FargatePrivate') ||
          (serviceType === ServiceType.FARGATE && name === 'EcsPrivate')
        ) {
          return
        }

        // Drop the "ecs" or "fargate" suffix if it's the "private" access point
        const containerPath = '/files' + (
          (name === 'FargatePrivate' || name === 'EcsPrivate') ? '/private' : ap.getResponseField('RootDirectory.Path')
        );

        mountPoints.push({containerPath, sourceVolume: name})
        volumes.push({
          name,
          efsVolumeConfiguration: {
            fileSystemId: fileSystem!.fileSystemId,
            authorizationConfig: {
              iam: 'ENABLED',
              accessPointId: ap.getResponseField('AccessPointId'),
            },
            transitEncryption: 'ENABLED',
          }
        })
      });
    } else {
      // Whether it's a "Bind Mount" or a root EFS filesystem mount, we'll be using "/files" as the mount point
      mountPoints = [{
        containerPath: '/files',
        sourceVolume: 'files',
      }];

      // `efsVolumeConfiguration` if we're mounting the root EFS filesystem.
      if (fileSystem) {
        volumes = [{
          efsVolumeConfiguration: {
            fileSystemId: fileSystem.fileSystemId,
            transitEncryption: 'ENABLED',
          },
          name: 'files',
        }];
      } else {
        volumes = [{name: 'files'}];
      }
    }

    /*
      This JSON structure represents the final desired task definition, which includes the
      EFS volume configurations. This is a stop-gap measure that will be replaced when this
      capability is fully supported in CloudFormation and CDK.
    */
    const customTaskDefinitionJson = {
      containerDefinitions: [
        {
          command: [
            '--no-keys-panel',
            '--one-file-panel',
            '--port=80',
            '--root=/files',
          ],
          essential: true,
          image: containerImage,
          logConfiguration: {
            logDriver: service.taskDefinition.defaultContainer?.logDriverConfig?.logDriver,
            options: service.taskDefinition.defaultContainer?.logDriverConfig?.options,
          },
          memory: 512,
          mountPoints,
          name: service.taskDefinition.defaultContainer?.containerName,
          portMappings: [
            {
              containerPort: 80,
              hostPort: 80,
              protocol: 'tcp',
            },
          ],
        },
      ],
      cpu: '256',
      executionRoleArn: service.taskDefinition.executionRole?.roleArn,
      family: service.taskDefinition.family,
      memory: '1024',
      networkMode: serviceType === ServiceType.EC2 ? NetworkMode.BRIDGE : NetworkMode.AWS_VPC,
      requiresCompatibilities: [
        serviceType.toUpperCase(),
      ],
      taskRoleArn: service.taskDefinition.taskRole.roleArn,
      volumes,
    };

    /*
      We use `AwsCustomResource` to create a new task definition revision with EFS volume
      configurations, which is available in the AWS SDK.
    */
    const createOrUpdateCustomTaskDefinition = {
      action: 'registerTaskDefinition',
      outputPath: 'taskDefinition.taskDefinitionArn',
      parameters: customTaskDefinitionJson,
      physicalResourceId: PhysicalResourceId.fromResponse('taskDefinition.taskDefinitionArn'),
      service: 'ECS',
    };
    const customTaskDefinition = new AwsCustomResource(service, 'Custom' + serviceType + 'TaskDefinition', {
      onCreate: createOrUpdateCustomTaskDefinition,
      onUpdate: createOrUpdateCustomTaskDefinition,
      policy: AwsCustomResourcePolicy.fromSdkCalls({
        resources: AwsCustomResourcePolicy.ANY_RESOURCE,
      }),
    });
    service.taskDefinition.executionRole?.grantPassRole(customTaskDefinition.grantPrincipal);
    service.taskDefinition.taskRole.grantPassRole(customTaskDefinition.grantPrincipal);

    /*
      Finally, we'll update the ECS service to use the new task definition revision
      that we just created above.
    */
    (service.service.node.tryFindChild('Service') as CfnService)?.addPropertyOverride(
      'TaskDefinition',
      customTaskDefinition.getResponseField('taskDefinition.taskDefinitionArn'),
    );

    return service;
  };
}
