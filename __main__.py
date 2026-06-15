import json
import pulumi
from pulumi import ResourceOptions
import pulumi_aws as aws
import pulumi_docker as docker

# ----------------------------
# CONFIGURATION (Pulumi inputs)
# ----------------------------
# https://www.pulumi.com/docs/intro/concepts/config/#configuring-stacks
config = pulumi.Config()

# Value shown in the web app (via env var)
custom_value = config.get("customValue") or "default-value"

# Name used for naming AWS resources consistently
service_name = config.get("serviceName") or "webapp"

# Docker image platform (useful for ARM vs x86 differences in AWS)
image_platform = config.get("imagePlatform") or "linux/amd64"

# Image tag derived from platform (helps avoid caching issues)
image_tag = config.get("imageTag") or f"v1-{image_platform.replace('/','-')}"

# AWS region (needed for CloudWatch logging configuration)
region = aws.get_region().name


# ----------------------------
# COMPONENT RESOURCE
# ----------------------------
# This encapsulates the full application stack:
# - ECR (container registry)
# - Docker build & push
# - Networking (VPC subnets, SG)
# - ALB (load balancer)
# - ECS Fargate service
# ----------------------------
# https://www.pulumi.com/docs/iac/guides/building-extending/components/build-a-component/#defining-a-component-resource
class WebApp(pulumi.ComponentResource):

    def __init__(self, name, image_tag, opts=None):

        # Register this as a reusable Pulumi component
        super().__init__("examples:WebApp", name, None, opts)

        # ----------------------------
        # 1. ECR Repository
        # ----------------------------
        # Stores Docker images in AWS
        # https://www.pulumi.com/registry/packages/aws/api-docs/ecr/repository/

        self.repo = aws.ecr.Repository(
            f"{name}-repo",
            opts=ResourceOptions(parent=self)
        )

        # Get credentials to push Docker image to ECR
        # https://www.pulumi.com/registry/packages/aws/api-docs/ecr/getauthorizationtoken/

        auth = aws.ecr.get_authorization_token_output(
            registry_id=self.repo.registry_id
        )

        username = auth.user_name
        password = auth.password

        # Full image name: repo_url:tag
        image_name = pulumi.Output.concat(
            self.repo.repository_url,
            ":",
            image_tag
        )

        # ----------------------------
        # 2. Build & Push Docker Image
        # ----------------------------
        # Pulumi builds local Docker image and pushes to ECR
        # https://www.pulumi.com/registry/packages/docker/api-docs/image/

        image = docker.Image(
            f"{name}-image",
            build=docker.DockerBuildArgs(
                context="./app",
                platform=image_platform  # supports ARM/x86
            ),
            image_name=image_name,
            registry=docker.RegistryArgs(
                server=self.repo.repository_url,
                username=username,
                password=password,
            ),
            opts=ResourceOptions(parent=self.repo),
        )

        # ----------------------------
        # 3. Networking (VPC)
        # ----------------------------
        # Uses default VPC instead of creating new network
        # https://www.pulumi.com/registry/packages/aws/api-docs/ec2/getvpc/

        default_vpc = aws.ec2.get_vpc(default=True)

        # Get all subnets in default VPC (needed for ALB + ECS)
        # https://www.pulumi.com/registry/packages/aws/api-docs/ec2/getsubnets/

        subnet_ids = aws.ec2.get_subnets(
            filters=[
                aws.ec2.GetSubnetsFilterArgs(
                    name="vpc-id",
                    values=[default_vpc.id]
                )
            ]
        )

        # ----------------------------
        # 4. Security Group
        # ----------------------------
        # Allows HTTP traffic from internet to ALB
        # https://www.pulumi.com/registry/packages/aws/api-docs/ec2/securitygroup/

        self.sg = aws.ec2.SecurityGroup(
            f"{name}-sg",
            description="allow http",
            vpc_id=default_vpc.id,

            ingress=[
                aws.ec2.SecurityGroupIngressArgs(
                    protocol="tcp",
                    from_port=80,
                    to_port=80,
                    cidr_blocks=["0.0.0.0/0"]
                )
            ],

            egress=[
                aws.ec2.SecurityGroupEgressArgs(
                    protocol="-1",
                    from_port=0,
                    to_port=0,
                    cidr_blocks=["0.0.0.0/0"]
                )
            ],

            opts=ResourceOptions(parent=self),
        )

        # ----------------------------
        # 5. Application Load Balancer
        # ----------------------------
        # https://www.pulumi.com/registry/packages/aws/api-docs/lb/loadbalancer/

        alb = aws.lb.LoadBalancer(
            f"{name}-alb",
            security_groups=[self.sg.id],
            subnets=subnet_ids.ids,
            opts=ResourceOptions(parent=self),
        )

        # Target group for ECS tasks
        # https://www.pulumi.com/registry/packages/aws/api-docs/lb/targetgroup/

        tg = aws.lb.TargetGroup(
            f"{name}-tg",
            port=80,
            protocol="HTTP",
            target_type="ip",  # required for Fargate
            vpc_id=default_vpc.id,
            opts=ResourceOptions(parent=alb),
        )

        # Listener: forwards traffic from ALB -> ECS tasks
        # https://www.pulumi.com/registry/packages/aws/api-docs/lb/listener/

        listener = aws.lb.Listener(
            f"{name}-listener",
            load_balancer_arn=alb.arn,
            port=80,
            default_actions=[
                aws.lb.ListenerDefaultActionArgs(
                    type="forward",
                    target_group_arn=tg.arn
                )
            ],
            opts=ResourceOptions(parent=alb),
        )

        # ----------------------------
        # 6. ECS Cluster
        # ----------------------------
        # https://www.pulumi.com/registry/packages/aws/api-docs/ecs/cluster/

        self.cluster = aws.ecs.Cluster(
            f"{name}-cluster",
            opts=ResourceOptions(parent=self)
        )

        # ----------------------------
        # 7. IAM Role for ECS Task
        # ----------------------------
        # Allows ECS to pull image & write logs
        # https://www.pulumi.com/registry/packages/aws/api-docs/iam/role/

        exec_role = aws.iam.Role(
            f"{name}-exec-role",
            assume_role_policy=json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Action": "sts:AssumeRole",
                    "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                    "Effect": "Allow"
                }]
            }),
            opts=ResourceOptions(parent=self),
        )
        # https://www.pulumi.com/registry/packages/aws/api-docs/iam/rolepolicyattachment/

        aws.iam.RolePolicyAttachment(
            f"{name}-exec-policy-attach",
            role=exec_role.name,
            policy_arn="arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
            opts=ResourceOptions(parent=exec_role),
        )

        # ----------------------------
        # 8. CloudWatch Logs
        # ----------------------------
        # https://www.pulumi.com/registry/packages/aws/api-docs/cloudwatch/loggroup/

        log_group = aws.cloudwatch.LogGroup(
            f"{name}-log",
            name=pulumi.Output.concat("/ecs/", name),
            retention_in_days=7,
            opts=ResourceOptions(parent=self),
        )

        # ----------------------------
        # 9. ECS Task Definition
        # ----------------------------
        # Defines container runtime configuration
        # https://www.pulumi.com/registry/packages/aws/api-docs/ecs/taskdefinition/
        # https://www.pulumi.com/docs/iac/concepts/inputs-outputs/all/

        container_def = pulumi.Output.all(
            image.image_name,
            log_group.name,
            region
        ).apply(lambda args: json.dumps({
            "name": service_name,
            "image": args[0],

            # Container port exposed internally
            "portMappings": [{
                "containerPort": 80,
                "protocol": "tcp"
            }],

            # Environment variable passed into container
            "environment": [
                {
                    "name": "CUSTOM_VALUE",
                    "value": custom_value
                }
            ],

            # Logs sent to CloudWatch
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": args[1],
                    "awslogs-region": args[2],
                    "awslogs-stream-prefix": "ecs"
                }
            }
        }))

        # https://www.pulumi.com/registry/packages/aws/api-docs/ecs/taskdefinition/#container_definitions

        task = aws.ecs.TaskDefinition(
            f"{name}-task",
            family=f"{name}-taskdef",
            cpu="256",
            memory="512",
            network_mode="awsvpc",
            requires_compatibilities=["FARGATE"],
            execution_role_arn=exec_role.arn,
            container_definitions=container_def,
            opts=ResourceOptions(parent=self),
        )

        # ----------------------------
        # 10. ECS Service
        # ----------------------------
        # https://www.pulumi.com/registry/packages/aws/api-docs/ecs/service/

        self.svc = aws.ecs.Service(
            f"{name}-svc",
            cluster=self.cluster.arn,
            desired_count=1,
            launch_type="FARGATE",
            task_definition=task.arn,

            network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
                subnets=subnet_ids.ids,
                security_groups=[self.sg.id],
                assign_public_ip=True,
            ),

            load_balancers=[aws.ecs.ServiceLoadBalancerArgs(
                target_group_arn=tg.arn,
                container_name=service_name,
                container_port=80,
            )],

            # ensure listener + logs exist before service starts
            opts=ResourceOptions(
                parent=self,
                depends_on=[listener, log_group]
            ),
        )

        # ----------------------------
        # OUTPUTS
        # ----------------------------
        # ALB DNS name = public URL of application

        self.url = alb.dns_name
        # https://www.pulumi.com/docs/iac/guides/building-extending/components/build-a-component/#registering-component-outputs

        self.register_outputs({
            "url": self.url
        })


# ----------------------------
# STACK ENTRYPOINT
# ----------------------------

app = WebApp("mypulumiweb", image_tag=image_tag)

pulumi.export("url", app.url)
pulumi.export("customValue", custom_value)