# Bird Feeder Data Infrastructure

This repository contains the data infrastructure setup for the Bird Feeder project, including Grafana for visualization and Kafka for data streaming.

## Overview

The infrastructure uses Docker Compose to run Grafana locally with provisioned dashboards and datasources for monitoring bird feeder metrics.

## Prerequisites

- Docker and Docker Compose installed
- Access to Aiven Kafka instance (certificates required)

## Getting Started

### 1. Start Grafana

```bash
docker-compose up -d
```

This will start Grafana on [http://localhost:3000](http://localhost:3000)

Default credentials:
- Username: `admin`
- Password: `admin` (you'll be prompted to change this on first login)

### 2. Connecting Aiven Kafka to Local Grafana

The Kafka datasource is automatically provisioned when Grafana starts. The configuration includes:

#### Certificate Setup

Place your Aiven Kafka certificates in the [`certs/`](certs/) directory:
- `ca.pem` - Certificate Authority certificate
- `service.cert` - Client certificate
- `service.key` - Client private key

These certificates are mounted as read-only into the Grafana container at `/etc/grafana/certs/`.

#### Datasource Configuration

The Kafka datasource is configured in [`provisioning/datasources/kafka.yml`](provisioning/datasources/kafka.yml) with:

- **Bootstrap Servers**: Your Aiven Kafka service endpoint
- **Security Protocol**: SSL/TLS
- **Certificates**: CA cert, client cert, and client key for authentication

To update the Kafka connection details:

1. Edit [`provisioning/datasources/kafka.yml`](provisioning/datasources/kafka.yml)
2. Update the `bootstrapServers` and `serverName` fields with your Kafka instance details
3. Update the certificate values in `secureJsonData` section
4. Restart Grafana: `docker-compose restart`

#### Installed Plugins

The setup automatically installs the Kafka datasource plugin (`hamedkarbasi93-kafka-datasource`) for Grafana.

### 3. Dashboards

Dashboards are automatically provisioned from the [`provisioning/dashboards/`](provisioning/dashboards/) directory:

- **Bird Weight Dashboard**: Visualizes bird weight measurements over time

To add new dashboards:
1. Create or export a dashboard JSON file
2. Place it in [`provisioning/dashboards/`](provisioning/dashboards/)
3. Restart Grafana: `docker-compose restart`

## Directory Structure

```
data-infrastructure/
├── docker-compose.yml           # Docker Compose configuration
├── certs/                       # Kafka SSL certificates (not in git)
│   ├── ca.pem
│   ├── service.cert
│   └── service.key
└── provisioning/
    ├── dashboards/              # Grafana dashboard definitions
    │   └── bird-weight.json
    └── datasources/             # Grafana datasource configurations
        └── kafka.yml
```

## Managing the Stack

### Start services
```bash
docker-compose up -d
```

### Stop services
```bash
docker-compose down
```

### View logs
```bash
docker-compose logs -f grafana
```

### Restart after configuration changes
```bash
docker-compose restart
```

## TODO: Kafka Deployment

The following Kafka infrastructure setup tasks are pending until the Aiven free tier is released:

- [ ] Terraform configuration for Aiven Kafka service provisioning
- [ ] Automated certificate management and rotation
- [ ] Topic creation and configuration
- [ ] Schema registry setup
- [ ] Consumer group management
- [ ] Monitoring and alerting for Kafka metrics
- [ ] Backup and disaster recovery procedures
- [ ] Documentation for Kafka producer integration

## Troubleshooting

### Grafana doesn't start
- Check if port 3000 is already in use: `lsof -i :3000`
- Check Docker logs: `docker-compose logs grafana`

### Kafka datasource not working
- Verify certificates are in the [`certs/`](certs/) directory
- Ensure certificate permissions are correct (private key should be readable)
- Check Kafka connection details in [`provisioning/datasources/kafka.yml`](provisioning/datasources/kafka.yml)
- Verify network connectivity to Aiven Kafka endpoint

### Dashboard not appearing
- Ensure dashboard JSON is valid
- Check Grafana logs for provisioning errors
- Verify dashboard is in [`provisioning/dashboards/`](provisioning/dashboards/) directory
