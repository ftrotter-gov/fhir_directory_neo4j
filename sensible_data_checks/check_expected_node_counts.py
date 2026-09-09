"""Check source-derived node counts for one import tag."""

from src.inlaw import InLaw

from sensible_data_checks._check_helpers import run_single_record_query


class ExpectedNodeCountsCheck(InLaw):
    title = "Imported node counts match the source resource counts"

    @staticmethod
    def run(engine, config=None):
        expected_counts = config["expected_counts"]
        failures = []
        for resource_type, expected_count in sorted(expected_counts.items()):
            record = run_single_record_query(
                engine=engine,
                query=(
                    "MATCH (directory_node) "
                    "WHERE directory_node.import_tag = $import_tag "
                    "AND directory_node.resource_type = $resource_type "
                    "RETURN count(directory_node) AS node_count"
                ),
                parameters={
                    "import_tag": config["import_tag"],
                    "resource_type": resource_type,
                },
            )
            actual_count = record.get("node_count", 0)
            print(f"    {resource_type}: source={expected_count} database={actual_count}")
            if actual_count != expected_count:
                failures.append(
                    f"{resource_type} expected {expected_count}, found {actual_count}"
                )
        return "; ".join(failures) if failures else True