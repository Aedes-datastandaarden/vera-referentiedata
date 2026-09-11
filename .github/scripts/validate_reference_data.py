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
    "Parent",
    "Informatiedomein"
}

DATE_FORMAT = "%d-%m-%Y"
DATE_FORMAT_DESCRIPTION = "DD-MM-JJJJ"


def parse_arguments():
    """
    Read the command-line arguments.

    The base file contains the reference data from the target branch.
    The current file contains the reference data from the pull request.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Compare two versions of the reference data file and validate "
            "the lifecycle rules for start and end dates."
        )
    )

    parser.add_argument(
        "--base-file",
        required=True,
        help=(
            "CSV file from the target branch of the pull request, "
            "for example main."
        ),
    )

    parser.add_argument(
        "--current-file",
        required=True,
        help="Modified CSV file from the pull request.",
    )

    return parser.parse_args()


def format_key(reference_key):
    """
    Format a reference key for human-readable validation messages.

    A reference key consists of:
    - Soort
    - Code
    """

    soort, code = reference_key

    return f"Soort='{soort}', Code='{code}'"


def read_csv(file_path):
    """
    Read a CSV file and return its rows as a dictionary.

    The combination of Soort and Code is used as the unique key.

    The following structural validations are also performed:
    - the file exists;
    - all expected columns are present;
    - Soort is populated;
    - Code is populated;
    - the combination of Soort and Code is unique.
    """

    path = Path(file_path)

    if not path.exists():
        raise ValueError(f"File does not exist: {file_path}")

    rows_by_key = {}
    duplicate_keys = []

    with path.open(
        mode="r",
        encoding="utf-8-sig",
        newline="",
    ) as csv_file:
        reader = csv.DictReader(
            csv_file,
            delimiter=",",
        )

        if reader.fieldnames is None:
            raise ValueError(
                f"CSV file does not contain column headers: {file_path}"
            )

        actual_fields = {
            field.strip()
            for field in reader.fieldnames
            if field is not None
        }

        missing_fields = EXPECTED_FIELDS - actual_fields

        if missing_fields:
            raise ValueError(
                f"CSV file '{file_path}' is missing the following columns: "
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

            if not soort:
                raise ValueError(
                    f"Empty Soort found in '{file_path}' "
                    f"on line {line_number}."
                )

            if not code:
                raise ValueError(
                    f"Empty Code found in '{file_path}' "
                    f"on line {line_number}."
                )

            reference_key = (soort, code)

            if reference_key in rows_by_key:
                duplicate_keys.append(reference_key)
                continue

            rows_by_key[reference_key] = {
                "line_number": line_number,
                "data": normalized_row,
            }

    if duplicate_keys:
        formatted_duplicates = sorted(
            format_key(reference_key)
            for reference_key in set(duplicate_keys)
        )

        raise ValueError(
            f"The following combinations of Soort and Code occur more than "
            f"once in '{file_path}': "
            f"{'; '.join(formatted_duplicates)}"
        )

    return rows_by_key


def parse_date(
    date_value,
    field_name,
    reference_key,
    line_number,
    errors,
):
    """
    Convert a populated date to a datetime object.

    Return None if the date is empty.

    Add a validation error and return None if the date does not have
    the expected format.
    """

    if not date_value:
        return None

    try:
        return datetime.strptime(date_value, DATE_FORMAT)
    except ValueError:
        errors.append(
            f"Line {line_number}, {format_key(reference_key)}: "
            f"{field_name} '{date_value}' does not use the expected "
            f"format {DATE_FORMAT_DESCRIPTION}."
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
    Validate that the end date is not before the start date.

    This validation is only performed when both dates are populated
    and have a valid format.
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

    if (
        start_date is not None
        and end_date is not None
        and end_date < start_date
    ):
        errors.append(
            f"Line {line_number}, {format_key(reference_key)}: "
            f"Einddatum '{end_date_value}' cannot be before "
            f"Begindatum '{start_date_value}'."
        )


def validate_new_reference_value(
    reference_key,
    current_entry,
    errors,
):
    """
    Validate a new reference value.

    Rules:
    - Begindatum is required.
    - Begindatum must use the format DD-MM-YYYY.
    - An optional Einddatum must use the format DD-MM-YYYY.
    - Einddatum cannot be before Begindatum.
    """

    current_row = current_entry["data"]
    line_number = current_entry["line_number"]

    current_start_date = current_row["Begindatum"]
    current_end_date = current_row["Einddatum"]

    if not current_start_date:
        errors.append(
            f"Line {line_number}, new reference value "
            f"{format_key(reference_key)}: Begindatum is required."
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
    Validate an existing reference value.

    Rules:
    - Begindatum cannot be modified or removed.
    - An empty Einddatum may be populated once.
    - A populated Einddatum cannot be modified.
    - A populated Einddatum cannot be removed.
    - Einddatum cannot be before Begindatum.
    """

    base_row = base_entry["data"]
    current_row = current_entry["data"]
    line_number = current_entry["line_number"]

    base_start_date = base_row["Begindatum"]
    base_end_date = base_row["Einddatum"]

    current_start_date = current_row["Begindatum"]
    current_end_date = current_row["Einddatum"]

    if current_start_date != base_start_date:
        errors.append(
            f"Line {line_number}, existing reference value "
            f"{format_key(reference_key)}: Begindatum cannot be modified "
            f"or removed. Old='{base_start_date}', "
            f"new='{current_start_date}'."
        )

    # Allowed transitions for Einddatum:
    #
    # empty     -> empty
    # empty     -> populated
    # populated -> same value
    #
    # Disallowed transitions:
    #
    # populated -> empty
    # populated -> different value

    if base_end_date and not current_end_date:
        errors.append(
            f"Line {line_number}, existing reference value "
            f"{format_key(reference_key)}: Einddatum cannot be removed. "
            f"Old value='{base_end_date}'."
        )

    elif (
        base_end_date
        and current_end_date
        and current_end_date != base_end_date
    ):
        errors.append(
            f"Line {line_number}, existing reference value "
            f"{format_key(reference_key)}: a populated Einddatum cannot "
            f"be modified. Old='{base_end_date}', "
            f"new='{current_end_date}'."
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
    errors,
):
    """
    Validate that existing reference values have not been deleted.

    Reference values should normally be made obsolete by populating
    Einddatum, rather than by physically deleting their CSV row.
    """

    deleted_keys = sorted(set(base_rows) - set(current_rows))

    for reference_key in deleted_keys:
        base_entry = base_rows[reference_key]
        original_line_number = base_entry["line_number"]

        errors.append(
            f"Reference value {format_key(reference_key)} from original "
            f"line {original_line_number} has been deleted. Do not "
            f"physically delete a reference value. Populate Einddatum "
            f"instead."
        )


