# Process Flow

## Overview
This system automates the notification workflow for scheduled ServiceNow Change Requests. It polls for new CRs, extracts structured impact data using an LLM, maps stakeholders, and dispatches email notifications.

## State Machine

```
[ServiceNow CR Table] --> fetch_snow_tickets()
                              |
                              v
                     [Raw CR Records]
                              |
                              v
                     extract_impact_data()
                              |
                              v
                     [Structured Impact Data]
                              |
                              v
                     map_stakeholders()
                              |
                              v
                     [Stakeholder Email List]
                              |
                              v
                     dispatch_notification()
                              |
                              v
                     [Email Sent / Logged]
```

## Function Definitions

1. **`fetch_snow_tickets()`**: Poll the ServiceNow `change_request` table via REST API for tickets in "Scheduled" state. Uses basic auth or OAuth token. Respects VDI SSL constraints.

2. **`extract_impact_data()`**: Pass the unstructured CR description to the LLM via LlamaIndex structured outputs to extract:
   - `change_order_number` (str)
   - `mail_codes` (List[str])
   - `lob_impacted` (str)

3. **`map_stakeholders()`**: Look up the extracted LOB against a static dictionary/JSON file (`config/stakeholder_map.json`) to find the QA Lead email addresses.

4. **`dispatch_notification()`**: Send the formatted payload via internal SMTP server. Includes change order details, impacted LOBs, and mail codes in the email body.
