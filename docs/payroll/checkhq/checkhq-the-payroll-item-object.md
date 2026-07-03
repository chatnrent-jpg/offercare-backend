> ## Documentation Index
> Fetch the complete documentation index at: https://docs.checkhq.com/llms.txt
> Use this file to discover all available pages before exploring further.

# The payroll item object

Represents a payment to an employee from a company.

Payroll items are created during [payroll creation](https://docs.checkhq.com/reference/create-payroll), and may include multiple earnings, reimbursements, and other line items for a single payroll period.

Note only one payroll item is allowed per employee per payroll.

> **Shared enums:** The `status` field on this object uses the same set of values as the `status` field on the [Payroll](https://docs.checkhq.com/reference/the-payroll-object) object: `draft`, `pending`, `processing`, `failed`, `partially_paid`, or `paid`.

```json Sample payroll item object
{
    "id": "itm_yvmmsVGFxLoBaMIkqzea",
    "payroll": "pay_Z26PNMC7Ky1wfFQzVqfF",
    "employee": "emp_zGGp6wYcxAeu1Ng8IA7v",
    "status": "draft",
    "payment_method": "direct_deposit",
    "supplemental_tax_calc_method": "flat",
    "net_pay": null,
    "earnings": [
      {
        "amount": "1384.61",
        "hours": 40.0,
        "type": "salaried",
        "workplace": "wrk_qbCnBhUIDzduGrwLJ83p",
        "earning_code": null,
        "description": null,
        "metadata": {}
      }
    ],
    "reimbursements": [
      {
        "amount": "123.43",
        "code": null,
        "description": null
      }
    ],
    "pto_balance_hours": null,
    "sick_balance_hours": null,
    "state_covid_sick_balance_hours": null,
    "taxes": null,
    "benefits": null,
    "benefit_overrides": null,
    "post_tax_deductions": null,
    "post_tax_deduction_overrides": null,
    "tax_overrides": null,
    "warnings": null,
    "paper_check_number": null,
    "paystub_info": {},
    "metadata": {}
}
```

<Table align={["left","left"]}>
  <thead>
    <tr>
      <th>
        Attribute
      </th>

      <th>
        Description
      </th>
    </tr>
  </thead>

  <tbody>
    <tr>
      <td>
        `id`<br />_string_
      </td>

      <td>
        Unique identifier for the payroll item.
      </td>
    </tr>

    <tr>
      <td>
        `payroll`<br />_string_
      </td>

      <td>
        The payroll ID associated with the payroll item.
      </td>
    </tr>

    <tr>
      <td>
        `employee`<br />_string_
      </td>

      <td>
        The employee ID associated with the payroll item.
      </td>
    </tr>

    <tr>
      <td>
        `status`<br />_string_
      </td>

      <td>
        Status of the payroll item.

        One of `draft`, `pending`, `processing`, `failed`, `partially_paid`, or `paid`.
      </td>
    </tr>

    <tr>
      <td>
        `void_of`<br />_string_
      </td>

      <td>
        The ID of the payroll item this payroll item is voiding.

        Only applicable to voided items
      </td>
    </tr>

    <tr>
      <td>
        `voided_by`<br />_string_
      </td>

      <td>
        The ID of the payroll item this payroll item was voided by.

        Only applicable to voided items
      </td>
    </tr>

    <tr>
      <td>
        `payment_method`<br />_string_
      </td>

      <td>
        May be `manual` or `direct_deposit` if the employee has a linked bank account
      </td>
    </tr>

    <tr>
      <td>
        `supplemental_tax_calc_method`<br />_string_
      </td>

      <td>
        Controls the method used by Check to calculate tax on supplemental earnings. May be `flat` or `aggregate`
      </td>
    </tr>

    <tr>
      <td>
        `pto_balance_hours`<br />_float_
      </td>

      <td>
        The employee's remaining PTO hour balance, for display on the paystub. Can be updated even after the associated payroll has been approved.
      </td>
    </tr>

    <tr>
      <td>
        `sick_balance_hours`<br />_float_
      </td>

      <td>
        The employee's remaining sick hour balance, for display on the paystub. Can be updated even after the associated payroll has been approved.
      </td>
    </tr>

    <tr>
      <td>
        `state_covid_sick_balance_hours`<br />_float_
      </td>

      <td>
        The employee's remaining sick hour balance from state COVID relief bills, for display on the paystub. This field is currently only applicable to California employers as per [SB-95](https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202120220SB95). When the requirement expires, this field will be removed in a future API version
      </td>
    </tr>

    <tr>
      <td>
        `net_pay`<br />_string_
      </td>

      <td>
        Read only. The total amount of net pay earned by the employee for this payroll item. The formula for net pay is `gross pay - employee taxes - employee benefit contributions - imputed income - post-tax deductions + reimbursements`
      </td>
    </tr>

    <tr>
      <td>
        `net_pay_split`<br />_string_
      </td>

      <td>
        The net pay split ID associated with this payroll item.
      </td>
    </tr>

    <tr>
      <td>
        `earnings`<br />_array of objects_
      </td>

      <td>
        The set of earnings objects associated with the payroll item.
      </td>
    </tr>

    <tr>
      <td>
        `reimbursements`<br />_array of objects_
      </td>

      <td>
        The set of non-taxable reimbursements objects associated with the payroll item.
      </td>
    </tr>

    <tr>
      <td>
        `taxes`<br />_array of objects_
      </td>

      <td>
        Read only. An array of tax line items associated with the payroll item.

        Each tax object contains:

        - **tax** (_string_): Unique identifier for the tax.
        - **description** (_string_): Human-readable name of the tax (e.g., "Federal Income Tax", "Employer FICA Tax").
        - **amount** (_string_): Dollar amount of the tax.
        - **payer** (_string_): Who is responsible for the tax. One of `employee` or `company`.
      </td>
    </tr>

    <tr>
      <td>
        `benefits`<br />_array of objects_
      </td>

      <td>
        Read only. An array of benefit line items associated with the payroll item.

        Each benefit object contains:

        - **benefit** (_string_): ID of the [employee benefit](https://docs.checkhq.com/reference/the-employee-benefit-object).
        - **description** (_string_): Human-readable name of the benefit.
        - **employee\_amount** (_string_): Dollar amount of the employee's contribution.
        - **company\_amount** (_string_): Dollar amount of the company's contribution.
      </td>
    </tr>

    <tr>
      <td>
        `post_tax_deductions`<br />_array of objects_
      </td>

      <td>
        Read only. An array of post-tax deduction line items associated with the payroll item.

        Each post-tax deduction object contains:

        - **post\_tax\_deduction** (_string_): ID of the [post-tax deduction](https://docs.checkhq.com/reference/the-post-tax-deduction-object).
        - **description** (_string_): Human-readable name of the deduction.
        - **amount** (_string_): Dollar amount of the deduction.
      </td>
    </tr>

    <tr>
      <td>
        `benefit_overrides`<br />_array of objects_
      </td>

      <td>
        The set of [benefit override](https://docs.checkhq.com/docs/defining-benefits#overriding-benefits-for-a-single-payroll) objects associated with this payroll item.

        Each benefit override object contains:

        - **benefit** (_string_, required): ID of the employee benefit being overridden.
        - **employee\_contribution\_amount** (_string_): Updated employee contribution amount for this payroll only.
        - **company\_contribution\_amount** (_string_): Updated company contribution amount for this payroll only.
      </td>
    </tr>

    <tr>
      <td>
        `post_tax_deduction_overrides`<br />_array of objects_
      </td>

      <td>
        The set of [post-tax deduction override](https://docs.checkhq.com/docs/post-tax-deductions#overriding-post-tax-deductions-for-a-single-payroll) objects associated with this payroll item.

        Each post-tax deduction override object contains:

        - **post\_tax\_deduction** (_string_, required): ID of the post-tax deduction being overridden.
        - **amount** (_string_, required): Updated deduction amount for this payroll only.
      </td>
    </tr>

    <tr>
      <td>
        `tax_overrides`<br />_array of objects_
      </td>

      <td>
        The set of [tax override](https://docs.checkhq.com/docs/overriding-withholding-taxes) objects associated with this payroll item.

        Each tax override object contains:

        - **tax** (_string_, required): ID of the tax being overridden. Only Federal Income Tax and State Income Taxes are eligible.
        - **amount** (_string_, required): Updated withholding amount for this payroll only.
      </td>
    </tr>

    <tr>
      <td>
        `warnings`<br />_array of objects_
      </td>

      <td>
        Read only. An array of [warning](https://docs.checkhq.com/reference/payroll-item-warnings) objects associated with the payroll item.
      </td>
    </tr>

    <tr>
      <td>
        `paper_check_number`<br />_string_
      </td>

      <td>
        For accounting. The check number associated with any printed checks. Can be updated even after the associated payroll has been approved. See [Get a paper check](https://docs.checkhq.com/reference/get-a-paper-check) for more details.
      </td>
    </tr>

    <tr>
      <td>
        `paystub_info`<br />_object_
      </td>

      <td>
        Loosely structured key-value information that will be returned on paystubs generated for this payroll item. Limited to 15 keys, and 500 total characters (combined length of keys and values). Keys and values are both strings. Example: `{"Employee ID": "12345", "Department": "Engineering"}`.
      </td>
    </tr>

    <tr>
      <td>
        `metadata`<br />_object_
      </td>

      <td>
        Additional loosely structured information to associate with the payroll item.
      </td>
    </tr>
  </tbody>
</Table>

<br />