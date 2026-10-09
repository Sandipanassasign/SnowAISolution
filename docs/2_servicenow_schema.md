# ServiceNow Change Request JSON Schema Reference

## API Endpoint
```
GET /api/now/table/change_request
```

## Query Parameters
| Parameter       | Value                          | Description                        |
|-----------------|--------------------------------|------------------------------------|
| `sysparm_query` | `state=Scheduled`              | Filter for scheduled CRs only     |
| `sysparm_limit` | `50`                           | Max records per request            |
| `sysparm_fields`| `number,state,short_description,description,sys_id,assigned_to,start_date,end_date` | Restrict returned fields |

## Response Shape
When querying `/api/now/table/change_request`, the API returns records in this format:

```json
{
  "result": [
    {
      "number": "CHG0034512",
      "state": "Scheduled",
      "short_description": "Deploy Release 4.2 to Production",
      "description": "This deployment impacts mail codes 45A, 99B. Needs QA sign-off from Retail Banking.",
      "sys_id": "9d385017c611228701d22104cc95c371",
      "assigned_to": {
        "link": "https://instance.service-now.com/api/now/table/sys_user/681ccaf9c0a8016400b98a06818d57c7",
        "value": "681ccaf9c0a8016400b98a06818d57c7"
      },
      "start_date": "2026-10-15 02:00:00",
      "end_date": "2026-10-15 06:00:00"
    }
  ]
}
```

## Authentication
- **Basic Auth**: Uses `SNOW_USERNAME` and `SNOW_PASSWORD` from environment.
- **OAuth**: Uses `SNOW_CLIENT_ID` and `SNOW_CLIENT_SECRET` to obtain a bearer token from `/oauth_token.do`.

## Headers
```json
{
  "Content-Type": "application/json",
  "Accept": "application/json"
}
```
