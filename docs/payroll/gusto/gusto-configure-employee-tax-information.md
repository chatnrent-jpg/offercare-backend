> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gusto.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Configure employee tax information

Employees are required to configure two types of tax information as part of their onboarding:

* **Federal tax**: Collected by the U.S. federal government based on an employee’s income.

* **State tax**: Collected by the state where an employee works or lives. Not all states collect income tax.

## Federal taxes

An employee must provide federal tax information to file and pay taxes correctly.

1. To provide federal tax details, you will first need to get the `version` of the tax details using the [GET employees/\{employee\_uuid}/federal\_taxes](https://docs.gusto.com/embedded-payroll/reference/get-v1-employees-employee_id-federal_taxes) endpoint.
2. Once you have the `version` you can update the federal tax details using the [PUT employees/\{employee\_uuid}/federal\_taxes](https://docs.gusto.com/embedded-payroll/reference/put-v1-employees-employee_id-federal_taxes) endpoint.

**Sample request**

```curl
curl --request PUT \
     --url https://api.gusto-demo.com/v1/employees/{employee_uuid}/federal_taxes \
     --header 'accept: application/json' \
     --header 'authorization: Bearer COMPANY_API_TOKEN' \
     --header 'content-type: application/json' \
     --data '
{
     "version": "VERSION",
     "filing_status": "Single",
     "extra_withholding": "0.0",
     "two_jobs": true,
     "dependents_amount": "0.0",
     "other_income": "0.0",
     "deductions": "0.0",
     "w4_data_type": "rev_2020_w4"
}
'
```

**Sample response**

```json
{
  "version": "VERSION",
  "filing_status": "Single",
  "extra_withholding": "0.0",
  "two_jobs": true,
  "dependents_amount": "0.0",
  "other_income": "0.0",
  "deductions": "0.0",
  "employee_id": 29,
  "w4_data_type": "rev_2020_w4"
}
```

## State taxes

The data required to calculate an employee's state taxes correctly varies by home and work location.

### 1. Get the employee’s state tax information

To know which information is needed for an employee’s state taxes, first call the [GET employees/\{employee\_uuid}/state\_taxes](https://docs.gusto.com/embedded-payroll/reference/get-v1-employees-employee_id-state_taxes) endpoint.

This will return an array of questions that must be answered, and possible answers for each, and what we currently have marked as that answer.

Below is an example for California with the following answers:

* `filing_status = S`
* `withholding_allowance = 1`
* `additional_withholding = 0.0`
* `file_new_hire_report = false`

**Sample request**

```curl
curl --request GET \
     --url https://api.gusto-demo.com/v1/employees/employee_uuid/state_taxes \
     --header 'X-Gusto-API-Version: 2024-04-01' \
     --header 'accept: application/json' \
     --header 'authorization: Bearer COMPANY_API_TOKEN'
```

**Sample response**

```json
{
  "employee_uuid": "92fa4d30-e284-43d0-a26e-605619c04beb",
  "file_new_hire_report": false,
  "is_work_state": true,
  "state": "CA",
  "questions": [
    {
      "label": "Filing Status",
      "description": "The Head of Household status applies to unmarried individuals who have a relative living with them in their home. If unsure, read the <a target='_blank' data-bypass rel='noopener noreferrer' tabindex='99' href='https://www.ftb.ca.gov/file/personal/filing-status/index.html'>CA Filing Status explanation</a>.\n",
      "key": "filing_status",
      "input_question_format": {
        "type": "Select",
        "options": [
          {
            "value": "S",
            "label": "Single"
          },
          {
            "value": "M",
            "label": "Married one income"
          },
          {
            "value": "MD",
            "label": "Married dual income"
          },
          {
            "value": "H",
            "label": "Head of household"
          },
          {
            "value": "E",
            "label": "Do Not Withhold"
          }
        ]
      },
      "answers": [
        {
          "value": "S",
          "valid_from": "2010-01-01",
          "valid_up_to": null
        }
      ]
    },
    {
      "label": "Withholding Allowance",
      "description": "This value is needed to calculate the employee's CA income tax withholding. If unsure, use the <a target='_blank' data-bypass rel='noopener noreferrer' tabindex='99' href='http://www.edd.ca.gov/pdf_pub_ctr/de4.pdf'>CA DE-4 form</a> to calculate the value manually.\n",
      "key": "withholding_allowance",
      "input_question_format": {
        "type": "Number"
      },
      "answers": [
        {
          "value": 1,
          "valid_from": "2010-01-01",
          "valid_up_to": null
        }
      ]
    },
    {
      "label": "Additional Withholding",
      "description": "You can withhold an additional amount of California income taxes here.",
      "key": "additional_withholding",
      "input_question_format": {
        "type": "Currency"
      },
      "answers": [
        {
          "value": "0.0",
          "valid_from": "2010-01-01",
          "valid_up_to": null
        }
      ]
    },
    {
      "label": "File a New Hire Report?",
      "description": "State law requires you to file a new hire report within 20 days of hiring or re-hiring an employee.",
      "key": "file_new_hire_report",
      "input_question_format": {
        "type": "Select"
      },
      "answers": [
        {
          "value": false,
          "valid_from": "2010-01-01",
          "valid_up_to": null
        }
      ]
    }
  ]
}

```

### 2. Update the employee’s state tax information

Once you know which information needs to be added or updated, you can use the [PUT employees/\{employee\_uuid}/state\_taxes](https://docs.gusto.com/embedded-payroll/reference/put-v1-employees-employee_id-state_taxes) endpoint.

In this example, the request is changing the following for the employee's California state tax information:

* `filing_status`: from `"S"` (single) to `"M"` (married)
* `withholding_allowance`: from a previous value (e.g., `0` or `1`) to `2`
* `additional_withholding`: from the previous amount to `"25.0"`
* `file_new_hire_report`: from `false` to `true`

**Sample request**

```curl
curl --request PUT \
     --url https://api.gusto-demo.com/v1/employees/{employee_uuid}/state_taxes \
     --header 'accept: application/json' \
     --header 'authorization: Bearer COMPANY_API_TOKEN' \
     --header 'content-type: application/json' \
     --data '
{
     "employee_id": "EMPLOYEE_UUID",
     "states": [
          {
               "state": "CA",
               "questions": [
                    {
                         "key": "filing_status",
                         "answers": [
                              {
                                   "value": "M",
                                   "valid_from": "2010-01-01",
                                   "valid_up_to": null
                              }
                         ]
                    },
                    {
                         "key": "withholding_allowance",
                         "answers": [
                              {
                                   "value": 2,
                                   "valid_from": "2010-01-01",
                                   "valid_up_to": null
                              }
                         ]
                    },
                    {
                         "key": "additional_withholding",
                         "answers": [
                              {
                                   "value": "25.0",
                                   "valid_from": "2010-01-01",
                                   "valid_up_to": null
                              }
                         ]
                    },
                    {
                         "key": "file_new_hire_report",
                         "answers": [
                              {
                                   "value": true,
                                   "valid_from": "2010-01-01",
                                   "valid_up_to": null
                              }
                         ]
                    }
               ]
          }
     ]
}
'
```

**Sample response**

```json
[
  {
    "employee_uuid": "EMPLOYEE_UUID",
    "state": "CA",
    "file_new_hire_report": false,
    "is_work_state": true,
    "questions": [
      {
        "is_question_for_admin_only": false,
        "label": "Filing Status",
        "description": "The Head of Household status applies to unmarried individuals who have a relative living with them in their home. If unsure, read the <a target='_blank' data-bypass rel='noopener noreferrer' tabindex='0' href='https://www.ftb.ca.gov/file/personal/filing-status/index.html'>CA
Filing Status explanation</a>.\n",
        "key": "filing_status",
        "input_question_format": {
          "type": "Select",
          "options": [
            {
              "value": "M",
              "label": "Single"
            }
          ]
        },
        "answers": [
          {
            "value": "M",
            "valid_from": "2010-01-01",
            "valid_up_to": null
          }
        ]
      },
      {
        "is_question_for_admin_only": false,
        "label": "Withholding Allowance",
        "description": "This value is needed to calculate the employee's CA income tax withholding. If unsure, use the <a target='_blank' data-bypass rel='noopener noreferrer' tabindex='0' href='https://www.edd.ca.gov/pdf_pub_ctr/de4.pdf'>CA DE-4 form</a> to calculate the value manually.\n",
        "key": "withholding_allowance",
        "input_question_format": {
          "type": "Number"
        },
        "answers": [
          {
            "value": 2,
            "valid_from": "2010-01-01",
            "valid_up_to": null
          }
        ]
      },
      {
        "is_question_for_admin_only": false,
        "label": "Additional Withholding",
        "description": "You can withhold an additional amount of California income taxes here.",
        "key": "additional_withholding",
        "input_question_format": {
          "type": "Currency"
        },
        "answers": [
          {
            "value": "25.0",
            "valid_from": "2010-01-01",
            "valid_up_to": null
          }
        ]
      },
      {
        "is_question_for_admin_only": true,
        "label": "File a New Hire Report?",
        "description": "State law requires you to file a new hire report within 20 days of hiring or re-hiring an employee.",
        "key": "file_new_hire_report",
        "input_question_format": {
          "type": "Select",
          "options": [
            {
              "value": true,
              "label": "Yes, file the state new hire report for me."
            },
            {
              "value": false,
              "label": "No, I have already filed."
            }
          ]
        },
        "answers": [
          {
            "value": true,
            "valid_from": "2010-01-01",
            "valid_up_to": null
          }
        ]
      }
    ]
  }
]
```