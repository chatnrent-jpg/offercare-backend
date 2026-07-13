# 1. Security Group for Public Ingress (Application Load Balancer Layer)
resource "aws_security_group" "alb_sg" {
  name        = "vettedme-prod-alb-sg"
  description = "Enforces isolated HTTP/HTTPS intake boundaries"
  vpc_id      = aws_vpc.vettedme_prod_vpc.id

  ingress {
    description = "Allow production HTTPS entry"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Allow production HTTP entry"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Allow all outbound traffic for proxying"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "vettedme-prod-alb-sg"
  }
}

# 2. Security Group for the Backend Computing Environment
resource "aws_security_group" "backend_sg" {
  name        = "vettedme-prod-backend-sg"
  description = "Restricts compute access exclusively to the load balancer"
  vpc_id      = aws_vpc.vettedme_prod_vpc.id

  ingress {
    description     = "Only allow ingress directly from the load balancer"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb_sg.id]
  }

  egress {
    description = "Allow computed outbound data traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "vettedme-prod-backend-sg"
  }
}

# 3. Security Group for Hidden Database Pool
resource "aws_security_group" "db_sg" {
  name        = "vettedme-prod-db-sg"
  description = "Isolates PostgreSQL pgvector storage inside the private network"
  vpc_id      = aws_vpc.vettedme_prod_vpc.id

  ingress {
    description     = "Only accept database queries from our application runtime"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.backend_sg.id]
  }

  egress {
    description = "Block database external output lines"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [aws_vpc.vettedme_prod_vpc.cidr_block]
  }

  tags = {
    Name = "vettedme-prod-db-sg"
  }
}
