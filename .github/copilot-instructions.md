# Global Project Constraints: ServiceNow AI Automation

## Environment Constraints
- We are operating in a restricted Banking VDI environment.
- Do NOT use standard `pip install` commands without referencing our internal Artifactory/Nexus proxy flags.
- All HTTP requests (especially to ServiceNow and LLM endpoints) must account for custom enterprise SSL certificates (e.g., passing `verify=False` during local dev or pointing to a custom `.pem` cert bundle).
- Never hardcode credentials. Always utilize `python-dotenv` and environment variables for ServiceNow client IDs, secrets, and API keys.

## Architectural Standards
- Framework: Python 3.10+ using LlamaIndex for orchestration.
- Integration: ServiceNow Table API via `requests` library.
- Parsing: Pydantic `BaseModel` for structured data extraction from LLM outputs.
- Logging: Use Python's native `logging` module. Print statements are forbidden. All errors must log the raw HTTP payload.

## Dependency Installation
When installing packages, always use the internal proxy:
```bash
pip install --index-url https://artifactory.internal.bank.com/api/pypi/pypi-remote/simple --trusted-host artifactory.internal.bank.com <package-name>
```

## SSL Configuration
- For local VDI development, set `REQUESTS_CA_BUNDLE` or `SSL_CERT_FILE` environment variables to point to the enterprise `.pem` bundle.
- As a fallback during local testing only, `verify=False` may be used with appropriate `urllib3` warning suppression.
- Production code must ALWAYS use proper certificate verification.
