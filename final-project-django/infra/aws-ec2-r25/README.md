# AWS EC2 R25 — preflight, deployment and Stop/Start

**Newer source, not yet deployed (21 November 2026).**
The main Django repository now includes six data-model improvements (commit `4fc80b8`) and new `listings.0004` / `bookings.0004`
migrations. Local MySQL migration and 91/91 tests passed. **This code is
NOT installed on EC2**. The last verified EC2 deployment is from
19 November; the instance was then STOPPED with its database volume intact.
Do not run it or apply new DDL without separately approved cloud work and
a verified server-side database backup / migration rehearsal.
See [the model integrity changes and safe update plan](../../docs/model-integrity-2026-11-21.md).

**Latest verified status — 19 November 2026: AWS deployment PASS; existing EC2 STOPPED with MySQL data preserved.** On the same pre-existing `m7i-flex.large` in Stockholm, `docker compose --env-file .env.aws -f infra/aws-ec2-r25/compose.aws.yml up -d --build` succeeded. Confirmed Ubuntu 24.04.5, Docker Engine 29.10.0, Compose v5.8.0, Python 3.14.10, Django 5.2.19, DRF 3.18.3, Gunicorn 27.0.1, MySQL 8.4.13 (`mysql:8.4`, InnoDB) and Nginx 1.28.3. DB/web healthchecks, all initial migrations, `migrate --check`, Django check, no pending migrations, Nginx syntax, and `DEBUG=False` passed. Only port 80 is public; port 18765 is bound to EC2 loopback, while ports 3306/8000 are not public.

**Live test evidence:** public HTTP **16/16** (anonymous GET/HEAD 200, invalid range 400, private routes 404, unsafe public methods 403); authenticated HTTP/content assertions through temporary **SSH local port forwarding** **68/68** (synthetic Tenant/Landlord, listing/permissions, bookings/confirm/conflict/reject/cancel, completed stay, review/rating, statistics, registration, login/logout/blacklisted refresh). The forwarding process was closed. A MySQL container restart kept the same persistent Docker volume **`lms271-r25_mysql_data`** and the same database counts before/after: **7 users, 5 listings, 11 bookings, 1 review**. Schema returned 200 again after restart. Separately, local Mac Docker/MySQL regression suite passed **84/84 Django unit/API/integration tests**; test database dropped by Django runner. Full HTTP status details: [deployment-contingency](../../docs/deployment-contingency.md).

**Cloud safety and billing:** same original instance, same Terraform state, Security Group and SSH Key Pair; **no new Terraform apply**, no EC2 replacement, no new private keys. SSH `/32` matched the workstation, and SSH host key matched the previous trusted host key. Only `DJANGO_ALLOWED_HOSTS` was updated inside the existing server `.env.aws` (0600), retaining its synthetic secrets. The session used a dynamically assigned EC2 IPv4 (now released). At **2026-11-19 14:20 UTC**, AWS Cost Explorer returned **$0 estimated** for November; no AWS Budget was configured, and Cost Explorer can lag. The same EC2 was explicitly **stopped** and verified through AWS CLI/API: `stopped`, no public IP, termination protection enabled, encrypted **30 GB gp3 EBS in-use/attached**. The persistent MySQL volume remains on that EBS, which can accrue storage charges while the instance is stopped. Technical R25 deployment is verified, **not continuously online**. Next action before the **11 December 2026** defense: Start this same EC2, confirm updated IP/SSH `/32` and trusted key, adjust only private allowed hosts as needed, check MySQL volume, HTTP and JWT again, then Stop after defense. Teacher assessment and LMS submission have not happened.

**Historical status (earlier 19.11.2026): Docker Engine 29.10.0 / Compose v5.8.0 verified on EC2; instance STOPPED; Django/MySQL deployment not yet started.** The owner performed the Docker installation on Ubuntu 24.04.5 LTS and added `ubuntu` to the remote `docker` group. Verified via SSH: `docker info`, `docker ps` work without `sudo`, and `docker compose --env-file .env.aws -f infra/aws-ec2-r25/compose.aws.yml config --quiet` succeeds on EC2. No containers or MySQL volume exist yet. **Current EC2 is stopped again**, preserving the installed Docker, app files and private `.env.aws` on root EBS. Docker group membership grants root-equivalent permissions on EC2. **This current status supersedes the historical setup blocker below.**

