Want to run your own private gallery? Follow these steps.

## Prerequisites

- Cloudflare account (free tier works)
- Cloudflare Images subscription ($5/month for 100k images)
- Node.js 18+ installed

1. Enable Cloudflare Images

Log in to Cloudflare Dashboard
Navigate to Images in sidebar
Click Subscribe to Cloudflare Images ($5/month)
Note your Account Hash (8-character code shown on Images page)

2. Create API Token

Go to API Tokens
Click Create Token
Use template Edit Cloudflare Images
Set permissions:

Account → Cloudflare Images → Edit


Click Continue to summary → Create Token
Copy the token (shown only once!)

3. Get Account ID

In Cloudflare Dashboard → any domain → sidebar shows Account ID
Or: Workers & Pages → Overview → Account ID on right side
Copy the Account ID

4. Install and Configure

```bash
cd cloudflare-worker

# Install dependencies
npm install

# Login to Cloudflare
npx wrangler login
```

5. Set Secrets

```bash
# Set Images API token
npx wrangler secret put IMAGES_API_TOKEN
# Paste your token when prompted

# Set Account ID
npx wrangler secret put CLOUDFLARE_ACCOUNT_ID
# Paste your account ID

# Set Account Hash (from Images dashboard)
npx wrangler secret put CLOUDFLARE_ACCOUNT_HASH
# Paste your 8-character hash
```
Verify secrets are set:

```bash
npx wrangler secret list
```

Should show:

```bash
IMAGES_API_TOKEN
CLOUDFLARE_ACCOUNT_ID
CLOUDFLARE_ACCOUNT_HASH
```

6. Deploy

```bash
npx wrangler deploy
```

Output will show your worker URL:

```bash
Deployed bird-upload-api triggers (4.13 sec)
  https://bird-upload-api.YOUR-SUBDOMAIN.workers.dev
```

7. Update Bird Feeder Config
Copy your worker URL to the bird feeder's .env:

```bash
UPLOAD_SERVICE_URL=https://bird-upload-api.YOUR-SUBDOMAIN.workers.dev
```
