# Bitcoin Blockchain with Amazon ECS and Amazon EFS

In this demo walkthrough, we experiment with the Bitcoin Blockchain on AWS and demonstrate how to set up a Bitcoin Node on AWS that can be used to send and receive bitcoin from an external wallet.  

Here is the detailed blog on [Experimenting with Bitcoin Blockchain on AWS](https://aws.amazon.com/blogs/industries/experimenting-with-bitcoin-blockchain-on-aws/)

## Architecture 

For the infrastructure, we use Amazon Elastic Container Service (Amazon ECS) with AWS Fargate in a public/private VPC across two  Availability Zones and spin up one AWS Fargate Service for the Bitcoin Node and the Electrum Server. 

All Blockchain data of the Bitcoin Core Full Node and the transaction data of the ElectrumX server are stored on a shared Amazon Elastic File System (Amazon EFS) that gets mounted to the running Fargate Service Task in one of the Private Subnets. This provides high availability for these services in one AWS region.

![](/application-integration/container/img/1.png)
