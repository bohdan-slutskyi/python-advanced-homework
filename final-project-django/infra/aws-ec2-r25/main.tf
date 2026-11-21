terraform {
  required_version = ">= 1.7.0, < 2.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
  backend "local" {
    path = "terraform.tfstate"
  }
}
provider "aws" {
  region  = "eu-north-1"
  profile = "docker-course"
  default_tags {
    tags = {
      Project   = "LMS271-Django-R25"
      Purpose   = "Defense-Smoke"
      RunId     = var.run_id
      ManagedBy = "Terraform"
    }
  }
}
data "aws_vpc" "default" {
  default = true
}
data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
  filter {
    name   = "state"
    values = ["available"]
  }
}
# Register an existing local PUBLIC SSH key; do not generate a private key.
resource "aws_key_pair" "deployer" {
  key_name   = "lms271-r25-${var.run_id}"
  public_key = file(pathexpand(var.ssh_public_key_path))
}
resource "aws_security_group" "django" {
  name        = "lms271-r25-${var.run_id}"
  description = "Isolated Django R25 trial; no public database or Gunicorn"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "SSH only from trusted workstation"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }
  ingress {
    description = "Read-only public HTTP reverse proxy"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    description = "Docker image and OS update downloads"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = {
    Name = "lms271-r25-${var.run_id}"
  }
}
resource "aws_instance" "django" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = "m7i-flex.large"
  subnet_id                   = sort(data.aws_subnets.default.ids)[0]
  vpc_security_group_ids      = [aws_security_group.django.id]
  key_name                    = aws_key_pair.deployer.key_name
  associate_public_ip_address = true
  monitoring                  = false
  disable_api_termination     = true

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 30
    encrypted             = true
    delete_on_termination = false
  }
  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }
  lifecycle {
    prevent_destroy = true
  }
  tags = {
    Name = "lms271-r25-${var.run_id}"
  }
}
