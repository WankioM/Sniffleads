#!/bin/bash
# scripts/aws-destroy.sh
# Destroys ALL AWS resources created by Terraform
# 
# WARNING: This deletes everything including your database!
# Make sure to backup any data you need first.

set -e

echo "=========================================="
echo "  SniffLeads AWS Resource Destruction"
echo "=========================================="
echo ""
echo "WARNING: This will permanently delete:"
echo "  - ECS services (web, worker, beat)"
echo "  - RDS PostgreSQL database (ALL DATA)"
echo "  - ElastiCache Redis"
echo "  - Load Balancer"
echo "  - VPC and networking"
echo "  - ECR repository and images"
echo "  - CloudWatch logs"
echo "  - Secrets Manager secrets"
echo ""
read -p "Are you sure? Type 'destroy' to confirm: " confirmation

if [ "$confirmation" != "destroy" ]; then
    echo "Aborted."
    exit 1
fi

cd "$(dirname "$0")/../infra/terraform"

echo ""
echo "Step 1: Checking Terraform state..."
terraform init

echo ""
echo "Step 2: Planning destruction..."
terraform plan -destroy -out=destroy.tfplan

echo ""
read -p "Review the plan above. Proceed with destruction? (y/n): " proceed

if [ "$proceed" != "y" ]; then
    echo "Aborted."
    rm -f destroy.tfplan
    exit 1
fi

echo ""
echo "Step 3: Destroying resources..."
terraform apply destroy.tfplan

echo ""
echo "Step 4: Cleanup..."
rm -f destroy.tfplan

echo ""
echo "=========================================="
echo "  All AWS resources have been destroyed"
echo "=========================================="
echo ""
echo "Note: Some resources may take a few minutes to fully delete."
echo "Check AWS Console to verify everything is gone."