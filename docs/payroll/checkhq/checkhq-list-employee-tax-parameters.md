> ## Documentation Index
> Fetch the complete documentation index at: https://docs.checkhq.com/llms.txt
> Use this file to discover all available pages before exploring further.

# List an employee's tax parameters

Get a paginated list of an employee’s tax parameters

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
      "get": {
        "summary": "List an employee's tax parameters",
        "description": "Get a paginated list of an employee’s tax parameters",
        "operationId": "list-employees-tax-parameters",
        "parameters": [
          {
            "name": "employee_id",
            "in": "path",
            "description": "ID of the employee used to list the applicable tax parameter.",
            "schema": {
              "type": "string"
            },
            "required": true
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
          },
          {
            "name": "tax_id",
            "in": "query",
            "description": "Used to further filter down the list of the company’s tax parameters to a specific tax.",
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
                    "value": "{\n  \"next\": null,\n  \"previous\": null,\n  \"results\": [\n    {\n      \"id\": \"spa_yqVxHQZb7aVPHrh16HRq\",\n      \"label\": \"Filing status\",\n      \"description\": \"Filing status\",\n      \"name\": \"filing_status\",\n      \"type\": \"select\",\n      \"options\": [\n        {\n          \"label\": \"Married but withholding at higher single rate\",\n          \"value\": \"MH\"\n        },\n        {\n          \"label\": \"Non-resident alien\",\n          \"value\": \"NRA\"\n        },\n        {\n          \"label\": \"Married\",\n          \"value\": \"M\"\n        },\n        {\n          \"label\": \"Single\",\n          \"value\": \"S\"\n        }\n      ],\n      \"depends_on\": null,\n      \"editable\": true,\n      \"effective_datable\": true,\n      \"can_be_applied_for\": false,\n      \"jurisdiction\": \"jur_mRpDYFyFSUD1ArZdrMis\",\n      \"tax\": \"tax_afRJqY785WwYH0PrtFde\",\n      \"setting\": null,\n      \"valid_formats\": null,\n      \"definitions\": null,\n      \"default_value\": \"S\",\n      \"help_links\": null,\n    },\n    ...,\n  ]\n}"
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