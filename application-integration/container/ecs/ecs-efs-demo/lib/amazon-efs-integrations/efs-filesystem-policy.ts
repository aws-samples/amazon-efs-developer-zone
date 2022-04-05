import { FileSystem } from '@aws-cdk/aws-efs';
import { AwsCustomResource, AwsCustomResourcePolicy, PhysicalResourceId } from '@aws-cdk/custom-resources';
import { Arn } from '@aws-cdk/core';
import { EfsAccessPoints } from './efs-access-points';
import { ApplicationLoadBalancedEc2Service, ApplicationLoadBalancedFargateService } from '@aws-cdk/aws-ecs-patterns';

/**
 * We use this `AwsCustomResource` construct to create the EFS filesystem policy via the AWS SDK. This
 * is a stop-gap until support for creating EFS filesystem policies via CloudFormation and CDK is available.
 */
export class EfsFileSystemPolicy extends AwsCustomResource {
  constructor(
    fileSystem: FileSystem,
    accessPoints: EfsAccessPoints,
    ecsOnEc2Service?: ApplicationLoadBalancedEc2Service,
    ecsOnFargateService?: ApplicationLoadBalancedFargateService,
  ) {
    // We'll be using this value several times throughout.
    const fileSystemArn = Arn.format(
      {service: 'elasticfilesystem', resource: 'file-system', resourceName: fileSystem.fileSystemId},
      fileSystem.stack,
    );

    /*
      Initialize statement list with equivalent of:
        * Disable root access by default
        * Enforce read-only access by default
        * Enforce in-transit encryption for all clients
     */
    const statements: object[] = [
      {
        Sid: 'DisableRootAccessAndEnforceReadOnlyByDefault',
        Effect: 'Allow',
        Action: 'elasticfilesystem:ClientMount',
        Principal: {
          AWS: '*',
        },
        Resource: fileSystemArn,
      },
      {
        Sid: 'EnforceInTransitEncryption',
        Effect: 'Deny',
        Action: ['*'],
        Principal: {
          AWS: '*',
        },
        Resource: fileSystemArn,
        Condition: {
          Bool: {'aws:SecureTransport': false},
        },
      },
    ];

    if (ecsOnEc2Service) {
      // Allow r/w for ECS on EC2 Service to Common, EcsPrivate, and EcsShared
      statements.push({
        Sid: 'EcsOnEc2CloudCmdTaskReadWriteAccess',
        Effect: 'Allow',
        Action: [
          'elasticfilesystem:ClientMount',
          'elasticfilesystem:ClientWrite',
        ],
        Principal: {
          AWS: ecsOnEc2Service.taskDefinition.taskRole.roleArn,
        },
        Resource: fileSystemArn,
        Condition: {
          StringEquals: {
            'elasticfilesystem:AccessPointArn': [
              accessPoints.get('Common')?.getResponseField('AccessPointArn'),
              accessPoints.get('EcsPrivate')?.getResponseField('AccessPointArn'),
              accessPoints.get('EcsShared')?.getResponseField('AccessPointArn'),
            ].filter((arn) => arn),
          },
        },
      });

      if (ecsOnFargateService) {
        // Allow readonly for ECS on EC2 Service to FargateShared, if exists.
        statements.push({
          Sid: 'EcsOnEc2CloudCmdTaskReadAccess',
          Effect: 'Allow',
          Action: [
            'elasticfilesystem:ClientMount',
          ],
          Principal: {
            AWS: ecsOnEc2Service.taskDefinition.taskRole.roleArn,
          },
          Resource: fileSystemArn,
          Condition: {
            StringEquals: {
              'elasticfilesystem:AccessPointArn': [
                accessPoints.get('FargateShared')?.getResponseField('AccessPointArn'),
              ].filter((arn) => arn),
            },
          },
        });
      }
    }

    if (ecsOnFargateService) {
      // Allow r/w for ECS on Fargate Service to Common, FargatePrivate, and FargateShared
      statements.push({
        Sid: 'EcsOnFargateCloudCmdTaskReadWriteAccess',
        Effect: 'Allow',
        Action: [
          'elasticfilesystem:ClientMount',
          'elasticfilesystem:ClientWrite',
        ],
        Principal: {
          AWS: ecsOnFargateService.taskDefinition.taskRole.roleArn,
        },
        Resource: fileSystemArn,
        Condition: {
          StringEquals: {
            'elasticfilesystem:AccessPointArn': [
              accessPoints.get('Common')?.getResponseField('AccessPointArn'),
              accessPoints.get('FargatePrivate')?.getResponseField('AccessPointArn'),
              accessPoints.get('FargateShared')?.getResponseField('AccessPointArn'),
            ].filter((arn) => arn),
          },
        },
      });

      if (ecsOnEc2Service) {
        // Allow readonly for ECS on Fargate Service to EcsShared, if exists.
        statements.push({
          Sid: 'EcsOnFargateCloudCmdTaskReadAccess',
          Effect: 'Allow',
          Action: [
            'elasticfilesystem:ClientMount',
          ],
          Principal: {
            AWS: ecsOnFargateService.taskDefinition.taskRole.roleArn,
          },
          Resource: fileSystemArn,
          Condition: {
            StringEquals: {
              'elasticfilesystem:AccessPointArn': [
                accessPoints.get('EcsShared')?.getResponseField('AccessPointArn'),
              ].filter((arn) => arn),
            },
          },
        });
      }
    }

    const createOrUpdateFileSystemPolicy = {
      action: 'putFileSystemPolicy',
      parameters: {
        FileSystemId: fileSystem.fileSystemId,
        Policy: fileSystem.stack.toJsonString({
          Version: '2012-10-17',
          Statement: statements,
        }),
      },
      physicalResourceId: PhysicalResourceId.fromResponse('FileSystemId'),
      service: 'EFS',
    };

    // Create the actual policy based on the statements assembled above.
    super(
      fileSystem.stack,
      'EfsFileSystemPolicy', {
        onCreate: createOrUpdateFileSystemPolicy,
        onUpdate: createOrUpdateFileSystemPolicy,
        policy: AwsCustomResourcePolicy.fromSdkCalls({
          resources: AwsCustomResourcePolicy.ANY_RESOURCE,
        }),
      },
    );
  }
};
