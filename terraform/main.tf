terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

# Latest Amazon Linux 2023 image (looked up automatically)
data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Use the account's default VPC and its subnets
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_security_group" "portal_sg" {
  name        = "portal-request-${var.request_id}-sg"
  description = "Security group for portal request ${var.request_id}"
  vpc_id      = data.aws_vpc.default.id

  # SSH is only opened when allowed_cidr is set (empty = closed)
  dynamic "ingress" {
    for_each = var.allowed_cidr == "" ? [] : [var.allowed_cidr]
    content {
      description = "SSH from allowed IP range"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = [ingress.value]
    }
  }

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project   = "ec2-portal"
    RequestId = var.request_id
  }
}

resource "aws_instance" "portal_instance" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  subnet_id              = data.aws_subnets.default.ids[0]
  vpc_security_group_ids = [aws_security_group.portal_sg.id]

  root_block_device {
    volume_size = var.storage_gb
    volume_type = "gp3"
    encrypted   = true
  }

  metadata_options {
    http_tokens   = "required"
    http_endpoint = "enabled"
  }

  tags = {
    Name      = var.instance_name != "" ? "${var.instance_name}-req${var.request_id}" : "portal-request-${var.request_id}"
    Project   = "ec2-portal"
    RequestId = var.request_id
  }
}
