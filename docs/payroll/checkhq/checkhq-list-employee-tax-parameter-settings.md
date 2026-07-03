> ## Documentation Index
> Fetch the complete documentation index at: https://docs.checkhq.com/llms.txt
> Use this file to discover all available pages before exploring further.

# List an employee's tax parameter settings

Get a paginated list of an employee’s tax parameter details which include a list of effective dated values

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
    "/employee_tax_params/{employee_id}/settings": {
      "get": {
        "summary": "List an employee's tax parameter settings",
        "description": "Get a paginated list of an employee’s tax parameter details which include a list of effective dated values",
        "operationId": "list-employee-tax-parameter-settings",
        "parameters": [
          {
            "name": "employee_id",
            "in": "path",
            "description": "ID of the employee used to list the applicable tax parameter details.",
            "schema": {
              "type": "string"
            },
            "required": true
          },
          {
            "name": "as_of",
            "in": "query",
            "description": "Used to show the list of tax parameter with the list of effective dated details.",
            "schema": {
              "type": "string",
              "format": "date"
            }
          },
          {
            "name": "jurisdiction",
            "in": "query",
            "description": "Used to further filter down the list of the employee’s tax parameter details to specific jurisdictions.",
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
                    "value": "{\n  \"next\": null,\n  \"previous\": null,\n  \"results\": [\n    {\n      \"id\": \"spa_yqVxHQZb7aVPHrh16HRq\",\n      \"jurisdiction\": \"jur_mRpDYFyFSUD1ArZdrMis\",\n      \"applied_for\": null,\n      \"value\": \"M\",\n      \"effective_start\": \"2021-03-15\",\n      \"settings\": [\n        {\n          \"value\": \"M\",\n          \"effective_start\": \"2021-03-15\"\n        },\n        {\n          \"value\": \"S\",\n          \"effective_start\": \"2020-01-01\"\n        }\n      ]\n    },\n    ...,\n  ]\n}"
                  }
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