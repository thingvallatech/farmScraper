# Deployment Guide - FSA Program Explorer

## Quick Start Deployment to Digital Ocean

### Prerequisites
1. Digital Ocean account
2. GitHub account with this repository
3. `doctl` CLI installed

### Deployment Steps

1. **Install doctl** (if not already installed):
```bash
# macOS
brew install doctl

# Linux
cd ~ && wget https://github.com/digitalocean/doctl/releases/download/v1.104.0/doctl-1.104.0-linux-amd64.tar.gz
tar xf ~/doctl-1.104.0-linux-amd64.tar.gz
sudo mv ~/doctl /usr/local/bin
```

2. **Authenticate with Digital Ocean**:
```bash
doctl auth init
# Enter your API token from: https://cloud.digitalocean.com/account/api/tokens
```

3. **Update the app configuration**:
Edit `.do/app.yaml` and replace `YOUR_GITHUB_USERNAME` with your GitHub username.

4. **Run the deployment script**:
```bash
./deploy_digitalocean.sh
```

5. **Monitor deployment**:
```bash
# Get your app ID
doctl apps list

# Watch logs
doctl apps logs YOUR_APP_ID --follow
```

### Database Migration

After deployment, you need to migrate your local database to Digital Ocean:

1. **Export local database**:
```bash
pg_dump -h localhost -p 5433 -U farm_user -d farm_scraper > farm_scraper_dump.sql
```

2. **Get Digital Ocean database connection**:
```bash
doctl apps list
doctl apps get YOUR_APP_ID --format json | jq '.spec.databases[0]'
```

3. **Import to Digital Ocean database**:
```bash
# Get database URL from Digital Ocean console
psql "YOUR_DATABASE_URL" < farm_scraper_dump.sql
```

### Manual Deployment (without script)

1. Create app:
```bash
doctl apps create .do/app.yaml
```

2. Update app:
```bash
doctl apps update YOUR_APP_ID --spec .do/app.yaml
```

3. Create deployment:
```bash
doctl apps create-deployment YOUR_APP_ID
```

### Estimated Costs

- **Basic Plan**: ~$12/month
  - Web app (basic-xxs): $5/month  
  - PostgreSQL database (dev): $7/month

- **Production Plan**: ~$30/month
  - Web app (basic-xs): $12/month
  - PostgreSQL database (basic): $15/month
  - Backups: $3/month

### Environment Variables

The app automatically connects to the managed PostgreSQL database via `${db.DATABASE_URL}`.

### Health Checks

The app includes a `/health` endpoint that checks:
- Application status
- Database connectivity

### Troubleshooting

**Build fails**:
```bash
doctl apps logs YOUR_APP_ID --type build
```

**Runtime errors**:
```bash
doctl apps logs YOUR_APP_ID --type run
```

**Database connection issues**:
```bash
# Check database URL is set correctly
doctl apps get YOUR_APP_ID --format json | jq '.spec.services[0].envs'
```

### Updating the Application

1. Push changes to GitHub (main branch)
2. Digital Ocean will automatically deploy if `deploy_on_push: true`

Or manually trigger:
```bash
doctl apps create-deployment YOUR_APP_ID
```

### Useful Commands

```bash
# List all apps
doctl apps list

# Get app details
doctl apps get YOUR_APP_ID

# View logs
doctl apps logs YOUR_APP_ID --follow

# List deployments
doctl apps list-deployments YOUR_APP_ID

# Delete app (careful!)
doctl apps delete YOUR_APP_ID
```

### Next Steps

1. Set up custom domain (optional)
2. Configure HTTPS (automatic with Digital Ocean)
3. Set up monitoring and alerts
4. Schedule regular database backups

## Support

For Digital Ocean specific issues, see:
- [Digital Ocean App Platform Docs](https://docs.digitalocean.com/products/app-platform/)
- [doctl CLI Reference](https://docs.digitalocean.com/reference/doctl/)
