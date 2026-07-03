> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gusto.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Complete a Regular Payroll

Your embedded payroll product allows the Company to pay the Employees the right amount at the right cadence, while accounting for tax implications.

We automatically pre-generate scheduled regular payrolls based on the company’s pay schedule and corresponding pay periods. Pay periods are the foundation of payroll. Compensation, time & attendance, taxes, and expense reports all rely on when they happened.

*Before using this guide you need a fully onboarded Company and Employee.*

## 1.  Retrieve Upcoming Payroll

Upcoming regular payrolls can be retrieved by calling [GET /v1/companies/\{company\_uuid}/payrolls](https://docs.gusto.com/embedded-payroll/reference/get-v1-companies-company_id-payrolls) with `processing_statuses=unprocessed`. The next upcoming payroll will be the earliest unprocessed payroll. By default, the payrolls#index endpoint will return only processed payrolls so make sure to add the `processing_statuses=unprocessed` query param. You can use the optional query parameters `start_date` & `end_date` to narrow or expand the response.

This endpoint paginates by default. The default page size is 25 payrolls (maximum 100). Use the `page` and `per` query parameters to iterate through pages and retrieve all payrolls.

The example cURL below is filtering to show unprocessed payrolls, including off cycle, the dates for payroll is between `2021-02-01` and `2021-03-01`. To see all query values review our [API Reference](https://docs.gusto.com/embedded-payroll/reference/get-v1-companies-company_id-payrolls).

```curl
curl --request GET \
     --url 'https://api.gusto-demo.com/v1/companies/company_id/payrolls?processing_statuses=unprocessed&payroll_types=regular,off_cycle&start_date=2021-02-01&end_date=2021-03-31' \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <<COMPANY_API_TOKEN>>'
```

```javascript
const fetch = require('node-fetch');

const url = 'https://api.gusto-demo.com/v1/companies/company_id/payrolls?processed=false&include_off_cycle=true&include=&include=deductions&start_date=2021-02-01&end_date=2021-03-31';
const options = {
  method: 'GET',
  headers: {accept: 'application/json', authorization: 'Bearer <<COMPANY_API_TOKEN>>'}
};

fetch(url, options)
  .then(res => res.json())
  .then(json => console.log(json))
  .catch(err => console.error('error:' + err));
```

This query will return an JSON array of payroll objects:

```json
[
  {
    "payroll_deadline": "2021-02-18T20:00:00Z",
    "check_date": "2021-02-22",
    "processed": false,
    "processed_date": null,
    "calculated_at": null,
    "payroll_uuid": "b50e611d-8f3d-4f24-b001-46675f7b5777",
    "company_uuid": "6bf7807c-a5a0-4f4d-b2e7-3fbb4b2299fb",
    "pay_period": {
      "start_date": "2021-02-01",
      "end_date": "2021-02-15",
      "pay_schedule_uuid": "00ebc4a4-ec88-4435-8f45-c505bb63e501"
    }
  }
]
```

## 2. Prepare & Update Payroll (Optional)

If there is information about the payroll that needs to be updated, start by using the  `PUT companies/{company_uuid}/payrolls/{payroll_uuid}/prepare` [endpoint](https://docs.gusto.com/embedded-payroll/reference/put-v1-companies-company_id-payrolls-payroll_id-prepare).  This endpoint will return the [`version`](https://docs.gusto.com/embedded-payroll/docs/idempotency) and the employee\_compensations data you need to update a payroll.

You can update Regular Hours, Overtime, and Double overtime for Salaried Nonexempt employees, but only Regular Hours can be updated for Exempt employees since they are not eligible for overtime.

**New in v2025-06-15**, the [PUT /v1/companies/{company_uuid}/payrolls/{payroll_uuid}/prepare](https://docs.gusto.com/embedded-payroll/reference/put-v1-companies-company_id-payrolls-payroll_id-prepare) and [GET /v1/companies/{company_uuid}/payrolls/{payroll_uuid}](https://docs.gusto.com/embedded-payroll/reference/get-v1-companies-company_id-payrolls-payroll_id) endpoints:

* Automatically [paginate](https://docs.gusto.com/embedded-payroll/docs/pagination) the number of employee compensations returned with each request
* Accept the pagination parameters of `page` (defaults to 1) and `per` (defaults to 25)
* Return a maximum of 100 employee compensations

Here's a sample request to the prepare endpoint:

```curl
curl --request PUT \
     --url https://api.gusto-demo.com/v1/companies/{company_uuid}/payrolls/{payroll_uuid}/prepare \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <<COMPANY_API_TOKEN>>' \
     --header 'content-type: application/json'
```

```javascript
const fetch = require('node-fetch');

const url = 'https://api.gusto-demo.com/v1/companies/{company_uuid}/payrolls/prepare';
const options = {
  method: 'PUT',
  headers: {
    accept: 'application/json',
    'content-type': 'application/json',
    authorization: 'Bearer <<COMPANY_API_TOKEN>>'
  }
};

fetch(url, options)
  .then(res => res.json())
  .then(json => console.log(json))
  .catch(err => console.error('error:' + err));
```

Here's a sample response from the prepare endpoint:

```json
{
  "payroll_deadline": "2022-02-18T22:00:00Z",
  "check_date": "2021-02-22",
  "processed": false,
  "processed_date": null,
  "calculated_at": null,
  "payroll_uuid": "b50e611d-8f3d-4f24-b001-46675f7b5777",
  "company_uuid": "6bf7807c-a5a0-4f4d-b2e7-3fbb4b2299fb",
  "pay_period": {
    "start_date": "2021-02-01",
    "end_date": "2021-02-15",
    "pay_schedule_uuid": "00ebc4a4-ec88-4435-8f45-c505bb63e501"
  },
  "payroll_status_meta": {
    "cancellable": false,
    "expected_check_date": "2022-02-22",
    "initial_check_date": "2022-02-22",
    "expected_debit_time": "2022-02-18T22:00:00Z",
    "payroll_late": false,
    "initial_debit_cutoff_time": "2022-02-18T22:00:00Z"
  },
  "employee_compensations": [
    {
      "employee_uuid": "187412e1-3dbe-491a-bb2f-2f40323a7067",
      "version": "19289df18e6e20f797de4a585ea5a91535c7ddf7",
      "excluded": false,
      "payment_method": "Direct Deposit",
      "fixed_compensations": [],
      "hourly_compensations": [
        {
          "name": "Regular Hours",
          "hours": "40.000",
          "job_uuid": "bd378298-3e0c-4145-904a-baadf8a91fa3",
          "compensation_multiplier": 1,
          "flsa_status": "Nonexempt"
        },
        {
          "name": "Overtime",
          "hours": "15.000",
          "job_uuid": "9d3760f0-d1f9-4700-8817-0fe2dce5cf23",
          "compensation_multiplier": 1.5,
          "flsa_status": "Nonexempt"
        },
        {
          "name": "Double overtime",
          "hours": "0.000",
          "job_uuid": "b5eef9a9-4a87-4649-a80d-14878c05f44e",
          "compensation_multiplier": 2,
          "flsa_status": "Nonexempt"
        },
        {
          "name": "Regular Hours",
          "hours": "40.000",
          "job_uuid": "332bd171-9efc-432b-abbb-a75c9dba706a",
          "compensation_multiplier": 1,
          "flsa_status": "Nonexempt"
        },
        {
          "name": "Overtime",
          "hours": "5.000",
          "job_uuid": "ca9b3dc1-57ac-4736-901a-9b1c9634b9d5",
          "compensation_multiplier": 1.5,
          "flsa_status": "Nonexempt"
        },
        {
          "name": "Double overtime",
          "hours": "0.000",
          "job_uuid": "1bad01e2-140c-49ed-9542-2388ce4a19b3",
          "compensation_multiplier": 2,
          "flsa_status": "Nonexempt"
        }
      ],
      "paid_time_off": [
        {
          "name": "Vacation Hours",
          "hours": "20.000"
        },
        {
          "name": "Sick Hours",
          "hours": "0.000"
        },
        {
          "name": "Holiday Hours",
          "hours": "0.000"
        }
      ]
    }
  ],
  "fixed_compensation_types": [
    {
      "name": "Bonus"
    },
    {
      "name": "Commission"
    },
    {
      "name": "Correction Payment"
    },
    {
      "name": "Cash Tips"
    },
    {
      "name": "Paycheck Tips"
    }
  ]
}
```

Next you can update the payroll with the new employee\_compensation data with the `PUT companies/{company_uuid}/payrolls/{payroll_uuid}` [endpoint](https://docs.gusto.com/embedded-payroll/reference/put-v1-companies-company_id-payrolls), passing in the updated `employee_compensations` params from the prepare endpoint, as in the example request below.

**New in v2025-06-15**: The `PUT companies/{company_uuid}/payrolls/{payroll_uuid}` [endpoint](https://docs.gusto.com/embedded-payroll/reference/put-v1-companies-company_id-payrolls) limits the number of employee compensations you can include in the request body to 100. In addition, the response will only include the employee compensations included in the request body, rather than the full payroll response.

Here's a sample request to the update payroll endpoint:

```curl
curl --request PUT \
     --url https://api.gusto-demo.com/v1/companies/{company_uuid}/payrolls/{payroll_uuid} \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <<COMPANY_API_TOKEN>>' \
     --header 'content-type: application/json' \
     --data '
{
     "employee_compensations": [
          {
               "employee_uuid": "187412e1-3dbe-491a-bb2f-2f40323a7067",
               "version": "19289df18e6e20f797de4a585ea5a91535c7ddf7",
               "excluded": false,
               "payment_method": "Direct Deposit",
               "fixed_compensations": [
                    {
                         "name": "Bonus",
                         "amount": "200.00",
                    }
               ],
               "hourly_compensations": [
                    {
                         "name": "Regular Hours",
                         "hours": "30.000",
                         "job_uuid": "91bc3b43-ded0-4ee7-98fe-215499e909ba"
                    },
                    {
                         "name": "Double overtime",
                         "hours": "20.000",
                         "job_uuid": "bd378298-3e0c-4145-904a-baadf8a91fa3"
                    },
                    {
                         "name": "Overtime",
                         "hours": "10.000",
                         "job_uuid": "9d3760f0-d1f9-4700-8817-0fe2dce5cf23"
                    }
               ],
               "paid_time_off": [
                    {
                         "name": "Vacation Hours",
                         "hours": "25.000"
                    },
                    {
                         "name": "Sick Hours",
                         "hours": "10.000"
                    },
                    {
                         "name": "Holiday Hours",
                         "hours": "8.000"
                    }
               ]
          }
     ]
}
'
```

```javascript
const fetch = require('node-fetch');

const url = 'https://api.gusto-demo.com/v1/companies/{company_uuid}/payrolls/{payroll_uuid}';
const options = {
  method: 'PUT',
  headers: {
    accept: 'application/json',
    'content-type': 'application/json',
    authorization: 'Bearer <<COMPANY_API_TOKEN>>'
  },
  body: JSON.stringify({
    employee_compensations: [
      {
        employee_uuid: '187412e1-3dbe-491a-bb2f-2f40323a7067',
        version: '19289df18e6e20f797de4a585ea5a91535c7ddf7',
        excluded: false,
        payment_method: 'Direct Deposit',
        fixed_compensations: [
          {
            name: 'Bonus',
            amount: '200.00'
          }
        ],
        hourly_compensations: [
          {
            name: 'Regular Hours',
            hours: '30.000',
            job_uuid: '91bc3b43-ded0-4ee7-98fe-215499e909ba'
          },
          {
            name: 'Double overtime',
            hours: '20.000',
            job_uuid: 'bd378298-3e0c-4145-904a-baadf8a91fa3'
          },
          {
            name: 'Overtime',
            hours: '10.000',
            job_uuid: '9d3760f0-d1f9-4700-8817-0fe2dce5cf23'
          }
        ],
        paid_time_off: [
          {name: 'Vacation Hours', hours: '25.000'},
          {name: 'Sick Hours', hours: '10.000'},
          {name: 'Holiday Hours', hours: '8.000'}
        ]
      }
    ]
  })
};

fetch(url, options)
  .then(res => res.json())
  .then(json => console.log(json))
  .catch(err => console.error('error:' + err));
```

The update endpoint will return the same response data as prepare, with the data reflecting your changes.

## 3. Calculate the Payroll

Once a payroll is updated, use the `PUT companies/{company_id}/payrolls/{payroll_id}/calculate` [endpoint](https://docs.gusto.com/embedded-payroll/reference/put-v1-companies-company_id-payrolls-payroll_id-calculate) to calculate the taxes, benefits, and deductions for the unprocessed payroll. The calculated payroll details provide a preview of the actual values that will be used when the payroll is run. Any benefits or deductions - mandatory or voluntary - that are set up for the employee at the time payroll is calculated will automatically be factored in.

This calculation is asynchronous and a successful request responds with a 202 HTTP status.

```curl
curl --request PUT \
     --url https://api.gusto-demo.com/v1/companies/{company_uuid}/payrolls/{payroll_uuid}/calculate \
     --header 'authorization: Bearer <<COMPANY_API_TOKEN>>'
```

```javascript
const fetch = require('node-fetch');

const url = 'https://api.gusto-demo.com/v1/companies/{company_uuid}/payrolls/{payroll_uuid}/calculate';
const options = {method: 'PUT', headers: {authorization: 'Bearer <<COMPANY_API_TOKEN>>'}};

fetch(url, options)
  .then(res => res.json())
  .then(json => console.log(json))
  .catch(err => console.error('error:' + err));
```

To view the details of the calculated payroll, poll the `GET /v1/companies/{company_uuid}/payrolls/{payroll_uuid}` [endpoint](https://docs.gusto.com/embedded-payroll/reference/get-v1-companies-company_id-payrolls-payroll_id) with the`include=taxes,benefits,deductions` param, until the payroll returns with the `calculated_at` field populated with a timestamp.  The payroll will include any `submission_blockers` and will also return a `totals` attribute once it is calculated.

**New in v2025-06-15** The `GET /v1/companies/{company_uuid}/payrolls/{payroll_uuid}` [endpoint](https://docs.gusto.com/embedded-payroll/reference/get-v1-companies-company_id-payrolls-payroll_id):

* Automatically [paginates](https://docs.gusto.com/embedded-payroll/docs/pagination) the number of employee compensations returned with each request
* Accepts the pagination parameters of `page` (defaults to 1) and `per` (defaults to 25)
* Returns a maximum of 100 employee compensations

If you need to make further updates to the payroll after calculating, use the `PUT companies/{company_uuid}/payrolls/{payroll_uuid}/prepare`  [endpoint](https://docs.gusto.com/embedded-payroll/reference/put-v1-companies-company_id-payrolls-payroll_id-prepare) again, which will cancel out the calculations and return the payroll `version` used for updates.

## 4. Submit Payroll

> 📘 Preview UI
>
> We recommend building a UI where the user can review their payroll before submitting. The displayed information can be customized to fit your unique business needs, but we highly recommend a preview step to provide the user with the payroll details before they finalize it. Typically this includes a breakdown of total payroll, taxes, and debits.

If everything looks accurate, a payroll can be processed using the `PUT companies/{company_uuid}/payrolls/{payroll_uuid}/submit` [endpoint](https://docs.gusto.com/embedded-payroll/reference/put-v1-companies-company_id-payrolls-payroll_id-submit).   Upon success, this request transitions the payroll to the `processed` state and initiates the transfer of funds. **This is a critical step to process payroll. A payroll is not finalized without calling this endpoint.**

This submission is asynchronous and a successful request responds with a 202 HTTP status. Upon success, the payroll status transitions to the `processed` state. You should poll to ensure that payroll is processed successfully, as async errors only occur after async processing is complete.

```curl
curl --request PUT \
     --url https://api.gusto-demo.com/v1/companies/{company_uuid}/payrolls/{payroll_uuid}/submit \
     --header 'authorization: Bearer <<COMPANY_API_TOKEN>>'
```

```javascript
const fetch = require('node-fetch');

const url = 'https://api.gusto-demo.com/v1/companies/{company_uuid}/payrolls/{payroll_uuid}/submit';
const options = {method: 'PUT', headers: {authorization: 'Bearer <<COMPANY_API_TOKEN>>'}};

fetch(url, options)
  .then(res => res.json())
  .then(json => console.log(json))
  .catch(err => console.error('error:' + err));
```

> 📘 Cancel a Payroll
>
> You can revert a payroll to the `unprocessed` state using the `PUT /companies/{company_uuid}/payrolls/{payroll_uuid}/cancel` [endpoint](https://docs.gusto.com/embedded-payroll/reference/put-api-v1-companies-company_id-payrolls-payroll_id-cancel). A payroll ***cannot*** be canceled after 3:30pm PST on the `payroll_deadline`.

## 5. Receive Payroll Receipts and Paystubs

Once a payroll is submitted, we recommend including a summary of the payroll for the end user to view the debit date, check date, and payroll details. The payroll receipt should also be available on this final step. See [Payroll Receipts](https://docs.gusto.com/embedded-payroll/docs/payroll-receipts) for more information.

You can retrieve Payroll Receipt using the `GET payrolls/{payroll_uuid}/receipt` [endpoint](https://docs.gusto.com/embedded-payroll/reference/get-v1-payment-receipts-payrolls-payroll_uuid).

You can retrieve a W2 Employee's Paystub using the `GET payrolls/{payroll_id}/employees/{employee_id}/pay_stub` [endpoint](https://docs.gusto.com/embedded-payroll/reference/get-v1-payrolls-payroll_uuid-employees-employee_uuid-pay_stub).

You can also use the pre-built UI [Flow](https://docs.gusto.com/embedded-payroll/docs/flow-types) for a payroll receipt.

## Architecture Diagram

<Image align="center" src="https://files.readme.io/a991f4abf813188f41ebf43ea2ecc635132b18ce1c46e17114c9b4f1aa892261-GE_diagram_runpayroll.jpg" />

<br />