**Historical status (earlier 19.11.2026): infrastructure created, instance STOPPED; Django not yet deployed.** Approved Terraform apply finished **1 added / 0 changed / 0 destroyed** (Ubuntu 24.04 `m7i-flex.large`, Stockholm). The dedicated Security Group and imported existing EC2 Key Pair are unchanged. The encrypted 30 GB gp3 root EBS remains attached; EC2 was explicitly stopped to prevent compute charges, not terminated. `/home/ubuntu/lms271` contains the tracked Django source from Git `69533da` and a private `.env.aws` (0600), but **Docker is not installed; no MySQL volume, migrations or AWS HTTP/API checks exist**. The available Mac Desktop Commander tool forbids privileged `sudo` commands, required for the official Ubuntu Docker Engine bootstrap; this safeguard was not bypassed. **R25 remains open.** Official setup instructions: https://docs.docker.com/engine/install/ubuntu/. The following initial preflight steps are historical; never reapply an old plan or create a duplicate instance. The current Terraform state is authoritative.

## Applied Terraform scope (19.11.2026)

- Account: the existing Fresh Deploy AWS account, accessed with the temporary AWS CLI profile docker-course.
- Allowed region: eu-north-1 (Stockholm) only; use the existing default VPC and one default subnet. No changes to default or launch-wizard-1 Security Groups or old Docker 7 Terraform state.
- Managed resources: exactly one Ubuntu 24.04 x86_64 **m7i-flex.large** EC2 instance, one dedicated Security Group and one registered **existing local SSH public key** as an EC2 Key Pair. The Security Group and Key Pair already existed before the final apply and were **no-op**; no new private SSH key was generated.
- Instance: 30 GB encrypted gp3 root EBS, instance detailed monitoring disabled, required IMDSv2. EC2 termination protection and Terraform prevent_destroy are enabled. Root EBS is kept even on termination, although termination is explicitly forbidden until separate approval.
- Network: SSH 22 restricted to a validated trusted IPv4/32, public HTTP 80 only for Nginx-proxied anonymous GET/HEAD schema and catalog, neither Gunicorn port 8000 nor MySQL 3306 exposed. All POST/PATCH/DELETE, JWT and passwords must pass through SSH local port forwarding, not HTTP.
- Excluded: RDS, ALB, NAT Gateway, Elastic IP, S3, new IAM users/credentials, DNS purchases, Terraform remote state, auto-Terminate, old AWS infrastructure.

The normal local Compose remains unchanged. The separate compose.aws.yml runs MySQL 8.4, Django/Gunicorn and Nginx; MySQL data live on a persistent Docker volume on root EBS. Docker services use restart unless-stopped for Stop/Start recovery.

## Historical Terraform preflight (already completed; do not rerun for deployment)

From this Terraform folder, after confirming the actual AWS account and current workstation public IPv4:

1. Export TF_VAR_admin_cidr as the approved IPv4 address with /32 suffix. Export TF_VAR_ssh_public_key_path as the absolute filename of an already existing .pub file, never a private key. Do not commit variables containing local network details.
2. Run the following checks:

    terraform fmt -check
    terraform init -reconfigure -input=false
    terraform validate
    terraform plan -input=false -refresh=true -out=preflight.tfplan
    terraform show -json preflight.tfplan

3. Expect exactly three additions, no replacements and no removals. Inspect chosen AMI, default VPC/subnet, SSH source, public key name, enabled protections and EBS properties. Confirm no secrets in state and no edits to old state files.
4. **STOP before terraform apply.** Review actual Billing, credits, eligibility, data transfer costs, the exact plan and a hard spending budget with the owner. An earlier agreement to use Stop/Start is not consent to incur expenses.

Terraform provider downloads during init are local. Plan and provider reads do not create AWS resources. State, plan and variable files are explicitly ignored by Git.

## Deployment continuation — the existing STOPPED EC2, no new Terraform apply

