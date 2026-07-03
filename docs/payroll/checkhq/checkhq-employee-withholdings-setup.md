> ## Documentation Index
> Fetch the complete documentation index at: https://docs.checkhq.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Employee Withholdings Setup

This Component allows an employee to complete and sign state and federal withholding forms (i.e. W-4).
<img style="width: 500px;   display: block;
  margin-left: auto;
  margin-right: auto;" src="https://public-component-assets.s3.amazonaws.com/ee_tax_withholding.svg" />
Learn how to embed Components in our <a target="_blank" href="https://docs.checkhq.com/docs/embedding-a-component">guide</a>.

> 🚧 This component is intended for employee use only, not employers
>
> This component should only be completed by the employee who is intending to update their tax information, not the employer. This component generates forms signed by the employee, so employers should not use it to sign a form on the employee's behalf.
>
> If you are building an employer-facing UI to allow an employer to update an employee's tax information, you should surface the [Employee Tax Setup component](https://docs.checkhq.com/reference/employee-tax-setup). This component will allow the employer to update information based on tax documents provided to them, without signing forms on the employee's behalf.

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
    "/employees/{employee}/components/withholdings_setup": {
      "post": {
        "summary": "Employee Withholdings Setup",
        "description": "This Component allows an employee to complete and sign state and federal withholding forms (i.e. W-4).\n<img style=\"width: 500px;   display: block;\n  margin-left: auto;\n  margin-right: auto;\" src=\"https://public-component-assets.s3.amazonaws.com/ee_tax_withholding.svg\" />\nLearn how to embed Components in our <a target=\"_blank\" href=\"https://docs.checkhq.com/docs/embedding-a-component\">guide</a>.",
        "operationId": "employee-withholdings-setup",
        "parameters": [
          {
            "name": "employee",
            "in": "path",
            "description": "ID of the employee for which a component link will be generated",
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
                    "value": "{\"url\":\"{component_url}\"}"
                  }
                },
                "schema": {
                  "type": "object",
                  "properties": {
                    "url": {
                      "type": "string",
                      "example": "{component_url}"
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