"""Check NPI completeness and uniqueness for imported Practitioners."""

from src.inlaw import InLaw

from sensible_data_checks._check_helpers import run_single_record_query


class PractitionerNpisCheck(InLaw):
    title = "Imported Practitioners have distinct NPI values"

    @staticmethod
    def run(engine, config=None):
        record = run_single_record_query(
            engine=engine,
            query=(
                "MATCH (practitioner:Practitioner) "
                "WHERE practitioner.import_tag = $import_tag "
                "RETURN count(practitioner) AS practitioner_count, "
                "count(practitioner.npi) AS npi_count, "
                "count(DISTINCT practitioner.npi) AS distinct_npi_count"
            ),
            parameters={"import_tag": config["import_tag"]},
        )
        practitioner_count = record.get("practitioner_count", 0)
        npi_count = record.get("npi_count", 0)
        distinct_npi_count = record.get("distinct_npi_count", 0)
        print(
            f"    practitioners={practitioner_count} npis={npi_count} "
            f"distinct_npis={distinct_npi_count}"
        )
        if practitioner_count == npi_count == distinct_npi_count and practitioner_count > 0:
            return True
        return "Practitioner NPI values are missing or duplicated"