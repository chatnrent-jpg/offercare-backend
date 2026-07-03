> ## Documentation Index
> Fetch the complete documentation index at: https://docs.checkhq.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Multi-State Withholdings

Paying employees who live and work in different states.

In some scenarios, paying employees who live and work in different states may actually be quite complex due to the multi-state taxation laws and reciprocal agreements of states. Check’s API shoulders this complexity and makes these scenarios easy to understand and build against.

This guide will walk through how Check handles multi-state taxation.

## Multi-state Withholdings

Multi-state taxation arises when both the work and home state place a set of withholding requirements on the employee as either a resident or non-resident. With multi-state taxation, the employee’s wages are always subject to taxes in the work state (non-resident), but can also be subject to taxes in the home state (resident). Taxation in these cases is also dependent upon nexus – a company’s business presence in each of the states. This often results in the employee needing to complete withholding certificates (state W-4s) for both the work and home state. These forms, coupled with the state’s withholding rates, will determine how much tax is withheld for each set of taxes.

> 📘 How nexus is determined
>
> In Check, a company has nexus in a state if they have an active workplace in that state *or* if they have an employee opted into reciprocity in the state. This is described in more detail in the [Reciprocity](#reciprocity) section.

Check’s API accounts for multi-state logic and returns the correct forms an employee needs to complete in these scenarios. Below is an example of a request to [List employee forms](https://docs.checkhq.com/reference/list-employee-forms) in a multi-state scenario in action.

Take a company with workplaces in New York and New Jersey and an employee of that company living in New York and working at New Jersey workplace:

```curl List workplaces request
curl GET https://sandbox.checkhq.com/workplaces?company=com_P7JPeBhb8hH23iiReDQ5
```

```json List workplaces response
[
  {
    "id": "wrk_oRgjEaRycoCPuS5TqVkm",
    "name": "New York Office",
    "address": {
      "line1": "200 Park Ave",
      "line2": null,
      "city": "New York",
      "state": "NY",
      "postal_code": "10166",
      "country": "US"
    },
    "company": "com_P7JPeBhb8hH23iiReDQ5",
    "active": true,
    "metadata": {}
  },
  {
    "id": "wrk_CBsVFaGEpEaPBGIvJ6xi",
    "name": "New Jersey Office",
    "address": {
      "line1": "49 Washington St",
      "line2": null,
      "city": "Newark",
      "state": "NJ",
      "postal_code": "07102",
      "country": "US"
    },
    "company": "com_P7JPeBhb8hH23iiReDQ5",
    "active": true,
    "metadata": {}
  }
]
```

```curl Get an employee request
curl GET https://sandbox.checkhq.com/employees/emp_zGGp6wYcxAeu1Ng8IA7v
```

```json Get an employee response
{
  "id": "emp_zGGp6wYcxAeu1Ng8IA7v",
  "first_name": "Gregory",
  "last_name": "House",
  "middle_name": null,
  "email": "greg@house.org",
  "dob": "1959-06-11",
  "bank_accounts": [],
  "ssn_last_four": "9876",
  "payment_method_preference": "manual",
  "active": true,
  "onboard": {
    "status": "completed",
    "blocking_steps": [],
    "remaining_steps": []
  },
  "workplaces": ["wrk_CBsVFaGEpEaPBGIvJ6xi"],
  "company": "com_P7JPeBhb8hH23iiReDQ5",
  "start_date": "2020-01-13",
  "default_net_pay_split": "nps_cr642hx3546agdcgqD5b",
  "residence": {
    "line1": "20 W 34th St",
    "line2": null,
    "city": "New York",
    "state": "NY",
    "postal_code": "10001",
    "country": "US"
  },
  "w2_electronic_consent_provided": false,
  "metadata": {}
}
```

A call to [List employee forms](https://docs.checkhq.com/reference/list-employee-forms) for this employee would return both the New York and New Jersey withholding forms. An example API request and response are below.

```curl List employee forms request
curl GET https://sandbox.checkhq.com/employees/emp_zGGp6wYcxAeu1Ng8IA7v/forms
```

```json List employee forms response
{
    "next": null,
    "previous": null,
    "results": [
      {
        "form": {
          "id": "frm_EGFrW2qsMAqIysI1Bpzw",
          "description": "Federal W-4",
          "link": "https://www.irs.gov/pub/irs-pdf/fw4.pdf",
          "revision_date": "2022-01-03"
        },
        "document": null,
        "submitted_at": null,
        "submitted_form_id": null
      },
      {
        "form": {
          "id": "frm_tVAOrCpYupMwCbWNqB1h",
          "description": "New Jersey NJ-W4",
          "link": "https://www.state.nj.us/treasury/taxation/pdf/current/njw4.pdf",
          "revision_date": "2021-01-01"
        },
        "document": null,
        "submitted_at": null,
        "submitted_form_id": null
      },
      {
        "form": {
          "id": "frm_lXRcZI9SQxMrlHW1BAeI",
          "description": "New York IT-2104",
          "link": "https://www.tax.ny.gov/pdf/current_forms/it/it2104_fill_in.pdf",
          "revision_date": "2022-01-01"
        },
        "document": null,
        "submitted_at": null,
        "submitted_form_id": null
      }
    ]
  }
```

> 📘 When there's not nexus
>
> If a company does not have nexus in an employee's home state, [List employee forms](https://docs.checkhq.com/reference/list-employee-forms) would only return the employee's work state withholding forms. Any tax liability the employee would have in their home state would not be withheld through payroll. The employee would be responsible for paying that liability when filing their home state tax return.

> 📘 Overriding multi-state withholding calculation
>
> When an employee lives and works in more than one state, you will see a [company-defined attribute](https://docs.checkhq.com/docs/collecting-employee-information-from-employers#retrieving-and-updating-company-defined-attributes) for them called `withhold_resident_state_tax_only`. This is an optional parameter (defaults to False) that overrides multi-state income tax withholding to **only withhold income tax in the employee's resident state**.
>
> There are a variety of situations when an employer / employee might want to use this option. For example, certain states have a minimum threshold of wages or days worked in the state for non-residents to be subject to income tax. An employee who does not meet this threshold may want to use this option to avoid filing a tax return in the work state.
>
> It is important for users to consider the employee's tax situation carefully before using this option, to ensure they are remain compliant with payroll laws.

## "Localization of Work" Taxes

In addition to withholding taxes, other taxes such as State Unemployment Insurance (SUI) taxes also require special consideration when an employee is living and working across multiple states.

Contributions to these taxes should be made to the state in which the employee would expect to claim benefits (e.g., unemployment benefits in the case that he or she becomes unemployed, or worker's compensation benefits in the case that he or she sustains a work-related injury). So if an employee is living and working across multiple states, the employer and the employee **must designate the state to which these taxes should be paid.**

In Check, **this designation is made by selecting the employee's primary workplace**. All employees in Check are assigned workplaces, and one of those workplaces is designated as the employee’s primary workplace. If an employee is only assigned one workplace, then that workplace is automatically set as the employee’s primary workplace; otherwise, this selection needs to be made manually.

The state of the employee's primary workplace will dictate which SUI tax is withheld, as well as other taxes that follow these same "localization of work" provisions (for example, PA Earned Income Taxes, and many Paid Family Medical Leave and Worker's Compensation programs). In addition, setup parameters for these taxes (e.g., for the employer's unemployment insurance account number) will be prompted once any of their employees sets their primary workplace in that state.