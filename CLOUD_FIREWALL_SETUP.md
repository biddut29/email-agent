# Cloud Firewall Setup Guide

If you're getting `ERR_CONNECTION_TIMED_OUT` when accessing `http://74.242.217.91:3000/`, your cloud provider's firewall is blocking inbound traffic.

## Quick Fix

You need to open ports **3000** and **8000** in your cloud provider's firewall/security group.

---

## Azure VM Setup

1. **Go to Azure Portal** → Navigate to your Virtual Machine
2. **Click "Networking"** in the left menu
3. **Click "Add inbound port rule"**
4. **Add these rules:**

   | Port | Protocol | Priority | Source | Action |
   |------|----------|----------|--------|--------|
   | 3000 | TCP | 1000 | Any | Allow |
   | 8000 | TCP | 1001 | Any | Allow |
   | 22 | TCP | 1002 | Any | Allow (for SSH) |

5. **Save** the rules
6. **Wait 1-2 minutes** for rules to propagate
7. **Test**: `http://74.242.217.91:3000/`

---

## AWS EC2 Setup

1. **Go to AWS Console** → EC2 → Instances
2. **Select your instance** → Click "Security" tab
3. **Click the Security Group** link
4. **Click "Edit inbound rules"**
5. **Click "Add rule"** and add:

   | Type | Protocol | Port Range | Source |
   |------|----------|------------|--------|
   | Custom TCP | TCP | 3000 | 0.0.0.0/0 |
   | Custom TCP | TCP | 8000 | 0.0.0.0/0 |
   | SSH | TCP | 22 | 0.0.0.0/0 (optional) |

6. **Save rules**
7. **Test**: `http://74.242.217.91:3000/`

---

## Google Cloud Platform (GCP) Setup

1. **Go to GCP Console** → VPC Network → Firewall
2. **Click "Create Firewall Rule"**
3. **Configure:**
   - **Name**: `allow-email-agent-ports`
   - **Direction**: Ingress
   - **Targets**: All instances in the network
   - **Source IP ranges**: `0.0.0.0/0`
   - **Protocols and ports**: 
     - ☑ TCP
     - Ports: `3000,8000,22`
4. **Create** the rule
5. **Test**: `http://74.242.217.91:3000/`

---

## Verify Services Are Running

After opening firewall ports, verify services are accessible:

```bash
# From your local machine
curl -I http://74.242.217.91:3000
curl -I http://74.242.217.91:8000/api/health
```

If you still get timeouts after opening firewall ports, check:
1. Services are actually running (check CI/CD logs)
2. Docker containers are up: `sudo docker-compose -f docker-compose.dev.yml ps`
3. Ports are listening: `sudo ss -tlnp | grep -E ':(3000|8000)'`

---

## Security Note

⚠️ **For production**, consider:
- Restricting source IPs instead of `0.0.0.0/0`
- Using a reverse proxy (Nginx) on port 80/443
- Setting up SSL/TLS certificates
- Using a load balancer

For development, allowing `0.0.0.0/0` is acceptable.

