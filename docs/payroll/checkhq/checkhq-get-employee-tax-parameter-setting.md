> ## Documentation Index
> Fetch the complete documentation index at: https://docs.checkhq.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Get a specific employee's tax parameter setting

Get an employee’s tax parameter detail which includes a list of effective dated values

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
    "/employee_tax_params/{employee_id}/settings/{tax_param_id}": {
      "get": {
        "summary": "Get a specific employee's tax parameter setting",
        "description": "Get an employee’s tax parameter detail which includes a list of effective dated values",
        "operationId": "get-employee-tax-parameter-setting",
        "parameters": [
          {
            "name": "employee_id",
            "in": "path",
            "description": "ID of the employee used to get the applicable tax parameter details.",
            "schema": {
              "type": "string"
            },
            "required": true
          },
          {
            "name": "tax_param_id",
            "in": "path",
            "description": "ID of the tax parameter used to detail the values.",
            "schema": {
              "type": "string"
            },
            "required": true
          },
          {
            "name": "as_of",
            "in": "query",
            "description": "Used to show the tax parameter’s effective dated details.",
            "schema": {
              "type": "string",
              "format": "date"
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
                    "value": "{\n  \"id\": \"spa_yqVxHQZb7aVPHrh16HRq\",\n  \"jurisdiction\": \"jur_mRpDYFyFSUD1ArZdrMis\",\n  \"applied_for\": null,\n  \"value\": \"M\",\n  \"effective_start\": \"2021-03-15\",\n  \"settings\": [\n    {\n      \"value\": \"M\",\n      \"effective_start\": \"2021-03-15\"\n    },\n    {\n      \"value\": \"S\",\n      \"effective_start\": \"2020-01-01\"\n    }\n  ]\n}"
                  }
                },
                "schema": {
                  "type": "object",
                  "properties": {
                    "id": {
                      "type": "string",
                      "example": "spa_yqVxHQZb7aVPHrh16HRq"
                    },
                    "jurisdiction": {
                      "type": "string",
                      "example": "jur_mRpDYFyFSUD1ArZdrMis"
                    },
                    "applied_for": {},
                    "value": {
                      "type": "string",
                      "example": "M"
                    },
                    "effective_start": {
                      "type": "string",
                      "example": "2021-03-15"
                    },
                    "settings": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "value": {
                            "type": "string",
                            "example": "M"
                          },
                          "effective_start": {
                            "type": "string",
                            "example": "2021-03-15"
                          }
                        }
                      }
                    }
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