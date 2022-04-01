

# Media file processing using AWS Lambda and Amazon EFS

In this demo we are going to use AWS SAM and Lambda Layer to process large video files and shall create screenshots for each second of the video. This will uses to the FFmpeg Linux package to process the video. After copying the MP4 to the EFS file location, we will invoke the Lambda function to create a series of JPG frames.

This pattern explains how to deploy an AWS SAM application that includes an API Gateway and a Lambda function with Amazon EFS access.



### Requirements

* AWS CLI already configured with Administrator permission
* AWS SAM is also installed 
* [NodeJS 12.x installed](https://nodejs.org/en/download/)
* An MP4 video - `video.mp4` is not provided in this repo. You can pick any random video of your choice.

### Setup

We assume that you have created the file system as mentioned in [this section](/application-integration/ec2/README.md) 

### Creating Access Point 

Since AWS Lambda can access the EFS file system only using `Access Point` so, lets go ahead and create an `Access Point` 

![](/application-integration/serverless/img/1.png)

Click on `Create access point` and create an access point, `app1` 

![](/application-integration/serverless/img/2.png)

Once the `access point` is created note the ARN of the access point, as we will need this later

![](/application-integration/serverless/img/3.png)


## Deploy the application 

1. From the command line of your workstation where `awscli` and `SAM` is installed, 

```
suman:~/environment $ sam --version
SAM CLI, version 1.33.0


suman:~/environment $ aws --version
aws-cli/2.4.25 Python/3.8.8 Linux/4.14.268-205.500.amzn2.x86_64 exe/x86_64.amzn.2 prompt/off

```

2. Create a sam project folder `my-efs-lambda-demo`

```
suman:~/environment $ mkdir my-efs-lambda-demo

suman:~/environment $ cd my-efs-lambda-demo

suman:~/environment/my-efs-lambda-demo $ 

```

3. Copy the content of this [repo](/application-integration/serverless/media-file-processing/) folder inside this newly created folder `my-efs-lambda-demo` 

```
suman:~/environment/my-efs-lambda-demo $ pwd
/home/ec2-user/environment/my-efs-lambda-demo
 
suman:~/environment/my-efs-lambda-demo $ ll
total 4
drwxr-xr-x 2 ec2-user ec2-user   40 Mar 29 16:13 processFile
-rw-r--r-- 1 ec2-user ec2-user 2121 Mar 29 16:13 template.yaml

```

4. Since we are going to use Lambda Layer for our application, lets fist create that, go to this [repo](https://serverlessrepo.aws.amazon.com/applications/us-east-1/145266761615/ffmpeg-lambda-layer) and click on `Deploy` 

Once it is deployed, you can check the same in the Lambda console, as we can see bellow, 

![](/application-integration/serverless/img/9.png)

Just take a note of this Layer ARN, as we are going to need this in the next step. 

5. Open the `template.yaml` and update the Layer ARN 

![](/application-integration/serverless/img/10.png)


6. Now, we can build the application, using `sam build` 

```
suman:~/environment/my-efs-lambda-demo $ sam build 
Building codeuri: /home/ec2-user/environment/my-efs-lambda-demo/processFile runtime: nodejs12.x metadata: {} architecture: x86_64 functions: ['ProcessFileFunction']
Running NodejsNpmBuilder:NpmPack
Running NodejsNpmBuilder:CopyNpmrc
Running NodejsNpmBuilder:CopySource
Running NodejsNpmBuilder:NpmInstall
Running NodejsNpmBuilder:CleanUpNpmrc

Build Succeeded

Built Artifacts  : .aws-sam/build
Built Template   : .aws-sam/build/template.yaml

Commands you can use next
=========================
[*] Invoke Function: sam local invoke
[*] Deploy: sam deploy --guided
    
suman:~/environment/my-efs-lambda-demo $ 

```

7. Now, we can deploy the application using `sam deploy -g`. 
   But, before you go ahead, have the following handy from [this previous demo](/application-integration/ec2/README.md)  

    - SecurityGroupIds (`sg-0dca469f9305ecd95`)
    - SubnetIDs (`subnet-e39eb2cd, subnet-0499bb58, subnet-483a4e76`)
    - AccessPointARN (ARN of the access point we created in the previous section)

![](/application-integration/serverless/img/4.png)

Wait for the application to get deployed 

![](/application-integration/serverless/img/5.png)


8. Now we can mount the same access point on the EC2 instance which we created in [this previous demo](/application-integration/ec2/README.md)  and copy some `video.MP4` file on the EFS File System 

```
# Login to the EC2 Instance 

$ sudo mount -t efs -o tls,accesspoint=fsap-01fc2a95463dc966b fs-0f55c9f4dda3dc344:/ efs

# Copy some video file (like in this case its `video.MP4`) into our EFS FS 

$ ll
total 16588
drwxrwxrwx 2 ec2-user ec2-user     6144 Mar 29 16:32 efs
-rw-rw-r-- 1 ec2-user ec2-user 16981034 Mar 29 16:33 video.MP4

$ mv video.MP4 efs/

$ ll efs/
total 16584
-rw-rw-r-- 1 ec2-user ec2-user 16981034 Mar 29 16:33 video.MP4

$ 

```

9. So, now at this point we have the video file stored inside our EFS file system, so now we go to our AWS Lambda console and we can invoke the lambda function and that will run our `ffmpeg` application which will create a series of JPG frames and will save all the frames inside the same EFS file system (as we have mentioned the same in the [code](/application-integration/serverless/demo2/processFile/app.js))

Since we are going to trigger this lambda function manually, we need to configure a dummy test first. 

![](/application-integration/serverless/img/6.png)

![](/application-integration/serverless/img/7.png)

So, now we can click on `Test` and trigger the lambda function 

![](/application-integration/serverless/img/8.png)

10. Now, we can go back to our EC2 instance and check if the application has executed sucessfully and created series of JPG frames 

``` 
# Login to the EC2 Instance 

$ cd efs

$ ls 
100.jpg  109.jpg  117.jpg  19.jpg  27.jpg  35.jpg  43.jpg  51.jpg  5.jpg   68.jpg  76.jpg  84.jpg  92.jpg  video.MP4
101.jpg  10.jpg   11.jpg   1.jpg   28.jpg  36.jpg  44.jpg  52.jpg  60.jpg  69.jpg  77.jpg  85.jpg  93.jpg
102.jpg  110.jpg  12.jpg   20.jpg  29.jpg  37.jpg  45.jpg  53.jpg  61.jpg  6.jpg   78.jpg  86.jpg  94.jpg
103.jpg  111.jpg  13.jpg   21.jpg  2.jpg   38.jpg  46.jpg  54.jpg  62.jpg  70.jpg  79.jpg  87.jpg  95.jpg
104.jpg  112.jpg  14.jpg   22.jpg  30.jpg  39.jpg  47.jpg  55.jpg  63.jpg  71.jpg  7.jpg   88.jpg  96.jpg
105.jpg  113.jpg  15.jpg   23.jpg  31.jpg  3.jpg   48.jpg  56.jpg  64.jpg  72.jpg  80.jpg  89.jpg  97.jpg
106.jpg  114.jpg  16.jpg   24.jpg  32.jpg  40.jpg  49.jpg  57.jpg  65.jpg  73.jpg  81.jpg  8.jpg   98.jpg
107.jpg  115.jpg  17.jpg   25.jpg  33.jpg  41.jpg  4.jpg   58.jpg  66.jpg  74.jpg  82.jpg  90.jpg  99.jpg
108.jpg  116.jpg  18.jpg   26.jpg  34.jpg  42.jpg  50.jpg  59.jpg  67.jpg  75.jpg  83.jpg  91.jpg  9.jpg

$

```

As we can see we have all these images saved here, which are saved by our lambda function. And this also shows how we can make use of EFS as a shared storage across different compute service (in this case Amazon EC2 instances and AWS Lambda)