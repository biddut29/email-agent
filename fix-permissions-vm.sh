#!/bin/bash

# Fix permissions for email-agent deployment
# This script fixes the permission issues on the VM

set -e

echo "🔧 Fixing permissions for /opt/email-agent..."

# Change ownership of the entire project directory
sudo chown -R $USER:$USER /opt/email-agent

# Ensure attachments directory exists and has correct permissions
mkdir -p /opt/email-agent/Backend/attachments
chmod -R 755 /opt/email-agent/Backend/attachments

# Reset git state to clean up any merge conflicts
cd /opt/email-agent
git reset --hard HEAD
git clean -fd

# Pull latest changes
git fetch origin
git checkout dev
git pull origin dev

echo "✅ Permissions fixed and repository updated!"

# Show current permissions
ls -la /opt/email-agent/Backend/ | grep attachments

