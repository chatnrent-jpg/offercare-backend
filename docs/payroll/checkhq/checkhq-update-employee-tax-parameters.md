> ## Documentation Index
> Fetch the complete documentation index at: https://docs.checkhq.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Update an employee's tax parameter

Update a list of one or more tax parameters belonging to the employee

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
    "/employee_tax_params/{employee_id}": {
      "patch": {
        "summary": "Update an employee's tax parameter",
        "description": "Update a list of one or more tax parameters belonging to the employee",
        "operationId": "update-employee-tax-parameters",
        "parameters": [
          {
            "name": "employee_id",
            "in": "path",
            "description": "ID of the employee used to update the applicable tax parameter.",
            "schema": {
              "type": "string"
            },
            "required": true
          }
        ],
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "RAW_BODY": {
                    "type": "array",
                    "description": "List of tax param update objects",
                    "items": {
                      "properties": {
                        "id": {
                          "type": "string",
                          "description": "ID of the tax parameter that will be updated."
                        },
                        "applied_for": {
                          "type": "boolean",
                          "description": "(Optional) Indicates whether the setting was marked as applied for."
                        },
                        "value": {
                          "type": "string",
                          "description": "(Optional) The value of the setting."
                        },
                        "effective_start": {
                          "type": "string",
                          "description": "(Optional) Date representing when the supplied value will start being effective.",
                          "format": "date"
                        }
                      },
                      "required": [
                        "id"
                      ],
                      "type": "object"
                    }
                  }
                }
              },
              "examples": {
                "Request Example": {
                  "value": [
                    {
                      "id": "spa_123456789",
                      "value": "1.25",
                      "effective_start": "2021-01-01"
                    }
                  ]
                }
              }
            }
          }
        },
        "responses": {
          "200": {
            "description": "200",
            "content": {
              "application/json": {
                "examples": {
                  "Result": {
                    "value": "{\n  \"next\": null,\n  \"previous\": null,\n  \"results\": [\n    {\n      \"id\": \"spa_yqVxHQZb7aVPHrh16HRq\",\n      \"label\": \"Filing status\",\n      \"description\": \"Filing status\",\n      \"name\": \"filing_status\",\n      \"type\": \"select\",\n      \"options\": [\n        {\n          \"label\": \"Married but withholding at higher single rate\",\n          \"value\": \"MH\"\n        },\n        {\n          \"label\": \"Non-resident alien\",\n          \"value\": \"NRA\"\n        },\n        {\n          \"label\": \"Married\",\n          \"value\": \"M\"\n        },\n        {\n          \"label\": \"Single\",\n          \"value\": \"S\"\n        }\n      ],\n      \"depends_on\": null,\n      \"editable\": true,\n      \"effective_datable\": true,\n      \"can_be_applied_for\": false,\n      \"jurisdiction\": \"jur_mRpDYFyFSUD1ArZdrMis\",\n      \"tax\": \"tax_afRJqY785WwYH0PrtFde\",\n      \"setting\": {\n        \"applied_for\": null,\n        \"value\": \"M\",\n        \"effective_start\": \"2021-03-15\"\n      }\n    },\n    ...,\n  ]\n}"
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