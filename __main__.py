import json

import pulumi
from pulumi import ResourceOptions
import pulumi_aws as aws
import pulumi_docker as docker

config = pulumi.Config()
custom_value = config.get("customValue") or "default-value"
service_name = config.get("serviceName") or "webapp"

# allow choosing image platform (set via `pulumi config set imagePlatform linux/arm64` if Fargate uses Graviton)
image_platform = config.get("imagePlatform") or "linux/amd64"
image_tag = config.get("imageTag") or f"v1-{image_platform.replace('/','-')}"

# add/get region (used for awslogs option)
region = aws.get_region().name

class WebApp(pulumi.ComponentResource):
    def __init__(self, name, image_tag, opts=None):
        super().__init__("examples:WebApp", name, None, opts)

        # ECR repo
        repo = aws.ecr.Repository(f"{name}-repo", opts=ResourceOptions(parent=self))

        # Get ECR auth token
        auth = aws.ecr.get_authorization_token_output(registry_id=repo.registry_id)

        password = auth.password
        username = auth.user_name

        image_name = pulumi.Output.concat(repo.repository_url, ":", image_tag)

        # Build & push image to ECR (honor configured platform)
        image = docker.Image(
            f"{name}-image",
            build=docker.DockerBuildArgs(context="./app", platform=image_platform),
            image_name=image_name,
            registry=docker.RegistryArgs(
                server=repo.repository_url,
                username=username,
                password=password,
            ),
            opts=ResourceOptions(parent=repo),
        )

        # Network: default VPC & subnets
        default_vpc = aws.ec2.get_vpc(default=True)
        subnet_ids = aws.ec2.get_subnets(filters=[aws.ec2.GetSubnetsFilterArgs(name="vpc-id", values=[default_vpc.id])])

        # Security Group for ALB -> service
        sg = aws.ec2.SecurityGroup(
            f"{name}-sg",
            description="allow http",
            vpc_id=default_vpc.id,
            ingress=[aws.ec2.SecurityGroupIngressArgs(protocol="tcp", from_port=80, to_port=80, cidr_blocks=["0.0.0.0/0"])],
            egress=[aws.ec2.SecurityGroupEgressArgs(protocol="-1", from_port=0, to_port=0, cidr_blocks=["0.0.0.0/0"])],
            opts=ResourceOptions(parent=self),
        )

        # ALB
        alb = aws.lb.LoadBalancer(
            f"{name}-alb",
            security_groups=[sg.id],
            subnets=subnet_ids.ids,
            opts=ResourceOptions(parent=self),
        )

        tg = aws.lb.TargetGroup(
            f"{name}-tg",
            port=80,
            protocol="HTTP",
            target_type="ip",
            vpc_id=default_vpc.id,
            opts=ResourceOptions(parent=alb),
        )

        listener = aws.lb.Listener(
            f"{name}-listener",
            load_balancer_arn=alb.arn,
            port=80,
            default_actions=[aws.lb.ListenerDefaultActionArgs(type="forward", target_group_arn=tg.arn)],
            opts=ResourceOptions(parent=alb),
        )

        # ECS Cluster
        cluster = aws.ecs.Cluster(f"{name}-cluster", opts=ResourceOptions(parent=self))

        # IAM roles
        exec_role = aws.iam.Role(
            f"{name}-exec-role",
            assume_role_policy=json.dumps({"Version":"2012-10-17","Statement":[{"Action":"sts:AssumeRole","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Effect":"Allow"}]}),
            opts=ResourceOptions(parent=self),
        )
        aws.iam.RolePolicyAttachment(
            f"{name}-exec-policy-attach",
            role=exec_role.name,
            policy_arn="arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
            opts=ResourceOptions(parent=exec_role),
        )

        # create CloudWatch log group (ensure exists before task starts)
        log_group = aws.cloudwatch.LogGroup(
            f"{name}-log",
            name=pulumi.Output.concat("/ecs/", name),
            retention_in_days=7,
            opts=ResourceOptions(parent=self),
        )

        # Task definition (Fargate)
        container_def = pulumi.Output.all(image.image_name, log_group.name, region).apply(
            lambda args: json.dumps([{
                "name": service_name,
                "image": args[0],
                "portMappings": [{"containerPort": 80, "protocol": "tcp"}],
                "environment": [{"name":"CUSTOM_VALUE","value": custom_value}],
                "logConfiguration": {
                    "logDriver": "awslogs",
                    "options": {
                        "awslogs-group": args[1],
                        "awslogs-region": args[2],
                        "awslogs-stream-prefix": "ecs"
                    }
                }
            }])
        )

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

        svc = aws.ecs.Service(
            f"{name}-svc",
            cluster=cluster.arn,
            desired_count=1,
            launch_type="FARGATE",
            task_definition=task.arn,
            network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
                subnets=subnet_ids.ids,
                security_groups=[sg.id],
                assign_public_ip=True,
            ),
            load_balancers=[aws.ecs.ServiceLoadBalancerArgs(
                target_group_arn=tg.arn,
                container_name=service_name,
                container_port=80,
            )],
            opts=ResourceOptions(parent=self, depends_on=[listener, log_group]),
        )

        self.url = alb.dns_name
        self.register_outputs({"url": self.url})

# Instantiate component (use the computed image_tag)
app = WebApp("mypulumiweb", image_tag=image_tag)

pulumi.export("url", app.url)
pulumi.export("customValue", custom_value)