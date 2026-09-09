"""Check universal properties required on imported nodes."""

from src.inlaw import InLaw

from sensible_data_checks._check_helpers import run_single_record_query


class RequiredNodePropertiesCheck(InLaw):
    title = "Imported nodes have universal identity and provenance properties"

    @staticmethod
    def run(engine, config=None):
        record = run_single_record_query(
            engine=engine,
            query=(
                "MATCH (directory_node) "
                "WHERE directory_node.import_tag = $import_tag "
                "AND (directory_node.primary_key IS NULL "
                "OR directory_node.fhir_id IS NULL "
                "OR directory_node.resource_type IS NULL "
                "OR directory_node.source_format IS NULL) "
                "RETURN count(directory_node) AS invalid_count"
            ),
            parameters={"import_tag": config["import_tag"]},
        )
        invalid_count = record.get("invalid_count", 0)
        print(f"    nodes missing required properties={invalid_count}")
        return True if invalid_count == 0 else f"Found {invalid_count} invalid nodes"