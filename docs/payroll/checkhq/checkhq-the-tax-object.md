> ## Documentation Index
> Fetch the complete documentation index at: https://docs.checkhq.com/llms.txt
> Use this file to discover all available pages before exploring further.

# The Tax object

A Tax represents a specific payroll levy. Taxes are global reference data: read-only, identical across companies, and stable across environments.

A `Tax` is a levy that arises when running payroll, like Federal Income Tax, a state's unemployment insurance tax (SUI), or a local levy like a PA borough's Local Services Tax. Each tax carries a `jurisdiction` for filtering, its `payer` (whether the money is withheld from the employee or an employer cost), and dating for both the obligation itself and Check's support for calculation, remittance, and/or filing.

```json Tax
{
  "id": "tax_8L3JLfsH4X6dp0maBWfW",
  "label": "Federal Income Tax",
  "jurisdiction": "fed",
  "payer": "employee",
  "supported": true,
  "remittable": true,
  "effective_from": "1900-01-01",
  "effective_to": null
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
        `id`  
         _string_
      </td>

      <td>
        Unique identifier (`tax_` prefix).
      </td>
    </tr>

    <tr>
      <td>
        `label`  
         _string_
      </td>

      <td>
        Human-readable name for display.
      </td>
    </tr>

    <tr>
      <td>
        `jurisdiction`  
        _enum_
      </td>

      <td>
        Lowercase region code (`fed` or lowercased [ISO 3166-2:US](https://en.wikipedia.org/wiki/ISO_3166-2:US) region code). Used to group and filter other resources. Local taxes use their state's value.
      </td>
    </tr>

    <tr>
      <td>
        `payer`  
        _enum_
      </td>

      <td>
        Whose money pays the tax: `employee` (withheld) or `company` (employer cost)
      </td>
    </tr>

    <tr>
      <td>
        `supported`  
        _boolean_
      </td>

      <td>
        Whether Check calculates and reports (files) this tax. This does not imply Check remits it — see `remittable`.
      </td>
    </tr>

    <tr>
      <td>
        `remittable`  
        _boolean_
      </td>

      <td>
        Whether Check remits this tax to the agency on your behalf. Always `false` when `supported` is `false` (Check can’t remit a tax it doesn’t support); may also be `false` for supported taxes the employer self-remits (e.g. NY SDI paid to a private carrier).
      </td>
    </tr>

    <tr>
      <td>
        `effective_from`  
        _date_ | _null_
      </td>

      <td>
        First date (inclusive) the obligation exists. Treat it as an eventually consistent reference as agency information comes in. Very old taxes carry values of `1900-01-01`.
      </td>
    </tr>

    <tr>
      <td>
        `effective_to`  
        _date_ | _null_
      </td>

      <td>
        Last date (inclusive) the obligation applies; `null` while still in effect.
      </td>
    </tr>
  </tbody>
</Table>