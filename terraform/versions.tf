terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Local state for the capstone. For a team, use an S3 backend with locking:
  # backend "s3" { bucket = "..." key = "shelflend/terraform.tfstate" region = "ap-south-1" use_lockfile = true }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = var.project
      ManagedBy = "terraform"
      Owner     = var.owner
    }
  }
}
