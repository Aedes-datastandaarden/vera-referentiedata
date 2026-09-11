#!/usr/bin/env python3

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path


EXPECTED_FIELDS = {
    "Soort",
    "Code",
    "Naam",
    "Omschrijving",
    "Begindatum",
    "Einddatum",
}

DATE_FORMAT = "%d-%m-%Y"
DATE_FORMAT_DESCRIPTION = "DD-MM-JJJJ"


def parse_arguments():
    """
    Leest de argumenten waarmee het script wordt aangeroepen.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Vergelijk twee versies van het referentiedatabestand en "
            "valideer de levenscyclusregels voor begin- en einddatums."
        )
    )

    parser.add_argument(
        "--base-file",
        required=True,
        help=(
            "Het CSV-bestand uit de doelbranch van de Pull Request, "
            "bijvoorbeeld main."
        ),
    )

    parser.add_argument(
        "--current-file",
        required=True,
        help="Het gewijzigde CSV-bestand uit de Pull Request.",
    )

    return parser.parse_args()


def read_csv(file_path):
    """
    Leest een CSV-bestand en retourneert de regels als dictionary,
    waarbij Code als unieke sleutel wordt gebruikt.

    Ook worden de volgende structuurcontroles uitgevoerd:
    - het bestand bestaat;
    - de verwachte kolommen zijn aanwezig;
    - Code is gevuld;
    - Code is uniek.
    """

    path = Path(file_path)

    if not path.exists():
        raise ValueError(f"Bestand bestaat niet: {file_path}")

    rows_by_code = {}
    duplicate_codes = []

    with path.open(
        mode="r",
        encoding="utf-8-sig",
        newline="",
    ) as csv_file:
        reader = csv.DictReader(
            csv_file,
            delimiter=";",
        )

        if reader.fieldnames is None:
            raise ValueError(
                f"CSV-bestand bevat geen kolomkoppen: {file_path}"
            )

        actual_fields = {
            field.strip()
            for field in reader.fieldnames
            if field is not None
        }

        missing_fields = EXPECTED_FIELDS - actual_fields

        if missing_fields:
            raise ValueError(
                f"CSV-bestand '{file_path}' mist de volgende kolommen: "
                f"{', '.join(sorted(missing_fields))}"
            )

        for line_number, row in enumerate(reader, start=2):
            normalized_row = {
                key.strip(): value.strip() if value is not None else ""
                for key, value in row.items()
                if key is not None
            }

            code = normalized_row["Code"]

            if not code:
                raise ValueError(
                    f"Lege Code gevonden in '{file_path}' "
                    f"op regel {line_number}."
                )

            if code in rows_by_code:
                duplicate_codes.append(code)
                continue

            rows_by_code[code] = {
                "line_number": line_number,
                "data": normalized_row,
            }

    if duplicate_codes:
        unique_duplicates = sorted(set(duplicate_codes))

        raise ValueError(
            f"De volgende codes komen meerdere keren voor in "
            f"'{file_path}': {', '.join(unique_duplicates)}"
        )

    return rows_by_code


def parse_date(date_value, field_name, code, line_number, errors):
    """
    Converteert een ingevulde datum naar een datetime-object.

    Als de datum leeg is, wordt None teruggegeven.
    Als het formaat ongeldig is, wordt een validatiefout toegevoegd.
    """

    if not date_value:
        return None

    try:
        return datetime.strptime(date_value, DATE_FORMAT)
    except ValueError:
        errors.append(
            f"Regel {line_number}, code '{code}': "
            f"{field_name} '{date_value}' heeft niet het verwachte "
            f"formaat {DATE_FORMAT_DESCRIPTION}."
        )

        return None


def validate_date_order(
    start_date_value,
    end_date_value,
    code,
    line_number,
    errors,
):
    """
    Controleert dat de einddatum niet vóór de begindatum ligt.

    Deze controle wordt alleen uitgevoerd als beide datums:
    - gevuld zijn;
    - een geldig datumformaat hebben.
    """

    start_date = parse_date(
        date_value=start_date_value,
        field_name="Begindatum",
        code=code,
        line_number=line_number,
        errors=errors,
    )

    end_date = parse_date(
        date_value=end_date_value,
        field_name="Einddatum",
        code=code,
        line_number=line_number,
        errors=errors,
    )

    if start_date is not None and end_date is not None:
        if end_date < start_date:
            errors.append(
                f"Regel {line_number}, code '{code}': "
                f"Einddatum '{end_date_value}' mag niet vóór "
                f"Begindatum '{start_date_value}' liggen."
            )


def validate_new_code(code, current_entry, errors):
    """
    Valideert een nieuwe referentiewaarde.

    Regels:
    - Begindatum is verplicht.
    - Begindatum moet het formaat DD-MM-JJJJ hebben.
    - Een eventuele Einddatum moet het formaat DD-MM-JJJJ hebben.
    - Einddatum mag niet vóór Begindatum liggen.
    """

    current_row = current_entry["data"]
    line_number = current_entry["line_number"]

    current_start_date = current_row["Begindatum"]
    current_end_date = current_row["Einddatum"]

    if not current_start_date:
        errors.append(
            f"Regel {line_number}, nieuwe code '{code}': "
            f"Begindatum is verplicht."
        )

    validate_date_order(
        start_date_value=current_start_date,
        end_date_value=current_end_date,
        code=code,
        line_number=line_number,
        errors=errors,
    )


def validate_existing_code(
    code,
    base_entry,
    current_entry,
    errors,
):
    """
    Valideert een bestaande referentiewaarde.

    Regels:
    - Begindatum mag niet worden gewijzigd of verwijderd.
    - Een lege Einddatum mag één keer worden gevuld.
    - Een gevulde Einddatum mag niet worden gewijzigd.
    - Een gevulde Einddatum mag niet worden verwijderd.
    - Einddatum mag niet vóór Begindatum liggen.
    """

    base_row = base_entry["data"]
    current_row = current_entry["data"]
    line_number = current_entry["line_number"]

    base_start_date = base_row["Begindatum"]
    base_end_date = base_row["Einddatum"]

    current_start_date = current_row["Begindatum"]
    current_end_date = current_row["Einddatum"]

    # Een bestaande begindatum mag nooit worden gewijzigd of verwijderd.
    if current_start_date != base_start_date:
        errors.append(
            f"Regel {line_number}, bestaande code '{code}': "
            f"Begindatum mag niet worden gewijzigd of verwijderd. "
            f"Oud='{base_start_date}', nieuw='{current_start_date}'."
        )

    # Een lege einddatum mag één keer worden gevuld.
    #
    # De volgende situaties zijn toegestaan:
    # - leeg    -> leeg
    # - leeg    -> gevuld
    # - gevuld  -> dezelfde waarde
    #
    # De volgende situaties zijn niet toegestaan:
    # - gevuld  -> leeg
    # - gevuld  -> andere waarde

    if base_end_date and not current_end_date:
        errors.append(
            f"Regel {line_number}, bestaande code '{code}': "
            f"Einddatum mag niet worden verwijderd. "
            f"Oude waarde='{base_end_date}'."
        )

    elif (
        base_end_date
        and current_end_date
        and current_end_date != base_end_date
    ):
        errors.append(
            f"Regel {line_number}, bestaande code '{code}': "
            f"Een eenmaal gevulde Einddatum mag niet worden gewijzigd. "
            f"Oud='{base_end_date}', nieuw='{current_end_date}'."
        )

    validate_date_order(
        start_date_value=current_start_date,
        end_date_value=current_end_date,
        code=code,
        line_number=line_number,
        errors=errors,
    )


def validate_deleted_codes(base_rows, current_rows, errors):
    """
    Controleert of bestaande codes uit het CSV-bestand zijn verwijderd.

    Referentiewaarden horen normaal gesproken niet fysiek verwijderd te
    worden. Ze moeten door middel van een Einddatum obsolete worden
    verklaard.

    Als verwijderen in jullie proces wel is toegestaan, kan deze functie
    en de aanroep ervan worden verwijderd.
    """

    deleted_codes = sorted(set(base_rows) - set(current_rows))

    for code in deleted_codes:
        base_entry = base_rows[code]
        line_number = base_entry["line_number"]

        errors.append(
            f"Code '{code}' uit de oorspronkelijke regel {line_number} "
            f"is verwijderd. Verwijder referentiewaarden niet fysiek, "
            f"maar voorzie ze van een Einddatum."
        )


def validate_reference_data(base_rows, current_rows):
    """
    Vergelijkt de oorspronkelijke en actuele referentiedata.
    """

    errors = []

    for code, current_entry in current_rows.items():
        if code not in base_rows:
            validate_new_code(
                code=code,
                current_entry=current_entry,
                errors=errors,
            )
        else:
            validate_existing_code(
                code=code,
                base_entry=base_rows[code],
                current_entry=current_entry,
                errors=errors,
            )

    validate_deleted_codes(
        base_rows=base_rows,
        current_rows=current_rows,
        errors=errors,
    )

    return errors


def print_validation_errors(errors):
    """
    Toont validatiefouten in de GitHub Actions-log.

    De prefix ::error:: zorgt ervoor dat GitHub de melding als fout
    herkenbaar weergeeft.
    """

    print()
    print("Validatie van referentiedata is mislukt:")
    print()

    for error in errors:
        print(f"::error::{error}")
        print(f"- {error}")

    print()
    print(f"Aantal validatiefouten: {len(errors)}")


def print_validation_success(base_rows, current_rows):
    """
    Toont een korte samenvatting na een geslaagde validatie.
    """

    new_codes = sorted(set(current_rows) - set(base_rows))

    newly_completed_end_dates = sorted(
        code
        for code in current_rows
        if code in base_rows
        and not base_rows[code]["data"]["Einddatum"]
        and current_rows[code]["data"]["Einddatum"]
    )

    print("Validatie van referentiedata is geslaagd.")
    print(f"Aantal gecontroleerde regels: {len(current_rows)}")
    print(f"Aantal nieuwe codes: {len(new_codes)}")
    print(
        "Aantal bestaande codes met een nieuw ingevulde Einddatum: "
        f"{len(newly_completed_end_dates)}"
    )

    if new_codes:
        print()
        print("Nieuwe codes:")

        for code in new_codes:
            print(f"- {code}")

    if newly_completed_end_dates:
        print()
        print("Codes waarvoor de Einddatum is ingevuld:")

        for code in newly_completed_end_dates:
            print(f"- {code}")


def main():
    """
    Hoofdfunctie van het validatiescript.
    """

    args = parse_arguments()

    try:
        base_rows = read_csv(args.base_file)
        current_rows = read_csv(args.current_file)

        errors = validate_reference_data(
            base_rows=base_rows,
            current_rows=current_rows,
        )

        if errors:
            print_validation_errors(errors)
            return 1

        print_validation_success(
            base_rows=base_rows,
            current_rows=current_rows,
        )

        return 0

    except ValueError as error:
        print(f"::error::{error}")
        print(f"Validatiefout: {error}")
        return 1

    except Exception as error:
        print(f"::error::Onverwachte fout: {error}")
        print(f"Onverwachte fout: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())