> ## Documentation Index
> Fetch the complete documentation index at: https://docs.checkhq.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Tax Parameters

Displaying and collecting company and employee tax parameters

Collecting tax and withholding information from companies and employees is essential to calculating accurate taxable amounts and liabilities for every payroll. Displaying this information is just as important as it gives companies and employees visibility to validate their elections.

To that end, Check’s API allows you to display applicable tax parameters, collect and update tax parameter settings, and query these objects through different moments in time.

<Callout icon="📘" theme="info">
  The following examples are defined for a fictitious company, and can be used to list or update tax parameter settings for any existing company or employee.

* Company: `/company_tax_params/:company_id`
* Employee: `/employee_tax_params/:employee_id`
  </Callout>

## Listing applicable tax parameters

Use the Tax Setup API to display the information that is required to be collected by both companies and employees. The main [Tax Parameter](https://docs.checkhq.com/reference/the-tax-parameter-object) contains the following important fields:

* `description`: Contains the human-readable description of a tax parameter object which gives a detailed explanation of what it is.
* `type`: Defines the type of a tax parameter, which in turn defines the expected type of data to be collected. See the [Types of Tax Parameters](https://docs.checkhq.com/reference/types-of-tax-parameters) for more information.

The following example defines how we would list the applicable tax parameters for a company:

```curl
curl -X GET \
  https://sandbox.checkhq.com/company_tax_params/com_8BDDxUvOZcFVeiuAGne8 \
  -H 'Authorization: Bearer YOUR_API_KEY'
```

**EXAMPLE RESPONSE**

```json
{
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "spa_W2kGF6lFM69FuuuyWyEn",
      "label": "California Employer Unemployment Tax Rate",
      "description": "California Employer Unemployment Tax Rate",
      "name": "california_employer_unemployment_rate",
      "type": "percent",
      "options": null,
      "depends_on": null,
      "editable": true,
      "effective_datable": true,
      "can_be_applied_for": false,
      "jurisdiction": "jur_mRpDYFyFSUD1ArZdrMis",
      "tax": "tax_afRJqY785WwYH0PrtFde",
      "setting": null,
      "submitter": "company",
    },
    ...,
  ]
}
```

We can see how the response includes a paginated list of tax parameters where the setting is `null`. This is because we have not yet created a tax parameter setting for this company.

## Creating Tax Parameter Settings

To be able to accurately display the collected [Tax Parameter Settings](https://docs.checkhq.com/reference/tax-parameter-setting) from a company or employee, we must first create a new one. The tax parameter setting also has some important fields that are worth detailing:

* `value`: Contains the actual value of the setting that we are collecting from either a company or employee.
* `effective_start`: Represents the starting date from which we will consider the value to be effective. Can only be set if the tax parameter has `effective_datable=true`.
* `applied_for`: Defines a way to mark a setting as being applied for, but not having yet received the value. Can only be set if the tax parameter has `can_be_applied_for=true`.

The following example defines how we would create a new tax parameter setting for the same company from the previous example:

```curl
curl -X PATCH \
  https://sandbox.checkhq.com/company_tax_params/com_8BDDxUvOZcFVeiuAGne8 \
  -H 'Authorization: Bearer YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '[
        {
          "id":"spa_W2kGF6lFM69FuuuyWyEn",
          "value": "1.75", 
         }
      ]'
```

**EXAMPLE RESPONSE**

```json
{
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "spa_W2kGF6lFM69FuuuyWyEn",
      "label": "California Employer Unemployment Tax Rate",
      "description": "California Employer Unemployment Tax Rate",
      "name": "california_employer_unemployment_rate",
      "type": "percent",
      "options": null,
      "depends_on": null,
      "editable": true,
      "effective_datable": true,
      "can_be_applied_for": false,
      "jurisdiction": "jur_mRpDYFyFSUD1ArZdrMis",
      "tax": "tax_afRJqY785WwYH0PrtFde",
      "submitter": "company",
      "setting": {
        "applied_for": null,
        "value": "1.75",
        "effective_start": "1900-01-01",
      }
    },
    ...,
  ]
}
```

<Callout icon="📘" theme="info">
  Not defining an `effective_start` in the request body will default to `1900-01-01` for the first setting. Any subsequent update to the same parameter will use today’s date.
</Callout>

### Validations

When creating or updating a tax parameter setting, we run specific validations depending on the tax parameter type. See [Types of Tax Parameters](https://docs.checkhq.com/reference/types-of-tax-parameters) for more information. There are a couple of specific validations that are worth a further explanation.

* Federal EIN and State Account Numbers are defined as strings, but we also validate the format of each string in accordance with the format rules defined by each state agency. The error message detail will contain the available formats.
* Applied for can only be set if the tax parameter has `can_be_applied_for=true`, but we also block updating the value of the tax parameter setting if it has `applied_for=true`. Likewise we block removing the `applied_for` flag unless also updating the setting value.

## Updating and Overriding Tax Parameter Settings

Sometimes we will need to update and/or override previously set tax parameter settings. This could be to correct errors or to change values with different effective start dates.

The following example shows how we would override the previous setting whose value was incorrectly entered as `1.75` and effective start of `1900-01-01`, to a correct value of `2.75`.

```curl
curl -X PATCH \
  https://sandbox.checkhq.com/company_tax_params/com_8BDDxUvOZcFVeiuAGne8 \
  -H 'Authorization: Bearer YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '[
        {
          "id":"spa_W2kGF6lFM69FuuuyWyEn",
          "value": "2.75",
          "effective_start": "1900-01-01",
        }
      ]'
```

**EXAMPLE RESPONSE**

```json
{
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "spa_W2kGF6lFM69FuuuyWyEn",
      "label": "California Employer Unemployment Tax Rate",
      "description": "California Employer Unemployment Tax Rate",
      "name": "california_employer_unemployment_rate",
      "type": "percent",
      "options": null,
      "depends_on": null,
      "editable": true,
      "effective_datable": true,
      "can_be_applied_for": false,
      "jurisdiction": "jur_mRpDYFyFSUD1ArZdrMis",
      "tax": "tax_afRJqY785WwYH0PrtFde",
      "submitter": "company",
      "setting": {
        "applied_for": null,
        "value": "2.75",
        "effective_start": "1900-01-01",
      }
    },
    ...,
  ]
}
```

Following this example it follows that in order to override a setting, one must update it with the same effective start date.

If, on the other hand, we wanted to create a new setting with a value of `3.93` that we know will be effective starting on `2022-08-01` we can run the following example.

```curl
curl -X PATCH \
  https://sandbox.checkhq.com/company_tax_params/com_8BDDxUvOZcFVeiuAGne8 \
  -H 'Authorization: Bearer YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '[
        {
          "id":"spa_W2kGF6lFM69FuuuyWyEn",
          "value": "3.93",
          "effective_start": "2022-08-01",
        }
      ]'
```

**EXAMPLE RESPONSE**

```json
{
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "spa_W2kGF6lFM69FuuuyWyEn",
      "label": "California Employer Unemployment Tax Rate",
      "description": "California Employer Unemployment Tax Rate",
      "name": "california_employer_unemployment_rate",
      "type": "percent",
      "options": null,
      "depends_on": null,
      "editable": true,
      "effective_datable": true,
      "can_be_applied_for": false,
      "jurisdiction": "jur_mRpDYFyFSUD1ArZdrMis",
      "tax": "tax_afRJqY785WwYH0PrtFde",
      "submitter": "company",
      "setting": {
        "applied_for": null,
        "value": "3.93",
        "effective_start": "2022-08-01",
      }
    },
    ...,
  ]
}
```

We can see how this time both the value and the effective start date changed.

## Listing tax parameter settings

It is common  for tax parameter settings to be set more than once throughout the lifetime of the company or employee. There are times where we will need to update settings multiple times, but still need access to be able to check the previously set values. In order to do so we expose a `/setting` sub-resource.

The following example defines how we would be able to get the applicable tax parameter settings from the same company that operates in California containing the list of setting values that we’ve created thus far.

```curl
curl -X GET \
  https://sandbox.checkhq.com/company_tax_params/com_8BDDxUvOZcFVeiuAGne8/settings \
  -H 'Authorization: Bearer YOUR_API_KEY'
```

**EXAMPLE RESPONSE**

```json
{
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "spa_W2kGF6lFM69FuuuyWyEn",
      "jurisdiction": "jur_mRpDYFyFSUD1ArZdrMis",
      "applied_for": null,
      "value": "3.93",
      "effective_start": "2022-08-01",
      "settings": [
        {
          "value": "3.93",
          "effective_start": "2022-08-01",
          "created_at": "2022-08-01T00:00:00Z"
        },
        {
          "value": "2.75",
          "effective_start": "1900-01-01",
          "created_at": "2021-01-15T00:00:00Z"
        },
      ]
    },
    ...,
  ]
}
```

From the above example we can see both settings, which are ordered by their effective start in descending order.

The following example defines another way for getting a tax parameter setting, with the caveat that this time we can specify the tax parameter setting object that we want to return, hence only returning a single object.

```curl
curl -X GET \
  https://sandbox.checkhq.com/company_tax_params/com_8BDDxUvOZcFVeiuAGne8/settings/spa_W2kGF6lFM69FuuuyWyEn \
  -H 'Authorization: Bearer YOUR_API_KEY'
```

**EXAMPLE RESPONSE**

```json
{
  "id": "spa_W2kGF6lFM69FuuuyWyEn",
  "jurisdiction": "jur_mRpDYFyFSUD1ArZdrMis",
  "applied_for": null,
  "value": "3.93",
  "effective_start": "2022-08-01",
  "settings": [
    {
      "value": "3.93",
      "effective_start": "2022-08-01",
      "created_at": "2022-08-01T00:00:00Z"
    },
    {
      "value": "2.75",
      "effective_start": "1900-01-01",
      "created_at": "2021-01-15T00:00:00Z"
    },
  ]
}
```

## Listing tax parameter jurisdictions

In some cases we will want to filter down the list of tax setup params into more manageable responses. To that end we have the option of adding a jurisdiction as a query param to all of our list endpoints to filter the response by jurisdiction.

The following example shows how to filter by jurisdiction.

```curl
curl -X GET \
  https://sandbox.checkhq.com/company_tax_params/com_8BDDxUvOZcFVeiuAGne8?jurisdiction=jur_mRpDYFyFSUD1ArZdrMis \
  -H 'Authorization: Bearer YOUR_API_KEY'
```

We also have access to the full list of available jurisdictions for any company or employee. The following example defines how we would list the applicable tax parameter jurisdictions for a company.

```curl
curl -X GET \
  https://sandbox.checkhq.com/company_tax_params/com_8BDDxUvOZcFVeiuAGne8/jurisdictions \
  -H 'Authorization: Bearer YOUR_API_KEY'
```

**EXAMPLE RESPONSE**

```json
{
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "jur_mRpDYFyFSUD1ArZdrMis",
      "label": "California"
    },
    {
      "id": "jur_oFIe7BAqBbaz4tB6bcfV",
      "label": "Federal"
    },
  ]
}
```

The reason why this response contains two items; Federal as well as the expected California jurisdiction is that we will always return the taxes available in the Federal jurisdiction as well, unless we are specifically filtering on another jurisdiction.