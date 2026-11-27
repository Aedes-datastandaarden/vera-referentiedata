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
OBSOLETE_DESCRIPTION_MARKER = "VERVALLEN"


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

    parser.add_argument(
        "--base-commit",
        help="Commit SHA of the base file, used for logging.",
    )

    parser.add_argument(
        "--current-commit",
        help="Commit SHA of the current file, used for logging.",
    )

    return parser.parse_args()


def print_compared_versions(args):
    """
    Logt welke bestandsversies worden vergeleken, inclusief de commit
    SHA's wanneer deze als argument zijn meegegeven.
    """

    base_commit = args.base_commit or "onbekend"
    current_commit = args.current_commit or "onbekend"

    print("Vergeleken versies van de referentiedata:")
    print(f"- Basisbestand: {args.base_file} (commit {base_commit})")
    print(f"- Huidig bestand: {args.current_file} (commit {current_commit})")
    print()


def format_key(reference_key):
    """
    Formatteert een referentiesleutel voor leesbare validatiemeldingen.

    Een referentiesleutel bestaat uit:
    - Soort
    - Code
    - Naam
    """

    soort, code, naam = reference_key

    return f"Soort='{soort}', Code='{code}', Naam='{naam}'"


def read_csv(file_path):
    """
    Leest een CSV-bestand en retourneert twee waarden:
    - een dictionary met de regels, waarbij de combinatie van Soort,
      Code en Naam als unieke sleutel wordt gebruikt, met uitzondering
      van regels waarvan de Omschrijving VERVALLEN bevat;
    - de verzameling sleutels van regels waarvan de Omschrijving
      VERVALLEN bevat.

    Ook worden de volgende structuurcontroles uitgevoerd:
    - het bestand bestaat;
    - de verwachte kolommen zijn aanwezig;
    - Soort is gevuld;
    - Code is gevuld;
    - Naam is gevuld;
    - de combinatie van Soort, Code en Naam is uniek, tenzij de
      Omschrijving VERVALLEN bevat;
    - regels waarvan de Omschrijving VERVALLEN bevat, hebben een
      gevulde Einddatum.
    """

    path = Path(file_path)

    if not path.exists():
        raise ValueError(f"Bestand bestaat niet: {file_path}")

    rows_by_key = {}
    duplicate_keys = []
    obsolete_keys = set()
    obsolete_rows_without_end_date = []

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

            soort = normalized_row["Soort"]
            code = normalized_row["Code"]
            naam = normalized_row["Naam"]

            if not soort:
                raise ValueError(
                    f"Lege Soort gevonden in '{file_path}' "
                    f"op regel {line_number}."
                )

            if not code:
                raise ValueError(
                    f"Lege Code gevonden in '{file_path}' "
                    f"op regel {line_number}."
                )

            if not naam:
                raise ValueError(
                    f"Lege Naam gevonden in '{file_path}' "
                    f"op regel {line_number}."
                )

            reference_key = (soort, code, naam)

            if OBSOLETE_DESCRIPTION_MARKER in normalized_row["Omschrijving"]:
                obsolete_keys.add(reference_key)

                if not normalized_row["Einddatum"]:
                    obsolete_rows_without_end_date.append(
                        (line_number, reference_key)
                    )

                continue

            if reference_key in rows_by_key:
                duplicate_keys.append(reference_key)
                continue

            rows_by_key[reference_key] = {
                "line_number": line_number,
                "data": normalized_row,
            }

    if obsolete_rows_without_end_date:
        formatted_rows = [
            f"regel {line_number}, {format_key(reference_key)}"
            for line_number, reference_key in obsolete_rows_without_end_date
        ]

        raise ValueError(
            f"De volgende regels in '{file_path}' bevatten "
            f"'{OBSOLETE_DESCRIPTION_MARKER}' in de Omschrijving, maar "
            f"hebben geen gevulde Einddatum: {'; '.join(formatted_rows)}"
        )

    if duplicate_keys:
        formatted_duplicates = sorted(
            format_key(reference_key)
            for reference_key in set(duplicate_keys)
        )

        raise ValueError(
            f"De volgende combinaties van Soort, Code en Naam komen "
            f"meerdere keren voor in '{file_path}': "
            f"{'; '.join(formatted_duplicates)}"
        )

    return rows_by_key, obsolete_keys


def parse_date(date_value, field_name, reference_key, line_number, errors):
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
            f"Regel {line_number}, {format_key(reference_key)}: "
            f"{field_name} '{date_value}' heeft niet het verwachte "
            f"formaat {DATE_FORMAT_DESCRIPTION}."
        )

        return None


def validate_date_order(
    start_date_value,
    end_date_value,
    reference_key,
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
        reference_key=reference_key,
        line_number=line_number,
        errors=errors,
    )

    end_date = parse_date(
        date_value=end_date_value,
        field_name="Einddatum",
        reference_key=reference_key,
        line_number=line_number,
        errors=errors,
    )

    if start_date is not None and end_date is not None:
        if end_date < start_date:
            errors.append(
                f"Regel {line_number}, {format_key(reference_key)}: "
                f"Einddatum '{end_date_value}' mag niet vóór "
                f"Begindatum '{start_date_value}' liggen."
            )


