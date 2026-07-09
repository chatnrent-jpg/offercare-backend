provider "aws" {
  region = "us-east-1"
}

# 1. Dedicated Production VPC for VettedCare.ai
resource "aws_vpc" "vettedcare_prod_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "vettedcare-prod-vpc"
    Environment = "production"
  }
}

# 2. Public Subnet for the Application Load Balancer (ALB)
resource "aws_subnet" "public_subnet_1" {
  vpc_id            = aws_vpc.vettedcare_prod_vpc.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = "us-east-1a"
  map_public_ip_on_launch = true

  tags = {
    Name = "vettedcare-prod-public-1"
  }
}

# 3. Isolated Private Subnet Pool for PostgreSQL / pgvector Instance
resource "aws_subnet" "private_subnet_1" {
  vpc_id            = aws_vpc.vettedcare_prod_vpc.id
  cidr_block        = "10.0.10.0/24"
  availability_zone = "us-east-1a"

  tags = {
    Name = "vettedcare-prod-private-1"
  }
}

# 4. Internet Gateway for Traffic Ingress
resource "aws_internet_gateway" "prod_gw" {
  vpc_id = aws_vpc.vettedcare_prod_vpc.id

  tags = {
    Name = "vettedcare-prod-igw"
  }
}

# 5. Public Routing Fabric Configuration
resource "aws_route_table" "public_rt" {
  vpc_id = aws_vpc.vettedcare_prod_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.prod_gw.id
  }
}

resource "aws_route_table_association" "public_1_assoc" {
  subnet_id      = aws_subnet.public_subnet_1.id
  route_table_id = aws_route_table.public_rt.id
}
