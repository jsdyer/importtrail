# Import Trail

<!-- coolcode:guide -->
Search a product, company, city or HS code to explore Canada’s annual major-importer lists. Each product opens a shareable report with a national directory, separate lists for each published country of origin and earlier trade years. Selected reports also show ISED’s cumulative import values and shares. The source check runs monthly and builds use the last verified workbooks.
<!-- /coolcode:guide -->

[Open Import Trail](https://coolcode.ca/importtrail/) · [Browse reports](https://coolcode.ca/importtrail/records/) · [Green coffee beans](https://coolcode.ca/importtrail/records/hs-090111/)

## Using the directory

The first release covers 24 HS6 classifications across food and drink, electronics, clothing, household goods, recreation and transport. Open any card to read the exact classification and trade year. Search runs locally and accepts product names, HS codes, companies, cities and origin labels in the selected products. Choose a trade year on a report to compare published listings. The directory, origin disclosures, tables and year links work with JavaScript disabled.

For green coffee beans (HS 090111), ISED’s 2024 cumulative concentration table reports 13 major importers accounting for CAD 1,246,106,976, or 79.36% of CAD 1,570,246,910. In the national list, Swiss Water is listed in Burnaby, British Columbia. The 2023 national workbook lists 11 entries. The report links to Maple Label for a different question about the origin claims on coffee packaging.

## Sources and interpretation

Innovation, Science and Economic Development Canada (ISED) produces the annual Canadian Importers Database. The initial editions are [2024](https://open.canada.ca/data/en/dataset/e5eae1d4-687c-4db2-9273-a8d2d711144c) and [2023](https://open.canada.ca/data/en/dataset/873cfcb0-1c9b-4a48-a366-076697069bb9). Contains information licensed under the [Open Government Licence – Canada](https://open.canada.ca/en/open-government-licence-canada). See [ISED’s methodology](https://ised-isde.canada.ca/site/ised/en/canadian-importers-database/frequently-asked-questions).

- The national table comes from the *Major Importers by HS6* workbook. Country lists come from the separate *Major Importers by HS6, country* workbook, which explicitly records both product and country for each entry.
- Import Trail deduplicates exact company, city and province/state tuples within each list. ISED can list brokers and non-resident importers. A business address identifies the importer’s location. The country field identifies the recorded origin of the goods. The same firm can appear under several origins.
- ISED identifies major importers collectively accounting for up to 80% of imports, subject to confidentiality rules. Where the national workbook contains no entries, the report says so. A zero entry count gives no estimate of import value.
- Concentration comes from the national HTML product report for the matching trade year. Canadian dollars and shares refer to cumulative groups. The source provides no individual firm amounts, ranks for the alphabetically listed firms, or retail-brand supply relationships.
- The description workbook supplies classification text. For some 2023 codes, the publisher supplies importer rows but omits the classification from its description workbook. Import Trail includes those rows and identifies the classification using its plain-language label.
- Each report links to its edition and component files. The [source receipt](https://coolcode.ca/importtrail/data/editions.json) lists publisher URLs and SHA-256 hashes for each retained edition’s workbooks. Each report offers a compact JSON download. Its `firms` array holds name, city and province/state. Integer entries in `national` and `origins` index that same year’s array starting at zero. Each concentration row holds the cumulative importer count, CAD value, and percentage, with a null count marking all importers.

## Refresh and publication

The source collection runs on the seventh of each month at **10:47 UTC**, or on demand from **Actions → Check Canadian importer editions → Run workflow**. GitHub can delay the scheduled start. The collector finds the two newest dated ISED editions, verifies the licence and data columns, downloads both sets of workbooks and checks the configured concentration reports against the current trade year. It preserves older editions previously captured. An incompatible workbook or changed report year fails the check before replacing verified snapshots. The source check date and trade year appear separately on the site.

The scheduled workflow saves validated data and explicitly dispatches the Pages workflow. Pages builds offline from the repository, runs unit and browser checks, and deploys successful main-branch builds. A failed build leaves the previous deployment available. The independent CoolCode watchdog can inspect [source status](https://coolcode.ca/importtrail/data/status.json). Its `checked_at` is the UTC time of the last successful source collection, `latest_year` is the newest observed trade year and `product_count` counts configured products. The separate weekly schedule guard covers `refresh.yml`.

## Expand or customize

1. In `config/products.json`, add the six-digit HS6 code as a string, preserving any leading zero. Its value is a pair containing the display name and directory sector. Sector filters are generated from this file.
2. To include national cumulative import values, add the same code to `config/concentration.json` after confirming that ISED’s current product report contains a market concentration table. Other products still receive full name and origin reports.
3. Install the collection dependencies and refresh from ISED. The two most recent releases are checked, with previously stored older years preserved. A missing code in the newest edition prompts a classification review.
4. Run the build and tests below. Review and commit `config/` and `data/` to main to publish the new pages, or dispatch the source workflow after your configuration is merged. Product pages, filters, downloadable summaries and the child sitemap follow verified data automatically.

```sh
python -m pip install -r collectors/requirements.txt
python collectors/refresh.py
node --test tests/*.test.mjs
python -m unittest discover -s tests -v
python scripts/build.py
python -m pip install -r tests/browser-requirements.txt
python -m playwright install chromium
python tests/browser_smoke.py
python -m http.server 8000 --directory dist
```

The build and unit tests require Python 3.11+ and Node for the search tests. Only source collection needs openpyxl and lxml. Search queries are filtered locally and reflected in the browser address for sharing. Opening or reloading a shared filtered URL transmits that URL to the hosting service. The application does not store searches or request an account.
