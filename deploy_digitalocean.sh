#!/bin/bash
# Digital Ocean Deployment Script for FSA Program Explorer

set -e

echo "🚀 FSA Program Explorer - Digital Ocean Deployment"
echo "==================================================="

# Check if doctl is installed
if ! command -v doctl &> /dev/null; then
    echo "❌ doctl CLI not found. Installing..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install doctl
    else
        echo "Please install doctl: https://docs.digitalocean.com/reference/doctl/how-to/install/"
        exit 1
    fi
fi

# Check authentication
if ! doctl account get &> /dev/null; then
    echo "🔐 Please authenticate with Digital Ocean..."
    echo "Run: doctl auth init"
    exit 1
fi

echo "✅ Digital Ocean CLI authenticated"

# Create the app
echo "🏗️  Creating Digital Ocean App..."
doctl apps create .do/app.yaml

echo ""
echo "✅ App created successfully!"
echo ""
echo "📝 Next Steps:"
echo "1. Get your app ID: doctl apps list"
echo "2. Monitor deployment: doctl apps logs YOUR_APP_ID --follow"
echo "3. Your app will be available at: https://fsa-program-explorer-xxxxx.ondigitalocean.app"
echo ""
echo "💡 To update the app:"
echo "   doctl apps update YOUR_APP_ID --spec .do/app.yaml"
echo ""
echo "📊 Estimated Monthly Cost: ~$12/month"
echo "   - App (basic-xxs): $5/month"
echo "   - Database (dev): $7/month"
