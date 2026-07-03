> ## Documentation Index
> Fetch the complete documentation index at: https://docs.checkhq.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Update employee tax elections

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
    "/employee_tax_elections": {
      "patch": {
        "summary": "Update employee tax elections",
        "description": "",
        "operationId": "update-employee-tax-elections",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "required": [
                  "RAW_BODY"
                ],
                "properties": {
                  "RAW_BODY": {
                    "type": "array",
                    "items": {
                      "properties": {
                        "id": {
                          "type": "string",
                          "description": "Unique identifier for the Tax Election."
                        },
                        "employee": {
                          "type": "string",
                          "description": "Unique identifier for the Employee."
                        },
                        "setting": {
                          "type": "object",
                          "description": "The Tax Election setting.",
                          "required": [
                            "exempt",
                            "effective_start"
                          ],
                          "properties": {
                            "exempt": {
                              "type": "boolean",
                              "description": "Whether or not the tax is exempt."
                            },
                            "effective_start": {
                              "type": "string",
                              "description": "The effective start date for the Tax Election setting value.",
                              "format": "date"
                            },
                            "effective_end": {
                              "type": "string",
                              "description": "The effective end date for the Tax Election setting value.",
                              "format": "date"
                            }
                          }
                        }
                      },
                      "required": [
                        "id",
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
                    "value": ""
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