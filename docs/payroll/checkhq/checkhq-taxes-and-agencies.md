> ## Documentation Index
> Fetch the complete documentation index at: https://docs.checkhq.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Taxes, Agencies, and Jurisdictions

How Check models payroll taxes, the agencies that administer them, and the jurisdictions they belong to

Payroll taxes involve three related concepts. Before working with Check's APIs, it helps to understand what each one is in the real world and how they connect.

* **Jurisdiction** — a geographic region — federal, a state, or a locality within a state — whose government imposes payroll taxes on employers operating there. It's the *where* of a tax, as opposed to the agency, which is the *who* you register, pay, and file with.
* **Agency** — the government body, or an administrator it appoints, that employers actually interact with: who you register with, remit payments to, and file returns with. Examples include the IRS, a state department of revenue, or a local collector such as Berkheimer in Pennsylvania.
* **Tax** — a specific levy owed within a jurisdiction, such as Federal Income Tax, a state's unemployment insurance tax (SUI), or a locality's Local Services Tax.

These connect in a natural hierarchy: within a **jurisdiction**, a government levies one or more **taxes**, and each tax is administered by an **agency**. A single agency often administers many taxes, and a jurisdiction can have several agencies — for example, a state revenue department for income tax withholding and a separate department for unemployment insurance. Employers never transact with a jurisdiction directly; they register, pay, and file with agencies.

Check exposes **Tax** and **Agency** as read-only reference resources, and uses **jurisdiction** as a consistent code for grouping and filtering them. Both resources are identical across companies and stable across environments.

## Jurisdictions

A jurisdiction is represented as a lowercase code:

* `fed` for the federal government.
* A lowercased [ISO 3166-2:US](https://en.wikipedia.org/wiki/ISO_3166-2:US) region code for a state, the District of Columbia, or a US territory — the two-letter postal code in lowercase (`ny`, `pa`, `ca`, `dc`).

A few behaviors are worth calling out:

* **Localities roll up to their state.** A local tax or agency carries the code of the state it sits in, so `pa` covers Pennsylvania's state-level *and* local entries.
* **The code is the same everywhere.** Every Check resource that needs a jurisdiction uses this same code, so you can group and filter consistently across resources.

See [Jurisdictions](https://docs.checkhq.com/docs/jurisdictions) for the complete list of codes. Check is consolidating every resource onto this single canonical code; if you currently rely on older jurisdiction representations such as `jur_` IDs, see [Canonicalization](https://docs.checkhq.com/docs/jurisdictions#canonicalization).

## Taxes

A `Tax` is a specific levy that can arise when running payroll. Each tax carries the jurisdiction it belongs to, who pays it, whether Check supports it, and dating for the obligation itself.

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

See [the Tax object](https://docs.checkhq.com/reference/the-tax-object) for the full field reference..

### Listing taxes

[List taxes](https://docs.checkhq.com/reference/list-taxes) (`GET /taxes`) returns the catalog, ordered with federal taxes first, then by `jurisdiction`, then by `label`. It supports these filters:

| Filter           | Description                                                                                                                                               |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`             | Tax ID to look up. Repeatable for batch lookups.                                                                                                          |
| `jurisdiction`   | Jurisdiction code to filter to. Repeatable; multiple values are OR'd. A state code returns that state's **state and local** taxes.                        |
| `supported`      | Filter by whether Check supports calculating and reporting the tax.                                                                                       |
| `remittable`     | Filter by whether Check remits the tax to an agency.                                                                                                      |
| `effective`      | Filter by whether the obligation is in effect today. Defaults to currently-effective taxes only; pass `effective=false` to list repealed or lapsed taxes. |
| `label_contains` | Case-insensitive substring match on `label`.                                                                                                              |
| `limit`          | Results per page (default 25, max 500).                                                                                                                   |

List every tax in Pennsylvania, state and local:

```curl
curl -X GET \
  'https://sandbox.checkhq.com/taxes?jurisdiction=pa' \
  -H 'Authorization: Bearer YOUR_API_KEY'
```

## Agencies

An `Agency` is the operational counterparty Check transacts with on filings and remittances.

```json Agency
{
  "id": "agc_ukjABgbD0hQ3dfBRyMPD",
  "label": "Internal Revenue Service",
  "jurisdiction": "fed"
}
```

See [the Agency object](https://docs.checkhq.com/reference/the-agency-object) for the full field reference. As described above, agencies are referenced from the resources where employers transact with them.

### Listing agencies

[List agencies](https://docs.checkhq.com/reference/list-agencies) (`GET /agencies`) supports `id`, `jurisdiction`, `label_contains`, and `limit`, with the same repeatable, ordering, and pagination behavior as taxes.

Look up an agency by name:

```curl
curl -X GET \
  'https://sandbox.checkhq.com/agencies?label_contains=berkheimer' \
  -H 'Authorization: Bearer YOUR_API_KEY'
```