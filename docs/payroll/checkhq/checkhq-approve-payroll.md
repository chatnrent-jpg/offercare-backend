> ## Documentation Index
> Fetch the complete documentation index at: https://docs.checkhq.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Approve a payroll

Approves a payroll.

The payroll must have a completed preview (indicated by a `preview.status` of `succeeded`) before it can be approved.

```json
{
  ...,
  "preview": {
    "status": "succeeded",
    "started_at": "2019-06-29T18:26:56.848920Z"
  },
  ...
}
```

Approving a preview approves the most recent preview of the payroll and moves the payroll status to `pending`, and the payroll must be reopened before it can be further modified.

# OpenAPI definition

```json
{
  "openapi": "3.1.0",
  "info": {
    "title": "check-api",
    "version": "2025-01-01"
  },
  "servers": [
    {
      "url": "https://sandbox.checkhq.com"
    }
  ],
  "components": {
    "securitySchemes": {
      "sec0": {
        "type": "apiKey",
        "in": "header",
        "name": "Authorization",
        "x-bearer-format": "bearer",
        "x-default": "YOUR_API_KEY"
      }
    }
  },
  "security": [
    {
      "sec0": []
    }
  ],
  "paths": {
    "/payrolls/{payroll}/approve": {
      "post": {
        "summary": "Approve a payroll",
        "description": "Approves a payroll.",
        "operationId": "approve-payroll",
        "parameters": [
          {
            "name": "payroll",
            "in": "path",
            "schema": {
              "type": "string"
            },
            "required": true
          }
        ],
        "responses": {
          "200": {
            "description": "200",
            "content": {
              "application/json": {
                "examples": {
                  "Result": {
                    "value": ""
                  }
                }
              }
            }
          }
        },
        "deprecated": false
      }
    }
  },
  "x-readme": {
    "headers": [],
    "explorer-enabled": true,
    "proxy-enabled": true
  },
  "x-readme-fauxas": true
}
```