1. Read current Git/second-brain checkpoints and the ignored local Terraform state. Verify AWS profile `docker-course`, region `eu-north-1`, account, exact original instance, Security Group SSH /32, budget and remaining credits. Start **only the existing stopped EC2** and confirm the new dynamic public IP, instance health and trusted SSH host key. **Do not run Terraform apply, create another EC2 or replace the existing SSH key.**
2. SSH with the matching pre-existing private key. Docker Engine 29.10.0 and Compose v5.8.0 are **already installed and verified**, and user `ubuntu` belongs to the remote Docker group. The tracked Django code is already present in `/home/ubuntu/lms271` (source commit `69533da`); do not replace the source with unreviewed changes, install Docker again or copy Mac secrets/state.
3. The remote private environment file `/home/ubuntu/lms271/.env.aws` already exists (mode 0600). Safely update **only `DJANGO_ALLOWED_HOSTS`** with the actual current EC2 public IP if it changed, preserving the previously generated `DJANGO_SECRET_KEY`, `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD`, `MYSQL_DATABASE` and `MYSQL_USER`. Never print its values or store it in Git/logs.
4. From the existing project root on EC2 run, without `sudo`:

    cd /home/ubuntu/lms271
    docker compose --env-file .env.aws -f infra/aws-ec2-r25/compose.aws.yml config --quiet
    docker compose --env-file .env.aws -f infra/aws-ec2-r25/compose.aws.yml up -d --build
    docker compose --env-file .env.aws -f infra/aws-ec2-r25/compose.aws.yml ps

5. Confirm MySQL 8.4, completed Django migrations, DEBUG=False, ALLOWED_HOSTS, healthy Gunicorn and containers, and no externally published 3306 or 8000. Check Nginx public GET /api/schema/ and GET /api/listings/ (expected HTTP 200). Confirm public POST is rejected.
6. For authentication and Postman use an SSH tunnel on Mac with the matching identity, forwarding local port 28765 to EC2 loopback 18765:

    ssh -N -L 28765:127.0.0.1:18765 -i ~/.ssh/id_ed25519 ubuntu@<CURRENT_EC2_PUBLIC_IP>

   Postman base URL through this protected tunnel is http://127.0.0.1:28765. Do not send access/refresh tokens or passwords through publicly accessible HTTP. Use only synthetic Tenant/Landlord credentials and data for bookings, conflicts, cancellation, completed stays, reviews, permissions and statistics.
7. Save dated evidence: EC2/Ubuntu/Docker/Python/Django/MySQL/Gunicorn versions, Git SHA, migrations, HTTP codes, real API assertions, public IP at test time, and timestamped AWS costs/credits. Do not save secrets or real account identifiers.

## Stop/Start and defense on 11.12.2026

- After a successful initial smoke test: verify MySQL data and Docker volume; issue AWS CLI stop-instances for the exact EC2 instance with --profile docker-course --region eu-north-1. Verify state stopped; verify the root EBS still exists and is attached. The service is offline while stopped.
- When stopped, EC2 computation ceases accruing hourly charges, but EBS storage may continue to use credits. The auto-assigned public IPv4 is released, and the next Start may receive a different one.
- Before the 11 December defense: issue start-instances for **the same EC2**, verify running, get its current public IP, update the remote private .env.aws DJANGO_ALLOWED_HOSTS as necessary, recreate only web if needed, verify Docker service, MySQL volume/healthcheck, Gunicorn, public GET 200 and a synthetic authenticated SSH-tunnel Postman flow. If the Mac public IP changed, a separately reviewed change of the dedicated SG /32 may be required.
- After defense: Stop EC2, verify EBS retention, no other running chargeable resources and Billing/credits. The infrastructure is **not** destroyed automatically. Leaving 30 GB EBS stopped costs approximately $2.51 per month at the historical Stockholm rate.
- If teacher feedback requires code changes, update only the existing VM; preserve its MySQL volume, make a backup before migrations, rerun MySQL/API checks and Stop when finished.
- No terraform destroy, EC2 Terminate, EBS removal, docker compose down --volumes, or changes to unrelated AWS resources without separate permission.

## Cost estimate (not a promise of free service)

Historical official AWS Stockholm list rates verified on 19.11.2026: **m7i-flex.large Linux $0.10175/hour**, gp3 about **$0.0836/GB-month**, in-use public IPv4 **$0.005/hour**. Eight total compute hours plus 30 GB EBS for approximately 22 days suggest **about $2.67** before extra transfer, tax, backup, delays, previous usage and other charges. AWS credits do not guarantee no charges.

User-provided AWS Settings panel on 19.11 showed $0 billed, $120 credits and Free Plan until 04.04.2027. Credits and the Free Plan do not guarantee zero financial exposure. Check current prices and account-specific eligibility before requesting apply permission. Never activate other cloud services or upgrade the plan without explicit authorization.
