---
name: referentiedata
description: Help maintain VERA reference data in this repository.
---

# VERA Referentiedata

This repository manages VERA reference data in `Referentiedata.csv`. Do not treat it as contact data.

- Preserve the semicolon delimiter and the existing header and column order:
  `Soort;Code;Naam;Omschrijving;Begindatum;Einddatum;Parent;Informatiedomein`
- Never add, remove, or rename columns without an explicit request.
- Follow the repository README and `.github/scripts/validate_reference_data.py`.
- Preserve existing validation rules, including required `Soort` and `Code`, date formatting, and lifecycle rules.
- When editing rows, keep the CSV structure intact and validate the changes with the repository’s existing validation workflow.