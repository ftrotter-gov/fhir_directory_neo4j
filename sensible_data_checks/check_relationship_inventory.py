"""Report relationship counts and ensure no relationship is self-referential."""

from src.inlaw import InLaw


class RelationshipInventoryCheck(InLaw):
    title = "Relationship inventory contains no self-referential relationships"

    @staticmethod
    def run(engine, config=None):
        with engine.session() as session:
            records = list(
                session.run(
                    "MATCH ()-[directory_relationship]->() "
                    "RETURN type(directory_relationship) AS relationship_type, "
                    "count(directory_relationship) AS relationship_count "
                    "ORDER BY relationship_type"
                )
            )
            self_reference = session.run(
                "MATCH (directory_node)-[directory_relationship]->(directory_node) "
                "RETURN count(directory_relationship) AS self_reference_count"
            ).single()
        if records:
            for record in records:
                print(
                    f"    {record['relationship_type']}: "
                    f"{record['relationship_count']}"
                )
        else:
            print("    No relationships resolved from this partial cache")
        self_reference_count = self_reference["self_reference_count"] if self_reference else 0
        return (
            True
            if self_reference_count == 0
            else f"Found {self_reference_count} self-referential relationships"
        )