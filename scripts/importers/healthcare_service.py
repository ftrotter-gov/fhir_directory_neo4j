"""
HealthcareService resource importer (Da Vinci PDex Plan Net).

Graph nodes: (:HealthcareService {primary_key, fhir_id, source_format, active,
                                   categories, specialties, phones, emails, faxes,
                                   identifiers, import_tag})
Relationships:
  (:HealthcareService)-[:PROVIDED_BY]->(:Organization)
  (:HealthcareService)-[:AT_LOCATION]->(:Location)
"""

from typing import Dict, Any, List
from neo4j import Session
from .base import BaseImporter, _to_json_string


class HealthcareServiceImporter(BaseImporter):
    """Import HealthcareService resources into Neo4j."""

    RESOURCE_TYPE = "HealthcareService"
    NODE_LABEL = "HealthcareService"

    def __init__(self, *, neo4j_uri, neo4j_user, neo4j_password,
                 import_tag=None, use_create=False, source_format="fhir_unknown"):
        super().__init__(neo4j_uri=neo4j_uri, neo4j_user=neo4j_user,
                         neo4j_password=neo4j_password, import_tag=import_tag,
                         use_create=use_create)
        self.source_format = source_format

    def import_batch(self, *, session: Session, batch: List[Dict[str, Any]]) -> int:
        service_data = []

        for resource in batch:
            fhir_id = resource.get('id')
            if not fhir_id:
                self._log(message=f"Skipping HealthcareService without id")
                continue

            identifiers = self._extract_identifiers(resource=resource)
            active = resource.get('active')

            categories = []
            for cat in resource.get('category', []):
                if isinstance(cat, dict):
                    for code in cat.get('coding', []):
                        if isinstance(code, dict):
                            display = code.get('display') or code.get('code')
                            if display:
                                categories.append(display)

            specialties = []
            for spec in resource.get('specialty', []):
                if isinstance(spec, dict):
                    for code in spec.get('coding', []):
                        if isinstance(code, dict) and code.get('code'):
                            specialties.append(code['code'])

            provided_by_ref = resource.get('providedBy', {})
            provided_by_id = self._parse_reference(
                reference=provided_by_ref.get('reference') if isinstance(provided_by_ref, dict) else None
            )

            location_ids = []
            for loc_ref in resource.get('location', []):
                if isinstance(loc_ref, dict):
                    loc_id = self._parse_reference(reference=loc_ref.get('reference'))
                    if loc_id:
                        location_ids.append(loc_id)

            telecoms = self._extract_telecoms(resource=resource)

            service_data.append({
                'fhir_id':        fhir_id,
                'primary_key':    fhir_id,
                'source_format':  self.source_format,
                'resource_type':  self.RESOURCE_TYPE,
                'active':         active,
                'categories':     categories,
                'specialties':    specialties,
                'provided_by_id': provided_by_id,
                'location_ids':   location_ids,
                'emails':         telecoms['emails'],
                'phones':         telecoms['phones'],
                'faxes':          telecoms['faxes'],
                'identifiers':    _to_json_string(obj=identifiers),
                'import_tag':     self.import_tag,
            })

        if not service_data:
            return 0

        if self.use_create:
            query = """
            UNWIND $batch AS hs
            CREATE (s:HealthcareService {
                primary_key: hs.primary_key, fhir_id: hs.fhir_id,
                import_tag: hs.import_tag, source_format: hs.source_format,
                resource_type: hs.resource_type, active: hs.active,
                categories: hs.categories, specialties: hs.specialties,
                emails: hs.emails, phones: hs.phones, faxes: hs.faxes,
                identifiers: hs.identifiers
            })
            RETURN count(s) AS count
            """
        else:
            query = """
            UNWIND $batch AS hs
            MERGE (s:HealthcareService {primary_key: hs.primary_key})
            ON CREATE SET s.import_tag = hs.import_tag
            SET s.fhir_id = hs.fhir_id, s.source_format = hs.source_format,
                s.resource_type = hs.resource_type, s.active = hs.active,
                s.categories = hs.categories, s.specialties = hs.specialties,
                s.emails = hs.emails, s.phones = hs.phones, s.faxes = hs.faxes,
                s.identifiers = hs.identifiers
            RETURN count(s) AS count
            """

        result = session.run(query, batch=service_data)
        record = result.single()
        node_count = record['count'] if record else 0
        self._create_relationships(session=session, service_data=service_data,
                                   use_create=self.use_create)
        return node_count

    @staticmethod
    def _create_relationships(*, session, service_data, use_create=False):
        rel_op = "CREATE" if use_create else "MERGE"

        session.run(f"""
            UNWIND $batch AS hs
            MATCH (s:HealthcareService {{primary_key: hs.primary_key}})
            MATCH (o:Organization {{fhir_id: hs.provided_by_id}})
            {rel_op} (s)-[:PROVIDED_BY]->(o)
        """, batch=[s for s in service_data if s.get('provided_by_id')])

        session.run(f"""
            UNWIND $batch AS hs
            MATCH (s:HealthcareService {{primary_key: hs.primary_key}})
            UNWIND hs.location_ids AS loc_id
            MATCH (l:Location {{fhir_id: loc_id}})
            {rel_op} (s)-[:AT_LOCATION]->(l)
        """, batch=[s for s in service_data if s.get('location_ids')])
