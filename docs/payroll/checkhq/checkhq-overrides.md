> ## Documentation Index
> Fetch the complete documentation index at: https://docs.checkhq.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Overrides

Adjust calculated benefit, post-tax deduction, and tax amounts on a single payroll without changing ongoing configuration.

When you run a payroll, Check calculates each employee's benefit contributions, post-tax deductions, and tax withholdings from their ongoing setup. Occasionally, an employer needs to change one of these amounts for a single pay run only — without altering the underlying configuration that drives future payrolls. **Overrides** exist for exactly this purpose.

Check supports three kinds of overrides, all of which follow the same model:

* **Benefit overrides** — change a benefit's contribution amount on one payroll.
* **Post-tax deduction overrides** — change a post-tax deduction amount on one payroll.
* **Tax overrides** — replace Check's calculated Federal or State income tax withholding on one payroll.

## How overrides work

Although they target different parts of the calculation, all three override types share the same shape and behavior:

* **They live on the payroll item.** Each override type is passed as an array on the [Payroll Item object](https://docs.checkhq.com/reference/the-payroll-item-object) (`benefit_overrides`, `post_tax_deduction_overrides`, and `tax_overrides`). You can set them at payroll create/update time or payroll item create/update time.
* **They apply to a single payroll only.** An override affects just the payroll item it is set on. The employee's ongoing benefit, deduction, and withholding setup is left untouched, so future payrolls calculate normally.
* **To make an ongoing change, update the underlying object instead.** If the change should persist across pay runs, update the benefit, post-tax deduction, or the employee's withholding elections directly rather than using an override.

In other words: reach for an override when an employer wants a one-time adjustment on a specific payroll, and update the underlying object when they want the change to stick.

## Benefit overrides

Use `benefit_overrides` to change a benefit's employee and/or company contribution amount on a single payroll:

```json
{
    "id": "itm_yvmmsVGFxLoBaMIkqzea",
    "benefit_overrides": [
        {
            "benefit": "ben_SZhG3uagj9u8b3M6vFKt",
            "employee_contribution_amount": "400.00",
            "company_contribution_amount": null
        }
    ]
}
```

For details, including negative overrides and year-to-date validation, see [Overriding Benefits for a single payroll](https://docs.checkhq.com/docs/defining-benefits#overriding-benefits-for-a-single-payroll).

## Post-tax deduction overrides

Use `post_tax_deduction_overrides` to change the amount deducted for a post-tax deduction on a single payroll:

```json
{
    "id": "itm_yvmmsVGFxLoBaMIkqzea",
    "post_tax_deduction_overrides": [
        {
            "post_tax_deduction": "ptd_BCaZ3uagj9u8b3M6vFKt",
            "amount": "400.00"
        }
    ]
}
```

For details, including negative overrides and year-to-date validation, see [Overriding post-tax deductions for a single payroll](https://docs.checkhq.com/docs/post-tax-deductions#overriding-post-tax-deductions-for-a-single-payroll).

## Tax overrides

Use `tax_overrides` to replace Check's calculated income tax withholding with an exact amount on a single payroll. Tax overrides are supported for **Federal Income Tax (FIT)** and **State Income Taxes (SIT)** only:

```json
{
    "id": "itm_yvmmsVGFxLoBaMIkqzea",
    "tax_overrides": [
        {
            "tax": "tax_8L3JLfsH4X6dp0maBWfW",
            "amount": 100
        }
    ]
}
```

For details, including eligibility rules and the warnings and errors to handle, see [Overriding Withholding Taxes](https://docs.checkhq.com/docs/overriding-withholding-taxes).

## Negative overrides and limits

Benefit and post-tax deduction overrides may be set to **negative** values — useful for correcting an amount that was over-applied on a previous payroll. When you use negative overrides, Check validates that the relevant year-to-date (YTD) total does not go below zero. See each guide above for the specific YTD rules (benefit overrides are validated per benefit type, while post-tax deduction overrides are validated per deduction).

Tax overrides behave a little differently: the `amount` must be `>= 0`, and the amount actually withheld is capped by the available subject pay for the tax. See [Overriding Withholding Taxes](https://docs.checkhq.com/docs/overriding-withholding-taxes) for the full set of warnings and errors.