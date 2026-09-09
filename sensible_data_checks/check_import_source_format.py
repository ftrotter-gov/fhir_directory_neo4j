"""Check that imported sample nodes are classified as Plan Net."""

from src.inlaw import InLaw

from sensible_data_checks._check_helpers import run_single_record_query


class ImportSourceFormatCheck(InLaw):
    title = "Imported nodes have the expected Plan Net source format"

    @staticmethod
    def run(engine, config=None):
        record = run_single_record_query(
            engine=engine,
            query=(
                "MATCH (directory_node) "
                "WHERE directory_node.import_tag = $import_tag "
                "RETURN count(directory_node) AS total_count, "
                "count(CASE WHEN directory_node.source_format = $source_format "
                "THEN 1 END) AS matching_count"
            ),
            parameters={
                "import_tag": config["import_tag"],
                "source_format": config["source_format"],
            },
        )
        print(
            f"    expected={config['source_format']} "
            f"matching={record.get('matching_count', 0)} total={record.get('total_count', 0)}"
        )
        if record.get("total_count", 0) == record.get("matching_count", -1):
            return True
        return "One or more imported nodes have an unexpected source_format"