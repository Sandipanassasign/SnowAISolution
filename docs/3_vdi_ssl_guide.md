# VDI SSL Troubleshooting Guide

## The Problem
In a banking VDI environment, enterprise packet inspection appliances (Zscaler, BlueCoat, etc.) re-sign TLS certificates with an internal CA. Python's `certifi` bundle doesn't include this CA, causing:

```
ssl.SSLCertificateVerifyError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate
```

## Solutions (In Order of Preference)

### 1. Export and Use the Enterprise CA Bundle (Recommended)
```bash
# Export the enterprise root CA from your browser (Settings → Certificates → Export as .pem)
# Place it at a known path, e.g.:
export SSL_CERT_FILE=/path/to/enterprise-ca-bundle.pem
export REQUESTS_CA_BUNDLE=/path/to/enterprise-ca-bundle.pem
```

Add these to your `.env` file so the application picks them up automatically.

### 2. Append Enterprise CA to Python's certifi Bundle
```python
import certifi
print(certifi.where())
# → /path/to/venv/lib/python3.10/site-packages/certifi/cacert.pem

# Append your enterprise CA:
# cat enterprise-root-ca.pem >> $(python -c "import certifi; print(certifi.where())")
```

### 3. Bypass SSL Verification (Local Dev ONLY)
Set in your `.env` file:
```
DISABLE_SSL_VERIFY=true
```

This application will automatically:
- Set `verify=False` on all `requests` calls
- Suppress `InsecureRequestWarning` from urllib3
- Configure the `httpx` client for LlamaIndex with `verify=False`

> ⚠️ **Never** deploy to production with SSL verification disabled.

## Configuring LlamaIndex Specifically

The `llm_extractor.py` module handles this automatically by building a custom `httpx.Client`:

```python
import httpx

# With custom CA:
http_client = httpx.Client(verify="/path/to/enterprise-ca-bundle.pem")

# Without verification (dev only):
http_client = httpx.Client(verify=False)

# Pass to LlamaIndex:
llm = OpenAILike(
    model="claude-opus-4-20250514",
    api_key=api_key,
    api_base=api_base,
    http_client=http_client,
)
```

## Configuring `requests` Library

The `snow_client.py` module handles this automatically via `session.verify`:

```python
import requests
session = requests.Session()
session.verify = "/path/to/enterprise-ca-bundle.pem"  # or False for dev
```

## Proxy Configuration
If your VDI routes through an HTTP proxy:
```
HTTP_PROXY=http://proxy.internal.bank.com:8080
HTTPS_PROXY=http://proxy.internal.bank.com:8080
```
