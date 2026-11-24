# AWS EC2 R25 — deployment

The project uses an existing Ubuntu 24.04 EC2 instance, m7i-flex.large
in eu-north-1, encrypted 30 GB gp3 EBS, IMDSv2 and termination protection.
Terraform defines the EC2, dedicated security group and imported existing
SSH public key. Terraform state and credentials remain outside Git.
The existing infrastructure does not need to be recreated.

## Runtime

- MySQL 8.4 on a persistent Docker volume, no published database port.
- Django/Gunicorn with DEBUG=False and environment-based configuration.
- Nginx on port 80 permits public anonymous GET/HEAD; authenticated API
  requests use SSH local forwarding to the web service on loopback 18765.
- SSH ingress is restricted to a trusted IPv4/32.

The deployment uses [compose.aws.yml](compose.aws.yml) and
[nginx.conf](nginx.conf). Required variables are declared in Compose;
the server environment file .env.aws is private and excluded from Git.
Deployment commands, from the project root on the existing server
(after backup and migration rehearsal):

```bash
docker compose --env-file .env.aws -f infra/aws-ec2-r25/compose.aws.yml config --quiet
docker compose --env-file .env.aws -f infra/aws-ec2-r25/compose.aws.yml up -d --build
docker compose --env-file .env.aws -f infra/aws-ec2-r25/compose.aws.yml ps
```

## Verified results

19 November 2026: deployment, migrations and healthchecks passed;
public HTTP 16/16, authenticated HTTP/JWT via SSH forwarding 68/68.
21 November 2026: release f318e89 and migrations listings.0004 and
bookings.0004 deployed; existing data preserved, public HTTP 22/22,
isolated MySQL test suite 91/91. Full authenticated regression for this
updated release remains incomplete.

24 November 2026: local application regression passed on two MySQL
environments (123/123 in normal and reverse order), HTTP 62/62,
Postman 41 requests / 87 assertions. These are local results; the
current code has not been deployed to EC2.

The last verified EC2 state (21 November) is stopped; the original EBS
and MySQL volume are retained. A subsequent Start requires a fresh
identity, cost and connectivity check; deployment requires a verified
backup, migration rehearsal and authenticated regression. EC2 is stopped
after the verification window. EBS storage may incur charges while
the instance is stopped. The project does not use RDS, NAT Gateway or
an additional load balancer. See the [deployment report](../../docs/deployment-contingency.md).
