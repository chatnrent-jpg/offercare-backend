# 1. Private Database Subnet Mapping Group
resource "aws_db_subnet_group" "db_subnet_group" {
  name       = "vettedcare-prod-db-subnet-group"
  subnet_ids = [aws_subnet.private_subnet_1.id]

  tags = {
    Name = "vettedcare-prod-db-subnet-group"
  }
}

# 2. Managed Highly Isolated PostgreSQL Database Pool (For pgvector & HNSW indexes)
resource "aws_db_instance" "prod_postgres" {
  allocated_storage      = 50
  max_allocated_storage  = 500
  engine                 = "postgres"
  engine_version         = "15.7" # Production enterprise-certified build supporting pgvector 0.5.x+
  instance_class         = "db.r7g.xlarge" # Memory-optimized ARM instance group tailored for vector processing memory loads
  db_name                = "offercare_db"
  username               = "postgres"
  password               = "TEMPORARY_BOOTSTRAP_PASSWORD_REPLACED_IN_TRACK_2"
  
  db_subnet_group_name   = aws_db_subnet_group.db_subnet_group.name
  vpc_security_group_ids = [aws_security_group.db_sg.id]
  skip_final_snapshot    = false
  final_snapshot_identifier = "vettedcare-prod-db-final-snapshot"
  
  storage_encrypted      = true
  deletion_protection    = true

  tags = {
    Environment = "production"
    Name        = "vettedcare-prod-database"
  }
}

# 3. High-Concurrency Compute Framework Instance
resource "aws_instance" "backend_compute" {
  ami           = "ami-0c7217cdde317cfec" # Hardened minimal Ubuntu Enterprise Server LTS base
  instance_type = "c7g.xlarge"          # Compute-optimized ARM core structure for parallel high-volume intake handling
  
  subnet_id              = aws_subnet.private_subnet_1.id
  vpc_security_group_ids = [aws_security_group.backend_sg.id]

  root_block_device {
    volume_size           = 40
    volume_type           = "gp3"
    encrypted             = true
  }

  tags = {
    Name        = "vettedcare-prod-compute-node"
    Environment = "production"
  }
}