def validate_reference_data(base_rows, current_rows):
    """
    Compare the original and current reference data.

    The comparison uses the combination of Soort and Code as the
    unique identifier.
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
        errors=errors,
    )

    return errors


def print_validation_errors(errors):
    """
    Print validation errors to the GitHub Actions log.

    The ::error:: prefix causes GitHub Actions to display the message
    as an error annotation.
    """

    print()
    print("Reference data validation failed:")
    print()

    for error in errors:
        print(f"::error::{error}")
        print(f"- {error}")

    print()
    print(f"Number of validation errors: {len(errors)}")


def print_validation_success(base_rows, current_rows):
    """
    Print a summary after successful validation.
    """

    new_keys = sorted(set(current_rows) - set(base_rows))

    newly_populated_end_dates = sorted(
        reference_key
        for reference_key in current_rows
        if reference_key in base_rows
        and not base_rows[reference_key]["data"]["Einddatum"]
        and current_rows[reference_key]["data"]["Einddatum"]
    )

    print("Reference data validation succeeded.")
    print(f"Number of validated rows: {len(current_rows)}")
    print(f"Number of new reference values: {len(new_keys)}")
    print(
        "Number of existing reference values with a newly populated "
        f"Einddatum: {len(newly_populated_end_dates)}"
    )

    if new_keys:
        print()
        print("New reference values:")

        for reference_key in new_keys:
            print(f"- {format_key(reference_key)}")

    if newly_populated_end_dates:
        print()
        print("Reference values for which Einddatum was populated:")

        for reference_key in newly_populated_end_dates:
            print(f"- {format_key(reference_key)}")


def main():
    """
    Main entry point for the validation script.
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
        print(f"Validation error: {error}")
        return 1

    except Exception as error:
        print(f"::error::Unexpected error: {error}")
        print(f"Unexpected error: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())