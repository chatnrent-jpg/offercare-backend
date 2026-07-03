> ## Documentation Index
> Fetch the complete documentation index at: https://docs.checkhq.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Defining Workplaces

Setting Workplaces for payroll taxes, authorization forms, and reporting agencies

Employee earnings are almost always taxed based on the location where work occurs, which is represented by the Workplace resource.

A company can have many workplaces, which are often distinct from the company’s headquarters. For example, a coffee shop chain will generally have just one headquarters, but will have many workplaces (one for each location where employees earn wages).

Workplaces determine the taxes to withhold and pay, authorization forms to sign, and the government agencies to report to. Consequently, assigning workplaces to companies and employees is critical to the accurate calculation of payroll.

## Create Workplaces

First, create workplaces for your employees. These workplaces determine where employees can receive earnings. They also determine the taxes the company is liable to collect, pay, and report. Finally, company workplaces allow Check Onboard to ask for the exact set of information needed to file taxes in all jurisdictions the company has employees working in (state EINs or authorization forms, for example).

After you create a company, you should associate workplaces with it:

```curl Create a company workplace
curl -XPOST https://sandbox.checkhq.com/workplaces -d '{
  "address": {
    "line1": "123 Main St.",
    "city": "New York",
    "state": "NY",
    "postal_code": "10012"
  },
  "company": "com_axzjqzC5oOZ51h3mqmXK"
}'
```

## Assign Workplaces to Employees

**Then, assign workplaces to employees.** These workplaces determine the set of taxes calculated for each employee, and the state-specific withholding configuration needed to accurately calculate taxes.

You can associate workplaces with employees at employee creation or update:

```curl Create an employee
curl -XPOST https://sandbox.checkhq.com/employees -d '{
  "first_name": "Tony",
  "last_name": "Stark",
  "company": "com_axzjqzC5oOZ51h3mqmXK",
  "workplaces": ["wrk_9tb1CAiAu6fwNKxwxbcA", "wrk_ggrAYRGiZm95iwe97Xnf"],
  ...
}'
```

A workplace can be marked as active or inactive. Inactive workplaces may not be assigned to an employee, and active workplaces associated with an employee may not be deactivated. Inactive workplaces are not considered when computing `onboard_status` for a company.

> 🚧
>
> As new workplaces are added to a company or employee, they may affect the `onboard_status` of companies or employees.  For example, if a company adds a workplace in a new state, new information for that state will need to be collected before payrolls can be processed that pay employees who receive earnings at that workplace. If the new workplace is marked as inactive, it will not affect `onboard_status` of the company.

**An employee receives earnings at one or more of their workplaces.** When you create a payroll item for an employee, you can add earnings that were earned at any of the employee’s workplaces. This allows you the flexibility to pay an employee for work in multiple locations, all in the same payroll.

```curl Create a payroll
curl -XPOST https://sandbox.checkhq.com/payrolls -d '{
  "company": "com_axzjqzC5oOZ51h3mqmXK",
  "period_start": "2020-07-04",
  "period_end": "2020-07-17",
  "payday": "2020-07-24",
  "items": [
    {
      "employee": "emp_EyCIILuq69s5nFD5juGk",
      "earnings": [
        {
          "type": "regular",
          "amount": "1000.00",
          "hours": 40,
          "workplace": "wrk_9tb1CAiAu6fwNKxwxbcA"
        },
        {
          "type": "regular",
          "amount": "1200.00",
          "hours": 40,
          "workplace": "wrk_ggrAYRGiZm95iwe97Xnf"
        }
      ]
    }
  ]
}'
```

**It is the company's decision to assign workplaces.** Given the tax and legal implications of assigning workplaces, how workplaces are assigned is a decision to be made by the company.  For companies coming from an existing payroll provider, workplaces will generally remain consistent.

## Select a Primary Workplace

**Select an assigned workplace to be the employee's primary workplace**. This is also done as part of employee creation or update:

```curl Create an employee
curl -XPOST https://sandbox.checkhq.com/employees -d '{
  "first_name": "Tony",
  "last_name": "Stark",
  "company": "com_axzjqzC5oOZ51h3mqmXK",
  "workplaces": ["wrk_9tb1CAiAu6fwNKxwxbcA", "wrk_ggrAYRGiZm95iwe97Xnf"],
  "primary_workplace": "wrk_9tb1CAiAu6fwNKxwxbcA"
  ...
}'
```

If an employee is created with only one assigned workplace, that workplace will be automatically set as the employee's primary workplace. If a primary workplace is not assigned, then the employee's [onboard status](https://docs.checkhq.com/v2025-01-01/docs/onboard-status#onboard-status-for-employees) will be set to `blocking` until one is assigned.

Primary workplace has important implications for tax calculation, particularly for employees working across multiple states. State Unemployment Insurance (SUI) taxes, for example, are calculated **based on an employee's primary workplace**, not based on the workplace at which their wages were earned. For more information, go [here](https://docs.checkhq.com/v2025-01-01/docs/multi-state-taxation-and-reciprocity#localization-of-work-taxes).

## Update Workplaces

Workplace names and addresses can be updated through the [Workplace API](https://docs.checkhq.com/reference/update-a-workplace).

> 🚧 Updating a Workplace's address
>
> Updates to Workplace addresses are partially restricted in Check's API. This is because we do not allow updates that would create retroactive impact on employee taxes. For example, imagine that you create a Workplace in New York, pay an employee for work at that Workplace, and then modify the Workplace's address to be in Florida. It would be difficult for a user to understand when looking at reports after the fact why New York tax was withheld from the employee's earlier paycheck. To support this case in the real world, we recommend creating a new Workplace in Florida and assigning it to the Employee.
>
> Our API allows modifications to Workplace address that do not change the underlying tax location of the Workplace (for example, an address within the same city, or in some cases the same state). However, if our platform detects that you are trying to change the tax location of a Workplace it will raise an error.