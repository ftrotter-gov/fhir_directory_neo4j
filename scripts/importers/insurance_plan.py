"""
InsurancePlan resource importer.

Supports both NDH and Da Vinci PDex Plan Net InsurancePlan resources.

Graph nodes: (:InsurancePlan {primary_key, fhir_id, source_format, resource_type,
  status, name, alias[], plan_types[], period_start, period_end,
  owned_by_reference, network_references[], identifiers, import_tag})

Relationships:
  (InsurancePlan)-[:OWNED_BY]->(Organization)     from ownedBy (single reference)
  (InsurancePlan)-[:HAS_NETWORK]->(Organization)  from network[] (multiple references)

Field mapping is extracted into the static build_plan_record() helper so it can
be unit-tested without a live Neo4j connection.
"""

from typing import Dict, Any, List, Optional
from neo4j import Session
from .base import BaseImporter, _to_json_string


class InsurancePlanImporter(BaseImporter):
    """Import InsurancePlan resources into Neo4j."""

    RESOURCE_TYPE = "InsurancePlan"
    NODE_LABEL = "InsurancePlan"

    def __init__(self, *, neo4j_uri, neo4j_user, neo4j_password,
                 import_tag=None, use_create=False, source_format="fhir_unknown"):
        super().__init__(neo4j_uri=neo4j_uri, neo4j_user=neo4j_user,
                         neo4j_password=neo4j_password, import_tag=import_tag,
                         use_create=use_create)
        self.source_format = source_format

    @staticmethod
    def build_plan_record(
        *,
        resource: Dict[str, Any],
        source_format: str = "fhir_unknown",
        import_tag: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Map a single InsurancePlan FHIR resource to the flat Neo4j property dict.

        Returns None when the resource has no ``id`` (it cannot be keyed).
        This is a pure function of its inputs so it can be tested without Neo4j.
        """
        fhir_id = resource.get("id")
        if not fhir_id:
            return None

        identifiers = BaseImporter._extract_identifiers(resource=resource)

        status = resource.get("status")
        name = resource.get("name")

        # alias: array of strings (tolerate a bare string)
        alias = resource.get("alias", [])
        if not isinstance(alias, list):
            alias = [alias] if alias else []
        alias = [a for a in alias if isinstance(a, str) and a]

        # type: CodeableConcept[] -> flatten coding.display/code, else text
        plan_types: List[str] = []
        for plan_type in resource.get("type", []) or []:
            if not isinstance(plan_type, dict):
                continue
            coding = plan_type.get("coding", [])
            if isinstance(coding, list) and coding:
                for code in coding:
                    if isinstance(code, dict):
                        display = code.get("display") or code.get("code")
                        if display:
                            plan_types.append(display)
            elif plan_type.get("text"):
                plan_types.append(plan_type.get("text"))

        # period
        period = resource.get("period", {})
        period_start = period.get("start") if isinstance(period, dict) else None
        period_end = period.get("end") if isinstance(period, dict) else None

        # ownedBy: single Organization reference
        owned_by = resource.get("ownedBy", {})
        owned_by_reference = owned_by.get("reference") if isinstance(owned_by, dict) else None
        owned_by_id = BaseImporter._parse_reference(reference=owned_by_reference)

        # network: array of Organization references
        network_ids: List[str] = []
        network_refs = resource.get("network", [])
        if isinstance(network_refs, list):
            for net_ref in network_refs:
                if isinstance(net_ref, dict):
                    net_id = BaseImporter._parse_reference(reference=net_ref.get("reference"))
                    if net_id:
                        network_ids.append(net_id)

        return {
            "fhir_id":             fhir_id,
            "primary_key":         fhir_id,
            "source_format":       source_format,
            "resource_type":       InsurancePlanImporter.RESOURCE_TYPE,
            "status":              status,
            "name":                name,
            "alias":               alias,
            "plan_types":          plan_types,
            "period_start":        period_start,
            "period_end":          period_end,
            "owned_by_id":         owned_by_id,
            "network_ids":         network_ids,
            "identifiers":         _to_json_string(obj=identifiers),
            "import_tag":          import_tag,
        }

    def import_batch(self, *, session: Session, batch: List[Dict[str, Any]]) -> int:
        """
        Import a batch of InsurancePlan resources.

        Args:
            session: Neo4j session
            batch: List of InsurancePlan FHIR resources

        Returns:
            Number of nodes created/updated
        """
        plan_data: List[Dict[str, Any]] = []
        for resource in batch:
            record = self.build_plan_record(
                resource=resource,
                source_format=self.source_format,
                import_tag=self.import_tag,
            )
            if record is None:
                self._log(message=f"Skipping InsurancePlan without id: {resource}")
                continue
            plan_data.append(record)

        if self.use_create:
            query = """
            UNWIND $batch AS ip
            CREATE (p:InsurancePlan {
                primary_key:        ip.primary_key,
                fhir_id:            ip.fhir_id,
                import_tag:         ip.import_tag,
                source_format:      ip.source_format,
                resource_type:      ip.resource_type,
                status:             ip.status,
                name:               ip.name,
                alias:              ip.alias,
                plan_types:         ip.plan_types,
                period_start:       ip.period_start,
                period_end:         ip.period_end,
                owned_by_reference: ip.owned_by_id,
                network_references: ip.network_ids,
                identifiers:        ip.identifiers
            })
            RETURN count(p) AS count
            """
        else:
            query = """
            UNWIND $batch AS ip
            MERGE (p:InsurancePlan {primary_key: ip.primary_key})
            ON CREATE SET p.import_tag = ip.import_tag
            SET p.fhir_id            = ip.fhir_id,
                p.source_format      = ip.source_format,
                p.resource_type      = ip.resource_type,
                p.status             = ip.status,
                p.name               = ip.name,
                p.alias              = ip.alias,
                p.plan_types         = ip.plan_types,
                p.period_start       = ip.period_start,
                p.period_end         = ip.period_end,
                p.owned_by_reference = ip.owned_by_id,
                p.network_references = ip.network_ids,
                p.identifiers        = ip.identifiers
            RETURN count(p) AS count
            """

        result = session.run(query, batch=plan_data)
        record = result.single()
        node_count = record["count"] if record else 0

        self._create_relationships(session=session, plan_data=plan_data, use_create=self.use_create)

        return node_count

    @staticmethod
    def _create_relationships(*, session: Session, plan_data: List[Dict[str, Any]], use_create: bool = False) -> None:
        """
        Create relationships between InsurancePlan and Organizations.

        (InsurancePlan)-[:OWNED_BY]->(Organization)
        (InsurancePlan)-[:HAS_NETWORK]->(Organization)

        Organizations are matched by fhir_id, consistent with the other importers.
        """
        rel_op = "CREATE" if use_create else "MERGE"

        owned_query = f"""
        UNWIND $batch AS ip
        MATCH (p:InsurancePlan {{primary_key: ip.primary_key}})
        MATCH (o:Organization {{fhir_id: ip.owned_by_id}})
        {rel_op} (p)-[:OWNED_BY]->(o)
        """
        session.run(owned_query, batch=[p for p in plan_data if p.get("owned_by_id")])

        network_query = f"""
        UNWIND $batch AS ip
        MATCH (p:InsurancePlan {{primary_key: ip.primary_key}})
        UNWIND ip.network_ids AS net_id
        MATCH (o:Organization {{fhir_id: net_id}})
        {rel_op} (p)-[:HAS_NETWORK]->(o)
        """
        session.run(network_query, batch=[p for p in plan_data if p.get("network_ids")])
