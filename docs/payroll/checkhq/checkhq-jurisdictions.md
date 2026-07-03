> ## Documentation Index
> Fetch the complete documentation index at: https://docs.checkhq.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Jurisdictions

The canonical jurisdiction code used across Check's tax resources

A **jurisdiction** is a lowercase code used to group and filter Check's tax-related resources geographically. It is either `fed` (federal) or a lowercased [ISO 3166-2:US](https://en.wikipedia.org/wiki/ISO_3166-2:US) region code.

**Local taxes use their state's code.** A Pennsylvania borough's Local Services Tax has a `jurisdiction` of `pa`, so filtering taxes or agencies by `jurisdiction=pa` returns that state's **state and local** entries together.

For how jurisdictions relate to taxes and agencies, see the [Taxes, Agencies, and Jurisdictions](https://docs.checkhq.com/docs/taxes-and-agencies) guide.

## Jurisdiction codes

| Code  | Region               |
| ----- | -------------------- |
| `fed` | Federal              |
| `al`  | Alabama              |
| `ak`  | Alaska               |
| `az`  | Arizona              |
| `ar`  | Arkansas             |
| `ca`  | California           |
| `co`  | Colorado             |
| `ct`  | Connecticut          |
| `de`  | Delaware             |
| `dc`  | District of Columbia |
| `fl`  | Florida              |
| `ga`  | Georgia              |
| `hi`  | Hawaii               |
| `id`  | Idaho                |
| `il`  | Illinois             |
| `in`  | Indiana              |
| `ia`  | Iowa                 |
| `ks`  | Kansas               |
| `ky`  | Kentucky             |
| `la`  | Louisiana            |
| `me`  | Maine                |
| `md`  | Maryland             |
| `ma`  | Massachusetts        |
| `mi`  | Michigan             |
| `mn`  | Minnesota            |
| `ms`  | Mississippi          |
| `mo`  | Missouri             |
| `mt`  | Montana              |
| `ne`  | Nebraska             |
| `nv`  | Nevada               |
| `nh`  | New Hampshire        |
| `nj`  | New Jersey           |
| `nm`  | New Mexico           |
| `ny`  | New York             |
| `nc`  | North Carolina       |
| `nd`  | North Dakota         |
| `oh`  | Ohio                 |
| `ok`  | Oklahoma             |
| `or`  | Oregon               |
| `pa`  | Pennsylvania         |
| `ri`  | Rhode Island         |
| `sc`  | South Carolina       |
| `sd`  | South Dakota         |
| `tn`  | Tennessee            |
| `tx`  | Texas                |
| `ut`  | Utah                 |
| `vt`  | Vermont              |
| `va`  | Virginia             |
| `wa`  | Washington           |
| `wv`  | West Virginia        |
| `wi`  | Wisconsin            |
| `wy`  | Wyoming              |

## Canonicalization

Check is consolidating every resource onto this single canonical `jurisdiction` code — `fed` or a lowercased [ISO 3166-2:US](https://en.wikipedia.org/wiki/ISO_3166-2:US) region code.

### Why

Across Check's APIs, the same idea of a jurisdiction has been represented in several different ways, with identifiers that do not align from one resource to another — opaque `jur_` IDs in some places, uppercase abbreviations in others, and a bare `?state=` filter elsewhere. That makes it hard to reliably join or roll data up to a jurisdiction across resources.

Standardizing on one canonical code fixes that: a single, human-readable value means the same thing everywhere, so you can group filings, taxes, parameters, and elections by jurisdiction with confidence. It is also the foundation the newer reference resources ([Tax](https://docs.checkhq.com/reference/the-tax-object) and [Agency](https://docs.checkhq.com/reference/the-agency-object)) and future agency-referencing resources are built on.

### Impacted resources

The table below maps each legacy jurisdiction representation to its canonical replacement:

| Resource                                                        | Legacy representation                                   | Canonical replacement         |
| --------------------------------------------------------------- | ------------------------------------------------------- | ----------------------------- |
| Company / employee [tax elections](https://docs.checkhq.com/reference/the-tax-election-object) | `jur_` ID plus an uppercase `jurisdiction_abbreviation` | `jurisdiction` code           |
| [Tax parameters](https://docs.checkhq.com/docs/tax-parameters)                            | `jurisdiction` as a `jur_` ID                           | `jurisdiction` code           |
| [Reciprocity](https://docs.checkhq.com/docs/reciprocity) elections                        | `jur_` ID plus a non-standard `jurisdiction_name`       | `jurisdiction` code           |
| Applied-for tax params report                                   | bare uppercase string (e.g. `"AL"`)                     | `jurisdiction` code           |
| `company_tax_params/{id}/jurisdictions`                         | `{ id, label }` object shape                            | `jurisdiction` code           |
| Filings                                                         | `?state=` query filter                                  | `?jurisdiction=` query filter |

`Workplace.address_state` is **not** changing. It is the state of a physical address (an uppercase USPS code).

<Callout icon="🚧" theme="warn">
  Tax elections are the most sensitive case: their `jurisdiction` is a `jur_` ID, and many integrations join tax-election data to the tax catalog. If you depend on the legacy `jur_` IDs or uppercase abbreviations anywhere, flag it to your Check contact so we can sequence your migration.
</Callout>

### How the migration rolls out

Wherever possible, these changes are **additive** — a new canonical field appears. Where a representation actually changes, Check runs the canonical and legacy fields in parallel and coordinates the cutover with each partner before sunsetting the legacy form. This does not require a new API version. If you maintain an integration against any of the resources above, your Check contact will work with you to schedule the transition.