> ## Documentation Index
> Fetch the complete documentation index at: https://docs.checkhq.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Bulk update employee tax parameters

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
    "/employee_tax_params/settings": {
      "patch": {
        "summary": "Bulk update employee tax parameters",
        "description": "",
        "operationId": "bulk-update-employee-tax-parameters",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "RAW_BODY": {
                    "type": "array",
                    "description": "List of employee tax param update objects",
                    "items": {
                      "properties": {
                        "id": {
                          "type": "string",
                          "description": "ID of the tax parameter that will be updated."
                        },
                        "company": {
                          "type": "string",
                          "description": "ID of the company."
                        },
                        "employee": {
                          "type": "string",
                          "description": "ID of the employee."
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
                        "id",
                        "company",
                        "employee"
                      ],
                      "type": "object"
                    }
                  }
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