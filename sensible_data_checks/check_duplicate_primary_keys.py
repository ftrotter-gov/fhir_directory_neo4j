"""Check primary-key uniqueness within each resource type."""

from src.inlaw import InLaw

from sensible_data_checks._check_helpers import run_single_record_query


class DuplicatePrimaryKeysCheck(InLaw):
    title = "Imported resource primary keys are unique"

    @staticmethod
    def run(engine, config=None):
        record = run_single_record_query(
            engine=engine,
            query=(
                "MATCH (directory_node) "
                "WHERE directory_node.import_tag = $import_tag "
                "WITH directory_node.resource_type AS resource_type, "
                "directory_node.primary_key AS primary_key, count(*) AS key_count "
                "WHERE key_count > 1 "
                "RETURN count(*) AS duplicate_count"
            ),
            parameters={"import_tag": config["import_tag"]},
        )
        duplicate_count = record.get("duplicate_count", 0)
        print(f"    duplicate resource keys={duplicate_count}")
        return True if duplicate_count == 0 else f"Found {duplicate_count} duplicate keys"