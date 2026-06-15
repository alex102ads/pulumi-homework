# Pulumi AWS Fargate Web App — How it works & how to deploy

## Overview
This project builds a small Flask web app (app/app.py) into a Docker image, pushes it to ECR, and deploys it to AWS Fargate behind an Application Load Balancer (ALB) using Pulumi (Python). The web page shows a configurable value read from the environment variable CUSTOM_VALUE (set via Pulumi config key `customValue`).

## Key files
- Pulumi.yaml — Pulumi project metadata
- requirements.txt — Python dependencies (pulumi, pulumi-aws, pulumi-docker)
- __main__.py — Pulumi program (contains a ComponentResource `WebApp` that encapsulates ECR image build, ALB, TargetGroup, ECS cluster, TaskDefinition, and Service)
- app/Dockerfile — builds the container
- app/app.py — Flask app; reads os.environ["CUSTOM_VALUE"]

## How the app works (component breakdown)
- ComponentResource `WebApp` creates:
  - ECR repository and pushes a Docker image built from `./app` using pulumi-docker.
  - Security Group allowing HTTP (80).
  - ALB + Listener + Target Group to receive internet traffic.
  - ECS Cluster, IAM execution role, Fargate TaskDefinition with container environment variable CUSTOM_VALUE injected from Pulumi config.
  - ECS Service (Fargate) with awsvpc networking attached to the ALB Target Group.
- The Pulumi program exports `url` (ALB DNS name) and `customValue`.

## Prerequisites
- macOS with:
  - Docker Desktop running (local Docker daemon) for building/pushing images.
  - AWS CLI credentials configured (profile or env vars) with permissions for: ECR, ECS, ELB, IAM, EC2 (VPC/subnets), CloudWatch.
- Python 3.8+.
- Pulumi CLI installed and logged in.

## Recommended AWS IAM permissions (high level)
Create or use an IAM principal with ability to create/manage: ecr, ecs, iam:CreateRole/AttachPolicy, elbv2, ec2 (security groups, describe VPC/subnets), and cloudwatch logs.

## Deploy steps (macOS commands)
1. Open a terminal and cd to project:
```bash
cd {{your_path}}/pulumi-homework
```

2. Create and activate a virtualenv:
```bash
python -m venv .venv
```
```bash
source .venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Ensure Docker Desktop is running.

5. Login to Pulumi (local or cloud):
```bash
pulumi login
```
(see Pulumi login docs: https://www.pulumi.com/docs/reference/cli/pulumi_login/)

6. Create or select a stack:
```bash
pulumi stack init dev
```
```bash
# or
pulumi stack select --create dev
```
(see Pulumi stacks docs: https://www.pulumi.com/docs/intro/concepts/stack/)

7. Configure values:
```bash
pulumi config set aws:region eu-west-1
```
```bash
pulumi config set customValue "Hello from Pulumi"
```

```bash
# optional:
pulumi config set serviceName myweb
```

```bash
# If using Colima for Docker, set the Docker socket for the pulumi-docker provider
# Replace <your_user> with your macOS username or the actual socket path
pulumi config set docker:host unix:///Users/<your_user>/.colima/default/docker.sock
```
(see Pulumi config docs: https://www.pulumi.com/docs/intro/concepts/config/)

8. Run preview and deploy:
```bash
pulumi up
```
```bash
# to auto-approve:
pulumi up --yes
```
(see pulumi up docs: https://www.pulumi.com/docs/reference/cli/pulumi_up/)

9. Get the app URL:
```bash
pulumi stack output url
```
Visit the returned ALB DNS in a browser; the page will show the configured custom value.
(see stack output docs: https://www.pulumi.com/docs/reference/cli/stack_output/)

## Cleanup
To remove all created resources:
```bash
pulumi destroy --yes
```
(see pulumi destroy docs: https://www.pulumi.com/docs/reference/cli/pulumi_destroy/)

To remove the stack:
```bash
pulumi stack rm dev
```
(see stack rm docs: https://www.pulumi.com/docs/reference/cli/stack_rm/)

## Notes & troubleshooting
- Docker must be able to push to ECR; the Pulumi program gets ECR credentials automatically.
- If you see permission errors, ensure AWS credentials under your environment (AWS_PROFILE/AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY) have the required IAM policies.

## Pulumi references

- Pulumi docs (home): https://www.pulumi.com/docs/
- Pulumi CLI reference (commands like pulumi up, pulumi destroy, stacks): https://www.pulumi.com/docs/reference/cli/
- Pulumi config (storing stack configuration): https://www.pulumi.com/docs/intro/concepts/config/
- Pulumi Python language docs: https://www.pulumi.com/docs/intro/languages/python/
- ComponentResource (authoring reusable components): https://www.pulumi.com/docs/intro/concepts/resources/components/
- pulumi-aws provider package (overview & available resources): https://www.pulumi.com/registry/packages/aws/
- pulumi-docker provider package (Image resource used to build/push images): https://www.pulumi.com/registry/packages/docker/
- pulumi-aws API docs (useful resource pages)
  - ECR Repository: https://www.pulumi.com/registry/packages/aws/api-docs/ecr/repository/
  - ECS Service: https://www.pulumi.com/registry/packages/aws/api-docs/ecs/service/
  - IAM Role: https://www.pulumi.com/registry/packages/aws/api-docs/iam/role/
  - CloudWatch LogGroup: https://www.pulumi.com/registry/packages/aws/api-docs/cloudwatch/logGroup/