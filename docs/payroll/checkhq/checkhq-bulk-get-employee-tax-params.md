> ## Documentation Index
> Fetch the complete documentation index at: https://docs.checkhq.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Bulk get employee tax parameters

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
    "/employee_tax_params": {
      "get": {
        "summary": "Bulk get employee tax parameters",
        "description": "",
        "operationId": "bulk-get-employee-tax-params",
        "parameters": [
          {
            "name": "company",
            "in": "query",
            "description": "Unique ID of the company.",
            "required": true,
            "schema": {
              "type": "string"
            }
          },
          {
            "name": "as_of",
            "in": "query",
            "description": "Used to list tax parameters applicable as of the supplied date.",
            "schema": {
              "type": "string",
              "format": "date"
            }
          },
          {
            "name": "jurisdiction",
            "in": "query",
            "description": "Used to further filter down the list of the employee’s tax parameters to specific jurisdictions.",
            "schema": {
              "type": "string"
            }
          },
          {
            "name": "submitter",
            "in": "query",
            "description": "Filter by submitter type. Can be `employee` or `company`.",
            "schema": {
              "type": "string"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "200",
            "content": {
              "application/json": {
                "examples": {
                  "Result": {
                    "value": "{}"
                  }
                },
                "schema": {
                  "type": "object",
                  "properties": {}
                }
              }
            }
          },
          "400": {
            "description": "400",
            "content": {
              "application/json": {
                "examples": {
                  "Result": {
                    "value": "{}"
                  }
                },
                "schema": {
                  "type": "object",
                  "properties": {}
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