def validate_new_reference_value(reference_key, current_entry, errors):
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
            f"Regel {line_number}, nieuwe referentiewaarde "
            f"{format_key(reference_key)}: Begindatum is verplicht."
        )

    validate_date_order(
        start_date_value=current_start_date,
        end_date_value=current_end_date,
        reference_key=reference_key,
        line_number=line_number,
        errors=errors,
    )


def validate_existing_reference_value(
    reference_key,
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
            f"Regel {line_number}, bestaande referentiewaarde "
            f"{format_key(reference_key)}: Begindatum mag niet worden "
            f"gewijzigd of verwijderd. "
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
            f"Regel {line_number}, bestaande referentiewaarde "
            f"{format_key(reference_key)}: Einddatum mag niet worden "
            f"verwijderd. Oude waarde='{base_end_date}'."
        )

    elif (
        base_end_date
        and current_end_date
        and current_end_date != base_end_date
    ):
        errors.append(
            f"Regel {line_number}, bestaande referentiewaarde "
            f"{format_key(reference_key)}: Een eenmaal gevulde Einddatum "
            f"mag niet worden gewijzigd. "
            f"Oud='{base_end_date}', nieuw='{current_end_date}'."
        )

    validate_date_order(
        start_date_value=current_start_date,
        end_date_value=current_end_date,
        reference_key=reference_key,
        line_number=line_number,
        errors=errors,
    )


def validate_deleted_reference_values(
    base_rows,
    current_rows,
    current_obsolete_keys,
    errors,
):
    """
    Controleert of bestaande referentiewaarden uit het CSV-bestand zijn
    verwijderd.

    Referentiewaarden horen normaal gesproken niet fysiek verwijderd te
    worden. Ze moeten door middel van een Einddatum obsolete worden
    verklaard.

    Regels die in het huidige bestand als VERVALLEN zijn gemarkeerd,
    tellen niet als verwijderd.

    Als verwijderen in jullie proces wel is toegestaan, kan deze functie
    en de aanroep ervan worden verwijderd.
    """

    deleted_keys = sorted(
        set(base_rows) - set(current_rows) - current_obsolete_keys
    )

    for reference_key in deleted_keys:
        base_entry = base_rows[reference_key]
        line_number = base_entry["line_number"]

        errors.append(
            f"Referentiewaarde {format_key(reference_key)} uit de "
            f"oorspronkelijke regel {line_number} is verwijderd. "
            f"Verwijder referentiewaarden niet fysiek, maar voorzie ze "
            f"van een Einddatum."
        )


def validate_reference_data(base_rows, current_rows, current_obsolete_keys):
    """
    Vergelijkt de oorspronkelijke en actuele referentiedata.

    De vergelijking gebruikt de combinatie van Soort, Code en Naam als
    unieke identificatie.
    """

    errors = []

    for reference_key, current_entry in current_rows.items():
        if reference_key not in base_rows:
            validate_new_reference_value(
                reference_key=reference_key,
                current_entry=current_entry,
                errors=errors,
            )
        else:
            validate_existing_reference_value(
                reference_key=reference_key,
                base_entry=base_rows[reference_key],
                current_entry=current_entry,
                errors=errors,
            )

    validate_deleted_reference_values(
        base_rows=base_rows,
        current_rows=current_rows,
        current_obsolete_keys=current_obsolete_keys,
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

    new_keys = sorted(set(current_rows) - set(base_rows))

    newly_completed_end_dates = sorted(
        reference_key
        for reference_key in current_rows
        if reference_key in base_rows
        and not base_rows[reference_key]["data"]["Einddatum"]
        and current_rows[reference_key]["data"]["Einddatum"]
    )

    print("Validatie van referentiedata is geslaagd.")
    print(f"Aantal gecontroleerde regels: {len(current_rows)}")
    print(f"Aantal nieuwe referentiewaarden: {len(new_keys)}")
    print(
        "Aantal bestaande referentiewaarden met een nieuw ingevulde "
        f"Einddatum: {len(newly_completed_end_dates)}"
    )

    if new_keys:
        print()
        print("Nieuwe referentiewaarden:")

        for reference_key in new_keys:
            print(f"- {format_key(reference_key)}")

    if newly_completed_end_dates:
        print()
        print("Referentiewaarden waarvoor de Einddatum is ingevuld:")

        for reference_key in newly_completed_end_dates:
            print(f"- {format_key(reference_key)}")


def main():
    """
    Hoofdfunctie van het validatiescript.
    """

    args = parse_arguments()

    print_compared_versions(args)

    try:
        base_rows, _ = read_csv(args.base_file)
        current_rows, current_obsolete_keys = read_csv(args.current_file)

        errors = validate_reference_data(
            base_rows=base_rows,
            current_rows=current_rows,
            current_obsolete_keys=current_obsolete_keys,
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