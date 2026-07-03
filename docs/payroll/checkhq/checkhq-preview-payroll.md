> ## Documentation Index
> Fetch the complete documentation index at: https://docs.checkhq.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Preview a payroll

Returns a preview of an approved version of the input payroll

Previewing a payroll can be accomplished in two ways: synchronously (default) or asynchronously. Asynchronous preview is required if the payroll has more than 500 payroll items and contractor payments.

To preview asynchronously, set the `async` query parameter to `true`.

> **Note for Python clients:** The `async` query parameter name is a reserved keyword in Python. When using a typed Python client, you may need to pass this parameter using dictionary unpacking or an alternative syntax supported by your HTTP library (e.g., `params={"async": "true"}`).

When the preview is initiated, the `preview` property on the Payroll object will be created with a status of `calculating`. After the preview is completed, it will move into `succeeded`.

```json
{
  ...,
  "preview": {
    "status": "calculating",
    "started_at": "2019-06-29T18:26:56.848920Z"
  },
  ...
}
```

Previewing a payroll is required before the payroll can be approved. If the payroll or any associated Payroll Items or Contractor Payments are modified, then the preview calculation will no longer be valid, and the `preview` object on the payroll will be reset to `null`.

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
    "/payrolls/{payroll}/preview": {
      "get": {
        "summary": "Preview a payroll",
        "description": "Returns a preview of an approved version of the input payroll",
        "operationId": "preview-payroll",
        "parameters": [
          {
            "name": "payroll",
            "in": "path",
            "description": "ID of the payroll to preview.",
            "schema": {
              "type": "string"
            },
            "required": true
          },
          {
            "name": "Accept",
            "in": "header",
            "description": "Either `application/json` or `text/csv`",
            "schema": {
              "type": "string"
            }
          },
          {
            "name": "async",
            "in": "query",
            "description": "Enable this flag to preview asynchronously. This is required for payrolls with more than 500 payroll items and contractor payments.",
            "schema": {
              "type": "boolean",
              "default": false
            }
          },
          {
            "name": "include_items",
            "in": "query",
            "description": "Enable this flag to return payroll items directly on this payroll.",
            "schema": {
              "type": "boolean",
              "default": false
            }
          },
          {
            "name": "include_contractor_payments",
            "in": "query",
            "description": "Enable this flag to return contractor payments directly on this payroll.",
            "schema": {
              "type": "boolean",
              "default": false
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
                    "value": "{\n  \"id\": \"pay_Z26PNMC7Ky1wfFQzVqfF\",\n  \"company\": \"com_sx3svU6K8c5ZkSFlOh5p\",\n  \"period_start\": \"2019-06-16\",\n  \"period_end\": \"2019-06-29\",\n  \"approval_deadline\": \"2019-07-02T00:00:00.000000Z\",\n  \"approved_at\": \"2019-06-29T18:26:56.848920Z\",\n  \"payday\": \"2019-07-05\",\n  \"status\": \"paid\",\n  \"type\": \"regular\",\n  \"pay_frequency\": \"biweekly\",\n  \"funding_payment_method\": \"ach\",\n  \"processing_period\": \"four_day\",\n  \"off_cycle_options\": null,\n  \"managed\": true,\n  \"totals\": {\n    \"employee_gross\": \"961.54\",\n    \"employee_reimbursements\": \"0.00\",\n    \"employee_taxes\": \"249.23\",\n    \"employee_benefits\": \"0.00\",\n    \"post_tax_deductions\": \"0.00\",\n    \"employee_net\": \"712.31\",\n    \"contractor_gross\": \"100.00\",\n    \"contractor_reimbursements\": \"15.00\",\n    \"contractor_net\": \"115.00\",\n    \"company_taxes\": \"73.56\",\n    \"company_benefits\": \"0.00\",\n    \"liability\": \"1150.10\",\n    \"cash_requirement\": \"1150.10\"\n  },\n  \"items\": [\n    {\n      \"id\": \"itm_yvmmsVGFxLoBaMIkqzea\",\n      \"payroll\": \"pay_Z26PNMC7Ky1wfFQzVqfF\",\n      \"employee\": \"emp_zGGp6wYcxAeu1Ng8IA7v\",\n      \"payment_method\": \"direct_deposit\",\n      \"net_pay\": \"712.31\",\n      \"earnings\": [\n        {\n          \"amount\": \"961.54\",\n          \"hours\": 40.0,\n          \"type\": \"regular\",\n          \"workplace\": \"wrk_cxcG4vjGKcSXZk1fgKai\",\n          \"code\": null,\n          \"description\": null\n        }\n      ],\n      \"reimbursements\": [],\n      \"taxes\": [\n        {\n          \"tax\": \"tax_I1Z9zqbBGWIbvlZpN2Vq\",\n          \"description\": \"New York SDI\",\n          \"amount\": \"0.60\",\n          \"payer\": \"employee\"\n        },\n        {\n          \"tax\": \"tax_ImvSF9CTuMdokf0uwx5x\",\n          \"description\": \"Employer FICA Tax\",\n          \"amount\": \"59.62\",\n          \"payer\": \"company\"\n        },\n        {\n          \"tax\": \"tax_yjNkKk061BTipYv7G4Ti\",\n          \"description\": \"New York City Tax\",\n          \"amount\": \"31.04\",\n          \"payer\": \"employee\"\n        },\n        {\n          \"tax\": \"tax_S1krAkh75RzdWu5J53HA\",\n          \"description\": \"New York State Tax\",\n          \"amount\": \"44.20\",\n          \"payer\": \"employee\"\n        },\n        {\n          \"tax\": \"tax_UJrIQbtVErbdez0bYTVN\",\n          \"description\": \"New York Family Leave Benefits\",\n          \"amount\": \"1.47\",\n          \"payer\": \"employee\"\n        },\n        {\n          \"tax\": \"tax_1XHqR9Qf5t18SD2sfYEe\",\n          \"description\": \"Medicare\",\n          \"amount\": \"13.94\",\n          \"payer\": \"employee\"\n        },\n        {\n          \"tax\": \"tax_8L3JLfsH4X6dp0maBWfW\",\n          \"description\": \"Federal Income Tax\",\n          \"amount\": \"98.36\",\n          \"payer\": \"employee\"\n        },\n        {\n          \"tax\": \"tax_ibU8cGhC5OlpOjoQFIXV\",\n          \"description\": \"FICA\",\n          \"amount\": \"59.62\",\n          \"payer\": \"employee\"\n        },\n        {\n          \"tax\": \"tax_O3f21hkS1cvHBZTa61BO\",\n          \"description\": \"Employer Medicare Tax\",\n          \"amount\": \"13.94\",\n          \"payer\": \"company\"\n        }\n      ],\n      \"benefits\": [],\n      \"benefit_overrides\": [],\n      \"post_tax_deductions\": [],\n      \"post_tax_deduction_overrides\": [],\n      \"warnings\": []\n    }\n  ],\n  \"contractor_payments\": [\n    {\n      \"contractor\": \"ctr_90QzaH9xPRI7JRLXnRoU\",\n      \"payment_method\": \"manual\",\n      \"amount\": \"100.00\",\n      \"reimbursement_amount\": \"15.00\"\n    }\n  ],\n  \"is_void\": false,\n  \"metadata\": {}\n}"
                  }
                },
                "schema": {
                  "type": "object",
                  "properties": {
                    "id": {
                      "type": "string",
                      "example": "pay_Z26PNMC7Ky1wfFQzVqfF"
                    },
                    "company": {
                      "type": "string",
                      "example": "com_sx3svU6K8c5ZkSFlOh5p"
                    },
                    "period_start": {
                      "type": "string",
                      "example": "2019-06-16"
                    },
                    "period_end": {
                      "type": "string",
                      "example": "2019-06-29"
                    },
                    "approval_deadline": {
                      "type": "string",
                      "example": "2019-07-02T00:00:00.000000Z"
                    },
                    "approved_at": {
                      "type": "string",
                      "example": "2019-06-29T18:26:56.848920Z"
                    },
                    "payday": {
                      "type": "string",
                      "example": "2019-07-05"
                    },
                    "status": {
                      "type": "string",
                      "example": "paid"
                    },
                    "type": {
                      "type": "string",
                      "example": "regular"
                    },
                    "pay_frequency": {
                      "type": "string",
                      "example": "biweekly"
                    },
                    "funding_payment_method": {
                      "type": "string",
                      "example": "ach"
                    },
                    "processing_period": {
                      "type": "string",
                      "example": "four_day"
                    },
                    "off_cycle_options": {},
                    "managed": {
                      "type": "boolean",
                      "example": true,
                      "default": true
                    },
                    "totals": {
                      "type": "object",
                      "properties": {
                        "employee_gross": {
                          "type": "string",
                          "example": "961.54"
                        },
                        "employee_reimbursements": {
                          "type": "string",
                          "example": "0.00"
                        },
                        "employee_taxes": {
                          "type": "string",
                          "example": "249.23"
                        },
                        "employee_benefits": {
                          "type": "string",
                          "example": "0.00"
                        },
                        "post_tax_deductions": {
                          "type": "string",
                          "example": "0.00"
                        },
                        "employee_net": {
                          "type": "string",
                          "example": "712.31"
                        },
                        "contractor_gross": {
                          "type": "string",
                          "example": "100.00"
                        },
                        "contractor_reimbursements": {
                          "type": "string",
                          "example": "15.00"
                        },
                        "contractor_net": {
                          "type": "string",
                          "example": "115.00"
                        },
                        "company_taxes": {
                          "type": "string",
                          "example": "73.56"
                        },
                        "company_benefits": {
                          "type": "string",
                          "example": "0.00"
                        },
                        "liability": {
                          "type": "string",
                          "example": "1150.10"
                        },
                        "cash_requirement": {
                          "type": "string",
                          "example": "1150.10"
                        }
                      }
                    },
                    "items": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "id": {
                            "type": "string",
                            "example": "itm_yvmmsVGFxLoBaMIkqzea"
                          },
                          "payroll": {
                            "type": "string",
                            "example": "pay_Z26PNMC7Ky1wfFQzVqfF"
                          },
                          "employee": {
                            "type": "string",
                            "example": "emp_zGGp6wYcxAeu1Ng8IA7v"
                          },
                          "payment_method": {
                            "type": "string",
                            "example": "direct_deposit"
                          },
                          "net_pay": {
                            "type": "string",
                            "example": "712.31"
                          },
                          "earnings": {
                            "type": "array",
                            "items": {
                              "type": "object",
                              "properties": {
                                "amount": {
                                  "type": "string",
                                  "example": "961.54"
                                },
                                "hours": {
                                  "type": "integer",
                                  "example": 40,
                                  "default": 0
                                },
                                "type": {
                                  "type": "string",
                                  "example": "regular"
                                },
                                "workplace": {
                                  "type": "string",
                                  "example": "wrk_cxcG4vjGKcSXZk1fgKai"
                                },
                                "code": {},
                                "description": {}
                              }
                            }
                          },
                          "reimbursements": {
                            "type": "array"
                          },
                          "taxes": {
                            "type": "array",
                            "items": {
                              "type": "object",
                              "properties": {
                                "tax": {
                                  "type": "string",
                                  "example": "tax_I1Z9zqbBGWIbvlZpN2Vq"
                                },
                                "description": {
                                  "type": "string",
                                  "example": "New York SDI"
                                },
                                "amount": {
                                  "type": "string",
                                  "example": "0.60"
                                },
                                "payer": {
                                  "type": "string",
                                  "example": "employee"
                                }
                              }
                            }
                          },
                          "benefits": {
                            "type": "array"
                          },
                          "benefit_overrides": {
                            "type": "array"
                          },
                          "post_tax_deductions": {
                            "type": "array"
                          },
                          "post_tax_deduction_overrides": {
                            "type": "array"
                          },
                          "tax_overrides": {
                            "type": "array"
                          },
                          "warnings": {
                            "type": "array"
                          }
                        }
                      }
                    },
                    "contractor_payments": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "contractor": {
                            "type": "string",
                            "example": "ctr_90QzaH9xPRI7JRLXnRoU"
                          },
                          "payment_method": {
                            "type": "string",
                            "example": "manual"
                          },
                          "amount": {
                            "type": "string",
                            "example": "100.00"
                          },
                          "reimbursement_amount": {
                            "type": "string",
                            "example": "15.00"
                          }
                        }
                      }
                    },
                    "is_void": {
                      "type": "boolean",
                      "example": false,
                      "default": true
                    },
                    "metadata": {
                      "type": "object",
                      "properties": {}
                    }
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