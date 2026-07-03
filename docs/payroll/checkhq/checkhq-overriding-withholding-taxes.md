> ## Documentation Index
> Fetch the complete documentation index at: https://docs.checkhq.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Overriding Withholding Taxes

Override Federal and State Income Taxes to desired amounts on individual pay runs.

In some cases, employers and employees may request a specific tax amount to be withheld for federal and state income tax, rather than the amount that would normally be calculated based on their W-4 elections. These situations can be supported in Check using the concept of **Tax Overrides**.

Tax overrides let you replace Check's calculated income tax withholding on an individual payroll item with an exact amount you specify. They are supported for **Federal Income Tax (FIT)** and **State Income Taxes (SIT)** only.

This guide will outline when and how to create tax overrides, and the API edge cases to consider in your integration.

## When to use tax overrides

The amount withheld for Federal and State Income Taxes is determined by the employee's withholding elections, which are provided on the federal Form W-4 and all of the state-level equivalent forms. In Check, these elections can be managed by the [Employee Withholding Setup](https://docs.checkhq.com/reference/employee-withholdings-setup) component, or the [Employee Tax Parameters API](https://docs.checkhq.com/reference/employee-tax-parameters).

Tax overrides, on the other hand, only affect withholding amounts on an individual payday. When set, a tax override will cause Check to completely ignore the employee's withholding elections for the overridden tax, and will withhold the override amount provided instead.

In other words:

* If the employee wants to change their withholdings on an ongoing basis, **they should update their withholding elections**.
* If the employee wants to change their withholding on a specific, individual payroll, **they should set a tax override on that payroll item**.

## Creating tax overrides

Tax overrides are set through a `tax_overrides` array on the [Payroll Item API](https://docs.checkhq.com/reference/the-payroll-item-object). For example:

```json Tax Overrides
{
    "id": "itm_yvmmsVGFxLoBaMIkqzea",
    "payroll": "pay_Z26PNMC7Ky1wfFQzVqfF",
    "employee": "emp_zGGp6wYcxAeu1Ng8IA7v",
    "status": "draft",
    "tax_overrides": [
      {
        "tax": "tax_8L3JLfsH4X6dp0maBWfW",
        "amount": 100
      }
    ],
    ...
}
```

Every tax override requires these two fields:

* `tax`: the public ID of the tax to override. Only **Federal Income Tax (FIT)** and **State Income Taxes (SIT)** are eligible. Any other tax (FICA, FUTA, SUI, local taxes, etc.) is rejected at update time — see [Errors](#errors).
* `amount` : the amount that should be withheld on the payroll item.

Only Federal Income Tax and State Income Taxes can be included in the `tax` field on a tax override. To populate a dropdown of these taxes for employers in your payroll product, you can limit the options to just the taxes that may be calculated on the payroll item by following these steps:

* Compile all of the unique states from the workplaces on which the employee has earnings on the payroll item, then
* Use the [List Taxes endpoint](https://docs.checkhq.com/reference/list-taxes) to fetch the IDs of the State Income Taxes for those states, with a request such as the following:
  ```shell
  curl -X GET 'https://sandbox.checkhq.com/taxes?label_contains=State Tax&jurisdiction=ca&jurisdiction=or'
  ```
* Add Federal Income Tax, which has a ID of `tax_8L3JLfsH4X6dp0maBWfW` .

> 📘
>
> The full catalog of taxes and their IDs is available from the [List Taxes endpoint](https://docs.checkhq.com/reference/list-taxes) (the taxes API). Use it to look up the `tax` ID for any Federal or State Income Tax you want to override.

## API warnings and errors

Below are the possible edge cases when using tax overrides, which will surface as warnings or errors.

### Warnings

| Level   | Warning code               | When it fires                                                                                           |
| ------- | :------------------------- | ------------------------------------------------------------------------------------------------------- |
| Payroll | `tax_override_not_applied` | An override targets a tax that Check didn't calculate for that employee, so the override had no effect. |

Tax overrides are only applied on taxes that would have *normally* been calculated on that payroll item for the employee. In other words, you cannot use tax overrides to force a new tax to be withheld.

In the case when a tax override is configured for a tax that is not calculated on the payroll item, a payroll warning will be returned that indicates that certain tax overrides were skipped.

```json
{
  "id": "pay_123",
  "warnings": [
    {
      "code": "tax_override_not_applied",
      "reason": "tax_override_targets_non_applicable_tax",
      "reason_description": "Tax overrides for some employees (emp_a1b2c3, emp_d4e5f6) target a tax that does not apply to them, so the override had no effect on the calculated taxes."
    }
  ]
}
```

***

| Level        | Warning code        | When it fires                                                                                                                      |
| ------------ | :------------------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| Payroll Item | `partially_applied` | The amount withheld for a tax is less than the override amount due to insufficient subject pay (`reason` = `exceeds_subject_pay`). |

In general, it is possible for deduction amounts to be partially applied or skipped entirely in cases when the employee has insufficient available earnings to cover the total deductions (for example, if a large portion of their gross earnings are imputed income or cash tips). In these cases, a [Payroll item warning](https://docs.checkhq.com/update/reference/warnings) is returned for each deduction that is `partially_applied` or `skipped`. For more information, see [Handling negative net pay](https://docs.checkhq.com/docs/handling-negative-net-pay).

For tax overrides specifically, there is an additional validation that is applied that may affect deduction amounts in rare edge cases; namely, the tax amount may not exceed the available subject pay for the tax. When this validation is triggered, a Payroll item warning is also created, this time with a different `reason` value of `exceeds_subject_pay`:

```json
{
  "id": "itm_123",
  "warnings": [
    {
      "code": "partially_applied",
      "reason": "exceeds_subject_pay",
      "deduction_type": "tax",
      "deduction": "tax_123",
      "actual_deduction_amount": "100.00",
      "expected_deduction_amount": "150.00"
    }
  ]
}
```

### Errors

Eligibility and shape are validated when you write the payroll item, and failures come back in the standard field-attributed `input_errors` shape:

| Condition                              | Field    | Message                                                                                                          |
| -------------------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------- |
| Tax is not Federal or State Income Tax | `tax`    | `Tax overrides are only allowed for Federal Income Tax and State Income Taxes. Tax {public_id} is not eligible.` |
| Missing `tax`                          | `tax`    | `Tax overrides must include a tax.`                                                                              |
| Missing `amount`                       | `amount` | `Tax overrides must include an amount.`                                                                          |
| Negative `amount`                      | `amount` | Standard minimum-value validation error (`amount` must be `>= 0`).                                               |

<br />