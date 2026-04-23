# PDF intake folder

Drop source PDFs directly into this folder (or an archetype subfolder if you
want — either works).

## Naming convention

Use a short, stable slug-style name: `author_year_topic.pdf`. Examples:

```
worldbank_2024_remittance_prices.pdf
fdic_2023_unbanked_survey.pdf
fincen_2024_advisory_elder_exploitation.pdf
cfpb_2022_prepaid_card_report.pdf
mpi_2024_haitian_migrants.pdf
irs_2023_itin_statistics.pdf
bls_2024_contingent_workers.pdf
pew_2023_gig_economy.pdf
```

The slug becomes the `source_id` in `sources.json`, so pick something you're
happy to cite. ASCII only, no spaces, lowercase, underscores between parts.

## Optional: organize by archetype

If it's clearer, you can drop PDFs straight into subfolders:

```
datasets_v3/sources/pdfs/remittance/
datasets_v3/sources/pdfs/gig_worker/
datasets_v3/sources/pdfs/unbanked/
datasets_v3/sources/pdfs/itin/
datasets_v3/sources/pdfs/shared/    # FinCEN advisories, cross-cutting sources
```

Not required — if you drop everything flat, I'll route them after reading.

## What I'll do with each PDF

1. Register it in `datasets_v3/sources/sources.json` (title, authors, year,
   publisher, URL, `source_id` = the slug).
2. Extract page-keyed text to `datasets_v3/sources/extracts/<source_id>.json`
   so citations can reference page numbers and exact quotes.
3. Leave the PDF itself here untouched.