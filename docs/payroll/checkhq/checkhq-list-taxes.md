> ## Documentation Index
> Fetch the complete documentation index at: https://docs.checkhq.com/llms.txt
> Use this file to discover all available pages before exploring further.

# List taxes

Returns the catalog of payroll taxes Check tracks — both taxes Check supports and in-domain taxes it does not support (see [the Tax object](https://docs.checkhq.com/reference/the-tax-object)).

By default the list includes only taxes whose obligation is currently in effect; pass `effective=false` to list repealed or lapsed taxes instead.

Results are ordered with federal taxes first, then by `jurisdiction`, then by `label`. Pages contain 25 results by default and at most 500 (`limit`).

By default, includes both taxes Check supports and not, and only taxes whose obligation is currently in effect. Pass `effective=false` to list repealed or lapsed taxes instead.

Use `supported=` to filter by whether Check calculates and reports (files) the tax, and `remittable=` to filter by whether Check remits it to the agency on your behalf. Because remittance implies support, `remittable=true` returns a subset of `supported=true`.

Results are ordered with federal taxes first, then by `jurisdiction`, then by `label`. Pages contain 25 results by default and at most 500 (`limit`).

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
    "/taxes": {
      "get": {
        "summary": "List taxes",
        "operationId": "list-taxes",
        "description": "Returns the catalog of payroll taxes Check tracks — both taxes Check supports and in-domain taxes it does not support (see [the Tax object](https://docs.checkhq.com/reference/the-tax-object)).\n\nBy default the list includes only taxes whose obligation is currently in effect; pass `effective=false` to list repealed or lapsed taxes instead.\n\nResults are ordered with federal taxes first, then by `jurisdiction`, then by `label`. Pages contain 25 results by default and at most 500 (`limit`).",
        "parameters": [
          {
            "name": "id",
            "in": "query",
            "description": "Tax IDs to look up, for batch lookups. Repeat the parameter to provide multiple values (max 500 per request).",
            "explode": true,
            "schema": {
              "type": "array",
              "items": {
                "type": "string"
              }
            }
          },
          {
            "name": "jurisdiction",
            "in": "query",
            "description": "Jurisdictions to filter to, as lowercase region codes (e.g. `fed`, `ny`, `pa`). A state's code includes its state and local taxes. Repeat the parameter to provide multiple values.",
            "explode": true,
            "schema": {
              "type": "array",
              "items": {
                "type": "string"
              }
            }
          },
          {
            "name": "supported",
            "in": "query",
            "description": "Filter by whether Check calculates and reports (files) the tax. Use `supported=false` to find in-domain taxes Check does not support.",
            "schema": {
              "type": "boolean"
            }
          },
          {
            "name": "remittable",
            "in": "query",
            "description": "Filter by whether Check remits the tax to the agency on your behalf. Because remittance implies support, `remittable=true` returns a subset of `supported=true`.",
            "schema": {
              "type": "boolean"
            }
          },
          {
            "name": "effective",
            "in": "query",
            "description": "Filter by whether the tax obligation is in effect as of today. When omitted, the list includes only currently effective taxes.",
            "schema": {
              "type": "boolean"
            }
          },
          {
            "name": "label_contains",
            "in": "query",
            "description": "Case-insensitive substring match on the tax `label`. Useful for looking up local taxes by name.",
            "schema": {
              "type": "string"
            }
          },
          {
            "name": "limit",
            "in": "query",
            "description": "Number of results per page (default 25, max 500).",
            "schema": {
              "type": "integer",
              "default": 25,
              "maximum": 500
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
                    "value": {
                      "next": "https://sandbox.checkhq.com/taxes?cursor=cD0lNUIlMjJmZWQlMjIlMkMlMjJGZWRlcmFsK1VuZW1wbG95bWVudCtUYXglMjIlNUQ",
                      "previous": null,
                      "results": [
                        {
                          "id": "tax_8L3JLfsH4X6dp0maBWfW",
                          "label": "Federal Income Tax",
                          "jurisdiction": "fed",
                          "payer": "employee",
                          "supported": true,
                          "remittable": true,
                          "effective_from": "1900-01-01",
                          "effective_to": null
                        },
                        {
                          "id": "tax_u4DzMCYXAUL6OfcgPeyg",
                          "label": "Federal Unemployment Tax",
                          "jurisdiction": "fed",
                          "payer": "company",
                          "supported": true,
                          "remittable": true,
                          "effective_from": "1900-01-01",
                          "effective_to": null
                        },
                        {
                          "id": "tax_xs7qYWN4Y3je34zlrimK",
                          "label": "Hatboro Borough / Horsham SD Local Services Tax",
                          "jurisdiction": "pa",
                          "payer": "employee",
                          "supported": true,
                          "remittable": true,
                          "effective_from": "2021-01-01",
                          "effective_to": null
                        }
                      ]
                    }
                  }
                },
                "schema": {
                  "type": "object",
                  "properties": {
                    "next": {
                      "type": "string",
                      "nullable": true,
                      "description": "URL of the next page of results, or null if there are no more."
                    },
                    "previous": {
                      "type": "string",
                      "nullable": true,
                      "description": "URL of the previous page of results, or null on the first page."
                    },
                    "results": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "id": {
                            "type": "string",
                            "description": "Unique identifier (`tax_` prefix).",
                            "example": "tax_8L3JLfsH4X6dp0maBWfW"
                          },
                          "label": {
                            "type": "string",
                            "description": "Human-readable name for display.",
                            "example": "Federal Income Tax"
                          },
                          "jurisdiction": {
                            "type": "string",
                            "description": "Lowercase region code (`fed` or a lowercased ISO 3166-2:US region code). Local taxes use their state's value.",
                            "example": "fed"
                          },
                          "payer": {
                            "type": "string",
                            "enum": [
                              "employee",
                              "company"
                            ],
                            "description": "Whose money pays the tax: `employee` (withheld) or `company` (employer cost).",
                            "example": "employee"
                          },
                          "supported": {
                            "type": "boolean",
                            "nullable": true,
                            "description": "Whether Check calculates and reports (files) this tax. Does not imply Check remits it — see `remittable`.",
                            "example": true
                          },
                          "remittable": {
                            "type": "boolean",
                            "description": "Whether Check remits this tax to the agency on your behalf. Always `false` when `supported` is `false` (Check can’t remit a tax it doesn’t support); may also be `false` for supported taxes the employer self-remits (e.g. NY SDI paid to a private carrier).",
                            "example": true
                          },
                          "effective_from": {
                            "type": "string",
                            "format": "date",
                            "nullable": true,
                            "description": "First date (inclusive) the obligation exists. Very old taxes carry values of `1900-01-01`.",
                            "example": "1900-01-01"
                          },
                          "effective_to": {
                            "type": "string",
                            "format": "date",
                            "nullable": true,
                            "description": "Last date (inclusive) the obligation applies; `null` while still in effect."
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
                    "value": {
                      "error": {
                        "type": "validation_error",
                        "message": "Please correct the required fields and try again.",
                        "input_errors": [
                          {
                            "field": "detail",
                            "field_path": [
                              "detail"
                            ],
                            "message": "Unknown jurisdiction."
                          }
                        ]
                      }
                    }
                  }
                },
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": {
                      "type": "object",
                      "properties": {
                        "type": {
                          "type": "string",
                          "example": "validation_error"
                        },
                        "message": {
                          "type": "string",
                          "example": "Please correct the required fields and try again."
                        },
                        "input_errors": {
                          "type": "array",
                          "items": {
                            "type": "object",
                            "properties": {
                              "field": {
                                "type": "string",
                                "example": "detail"
                              },
                              "field_path": {
                                "type": "array",
                                "items": {
                                  "type": "string"
                                }
                              },
                              "message": {
                                "type": "string",
                                "example": "Unknown jurisdiction."
                              }
                            }
                          }
                        }
                      }
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