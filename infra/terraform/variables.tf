# infra/terraform/variables.tf

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "sniffleads"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "dev"  # Using dev for cost savings
  
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

# Database
variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"  # Free tier eligible, ~$15/mo after
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "sniffleads"
}

variable "db_username" {
  description = "Database username"
  type        = string
  default     = "sniffleads"
  sensitive   = true
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

# Redis
variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.micro"  # Free tier eligible
}

# Application
variable "django_secret_key" {
  description = "Django SECRET_KEY"
  type        = string
  sensitive   = true
}

# ECS - Cost optimized for dev
variable "use_fargate_spot" {
  description = "Use Fargate Spot for 70% cost savings (can be interrupted)"
  type        = bool
  default     = true  # Enabled for cost savings
}

variable "web_cpu" {
  description = "CPU units for web task (256, 512, 1024, 2048, 4096)"
  type        = number
  default     = 256  # Minimum, sufficient for low traffic
}

variable "web_memory" {
  description = "Memory for web task (MB)"
  type        = number
  default     = 512  # Minimum for 256 CPU
}

variable "worker_cpu" {
  description = "CPU units for worker task"
  type        = number
  default     = 256  # Crawling is I/O bound, not CPU bound
}

variable "worker_memory" {
  description = "Memory for worker task (MB)"
  type        = number
  default     = 512
}

variable "web_desired_count" {
  description = "Desired number of web tasks"
  type        = number
  default     = 1  # Single instance for dev
}

variable "worker_desired_count" {
  description = "Desired number of worker tasks"
  type        = number
  default     = 1  # Single worker for dev
}

# Networking - Cost optimized
variable "single_nat_gateway" {
  description = "Use single NAT gateway (saves ~$30/mo but less redundant)"
  type        = bool
  default     = true  # Enabled for cost savings
}

# Backup settings
variable "backup_retention_days" {
  description = "Days to retain RDS backups"
  type        = number
  default     = 1  # Minimum for dev, increase for prod
}

variable "skip_final_snapshot" {
  description = "Skip final DB snapshot on destroy (set false for prod)"
  type        = bool
  default     = true  # Skip for easy cleanup in dev
}