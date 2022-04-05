import { FileSystem } from '@aws-cdk/aws-efs';
import { AwsCustomResource, AwsCustomResourcePolicy, PhysicalResourceId } from '@aws-cdk/custom-resources';

/**
 * We use a collection of `AwsCustomResource` constructs, indexed by their name, to create
 * the EFS Access Points via the AWS SDK. This is a stop-gap until support for creating
 * EFS Access Points via CloudFormation and CDK is available.
 */
export class EfsAccessPoints extends Map {
  constructor(
    fileSystem: FileSystem,
    createEcsOnEc2AccessPoints: boolean,
    createFargateAccessPoints: boolean,
  ) {
    super()

    /*
      Configuration for the Access Points we're going to be creating so that we can do so iteratively.
      Note that the "Common" Access Point is always created.
    */
    const accessPointConfigs = [
      {name: 'Common', posixId: 6000, path: '/common'},
      ...(createEcsOnEc2AccessPoints ? [{name: 'EcsShared', posixId: 3000, path: '/shared/ecs'}] : []),
      ...(createEcsOnEc2AccessPoints ? [{name: 'EcsPrivate', posixId: 3000, path: '/private/ecs'}] : []),
      ...(createFargateAccessPoints ? [{name: 'FargateShared', posixId: 7000, path: '/shared/fargate'}] : []),
      ...(createFargateAccessPoints ? [{name: 'FargatePrivate', posixId: 7000, path: '/private/fargate'}] : []),
    ];

    /*
      Use a `AwsCustomResource` to create each EFS Access Point based on the `accessPointConfigs` array above
      via the AWS SDK. They'll each be keyed by their name for easy access using <EfsAccessPoints>.get(...).
    */
    accessPointConfigs.forEach((config: {name: string, posixId: number, path: string}) => {
      this.set(
        config.name,
        new AwsCustomResource(
          fileSystem.stack,
          'EfsAccessPoint' + config.name, {
          onUpdate: {
            action: 'createAccessPoint',
            parameters: {
              FileSystemId: fileSystem.fileSystemId,
              PosixUser: {
                Gid: config.posixId,
                Uid: config.posixId,
              },
              RootDirectory: {
                CreationInfo: {
                  OwnerGid: config.posixId,
                  OwnerUid: config.posixId,
                  Permissions: 750,
                },
                Path: config.path,
              },
              Tags: [{Key: 'Name', Value: config.name},
              ],
            },
            physicalResourceId: PhysicalResourceId.fromResponse('AccessPointArn'),
            service: 'EFS',
          },
          policy: AwsCustomResourcePolicy.fromSdkCalls({
            resources: AwsCustomResourcePolicy.ANY_RESOURCE,
          }),
        },
        )
      )
    });
  }
}
