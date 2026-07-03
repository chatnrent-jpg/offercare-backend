> ## Documentation Index
> Fetch the complete documentation index at: https://docs.checkhq.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Courtesy Withholdings

Courtesy withholding is when an employer withholds and remits a tax when they are not legally obligated to do so, as a courtesy for an employee to avoid he or she needing to pay a large sum in their personal tax return.

Check supports courtesy withholdings in several different tax scenarios, which are defined below. Courtesy withholding is not enabled by default in Check, and must be enabled for each employee by setting a *company-defined attribute* for the employee, which you can read more about in [Collecting Employee Information from Employers](https://docs.checkhq.com/docs/collecting-employee-information-from-employers).

## Ohio City Taxes

In Ohio, employers are required to withhold Ohio City Taxes for employees in the cities in which they work, but not where they live. Withholding an employee's residence Ohio City Tax is considered a courtesy withholding.

To enable courtesy withholding of resident Ohio City Taxes, a company must set the `courtesy_withhold_oh_city_taxes` parameter for each Ohio resident employee.

## Pennsylvania Earned Income Taxes

Similar to Ohio City Taxes, employees in Pennsylvania are subject to an Earned Income Tax (EIT) based on both their residence and work municipalities. If a Pennsylvania residents work entirely out-of-state, then by default, their out-of-state wages are not counted towards the calculation of their resident EIT. Withholding the employee's resident EIT on wages earned out-of-state is considered a courtesy withholding.

To enable courtesy withholding of Pennsylvania Earned Income Taxes for residents working out of state, a company must set the `courtesy_withhold_pa_eits` parameter for each Pennsylvania resident employee.

## Oregon Local Taxes

In Oregon, there are three (3) local taxes that have a notion of courtesy withholdings. They are:

* Metro Supportive Housing Services (SHS) Tax - Applicable to residents of the Portland Metro area.
* Multnomah County Preschool For All (PFA) Tax - Applicable to residents of Multnomah County.
* Oregon Transit Tax - Applicable to residents of Oregon state.

For each of these taxes, by default, Check will only calculate and withhold the tax on wages earned in each respective jurisdiction. For example, a resident of Portland, OR will only have Metro SHS Tax calculated on wages earned in the Portland Metro area. Withholding these taxes for residents on *all* wages earned, regardless of their workplace location, is considered a courtesy withholding for each of these taxes.

This setting is enabled with the company-defined attribute, `courtesy_withhold_or_locals`, for residents of any of these Oregon jurisdictions.