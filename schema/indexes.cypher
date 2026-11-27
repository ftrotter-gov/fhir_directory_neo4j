// Neo4j Schema and Indexes for FHIR Resources
// Run this after starting Neo4j and before importing data

// ============================================
// Constraints (enforce uniqueness)
// ============================================

// Practitioner constraints
CREATE CONSTRAINT practitioner_fhir_id IF NOT EXISTS
FOR (p:Practitioner) REQUIRE p.fhir_id IS UNIQUE;

// PractitionerRole constraints
CREATE CONSTRAINT practitioner_role_fhir_id IF NOT EXISTS
FOR (pr:PractitionerRole) REQUIRE pr.fhir_id IS UNIQUE;

// Organization constraints
CREATE CONSTRAINT organization_fhir_id IF NOT EXISTS
FOR (o:Organization) REQUIRE o.fhir_id IS UNIQUE;

// OrganizationAffiliation constraints
CREATE CONSTRAINT organization_affiliation_fhir_id IF NOT EXISTS
FOR (oa:OrganizationAffiliation) REQUIRE oa.fhir_id IS UNIQUE;

// Endpoint constraints
CREATE CONSTRAINT endpoint_fhir_id IF NOT EXISTS
FOR (e:Endpoint) REQUIRE e.fhir_id IS UNIQUE;

// Location constraints
CREATE CONSTRAINT location_fhir_id IF NOT EXISTS
FOR (l:Location) REQUIRE l.fhir_id IS UNIQUE;

// ============================================
// Indexes for NPI Values (Most Important)
// ============================================

// Index on all NPI values (most important for healthcare queries)
CREATE INDEX npi_practitioner IF NOT EXISTS
FOR (p:Practitioner) ON (p.npi);

// NOTE: Organization.npis is an ARRAY property. A RANGE index on a list value
// indexes the whole serialized list as one key, which hits Neo4j's ~8 KB
// index-value limit and aborts the Organization import whenever a single
// organization carries a large npis array (seen in the official CMS bulk
// download). Array properties are intentionally NOT range-indexed here; use a
// FULLTEXT index (see the array-search section at the end of this file) for
// membership search instead.

// ============================================
// Indexes for Common Query Patterns
// ============================================

// Active status for filtering
CREATE INDEX active_practitioner IF NOT EXISTS
FOR (p:Practitioner) ON (p.active);

CREATE INDEX active_organization IF NOT EXISTS
FOR (o:Organization) ON (o.active);

CREATE INDEX active_practitioner_role IF NOT EXISTS
FOR (pr:PractitionerRole) ON (pr.active);

// Name searches
CREATE TEXT INDEX name_practitioner IF NOT EXISTS
FOR (p:Practitioner) ON (p.name);

CREATE TEXT INDEX name_organization IF NOT EXISTS
FOR (o:Organization) ON (o.name);

// ============================================
// Indexes for Reference Resolution
// ============================================

// These help speed up relationship creation during import
CREATE INDEX reference_practitioner IF NOT EXISTS
FOR (pr:PractitionerRole) ON (pr.practitioner_reference);

CREATE INDEX reference_organization IF NOT EXISTS
FOR (pr:PractitionerRole) ON (pr.organization_reference);

CREATE INDEX reference_participating_org IF NOT EXISTS
FOR (oa:OrganizationAffiliation) ON (oa.participating_organization_reference);

CREATE INDEX reference_primary_org IF NOT EXISTS
FOR (oa:OrganizationAffiliation) ON (oa.organization_reference);

// ============================================
// Indexes for Import Tracking
// ============================================

// Import tag indexes for filtering by import run
CREATE INDEX import_tag_practitioner IF NOT EXISTS
FOR (p:Practitioner) ON (p.import_tag);

CREATE INDEX import_tag_organization IF NOT EXISTS
FOR (o:Organization) ON (o.import_tag);

CREATE INDEX import_tag_location IF NOT EXISTS
FOR (l:Location) ON (l.import_tag);

CREATE INDEX import_tag_endpoint IF NOT EXISTS
FOR (e:Endpoint) ON (e.import_tag);

CREATE INDEX import_tag_practitioner_role IF NOT EXISTS
FOR (pr:PractitionerRole) ON (pr.import_tag);

CREATE INDEX import_tag_organization_affiliation IF NOT EXISTS
FOR (oa:OrganizationAffiliation) ON (oa.import_tag);

// ============================================
// Array-property search (FULLTEXT, not RANGE)
// ============================================
// specialties, languages_spoken, emails, phones, and npis are ARRAY properties.
// A RANGE index on a list value indexes the whole serialized list as a single
// key and hits Neo4j's ~8 KB index-value limit, aborting the import for any
// node whose array is large (observed on Organization.phones and
// Organization.npis in the official CMS bulk download). FULLTEXT indexes
// tokenize each String element, carry no per-value size cap, and support
// membership search via CALL db.index.fulltext.queryNodes('<index>', '<term>').

CREATE FULLTEXT INDEX practitioner_specialties_fulltext IF NOT EXISTS
FOR (p:Practitioner) ON EACH [p.specialties];

CREATE FULLTEXT INDEX practitioner_languages_fulltext IF NOT EXISTS
FOR (p:Practitioner) ON EACH [p.languages_spoken];

CREATE FULLTEXT INDEX practitioner_contact_fulltext IF NOT EXISTS
FOR (p:Practitioner) ON EACH [p.emails, p.phones];

CREATE FULLTEXT INDEX organization_contact_fulltext IF NOT EXISTS
FOR (o:Organization) ON EACH [o.emails, o.phones];

CREATE FULLTEXT INDEX organization_npis_fulltext IF NOT EXISTS
FOR (o:Organization) ON EACH [o.npis];

// Endpoint address searches (scalar strings; RANGE is appropriate)
CREATE INDEX fhir_address_endpoint IF NOT EXISTS
FOR (e:Endpoint) ON (e.FHIR_address);

CREATE INDEX direct_address_endpoint IF NOT EXISTS
FOR (e:Endpoint) ON (e.Direct_address);

// ============================================
// HealthcareService (Plan Net)
// ============================================

CREATE CONSTRAINT healthcareservice_primary_key IF NOT EXISTS
FOR (hs:HealthcareService) REQUIRE hs.primary_key IS UNIQUE;

CREATE INDEX import_tag_healthcareservice IF NOT EXISTS
FOR (hs:HealthcareService) ON (hs.import_tag);

CREATE INDEX active_healthcareservice IF NOT EXISTS
FOR (hs:HealthcareService) ON (hs.active);

// ============================================
// Source Format Indexes (multi-format support)
// ============================================

// Enables queries like "show me all NDH vs Plan Net vs MR data"
CREATE INDEX source_format_practitioner IF NOT EXISTS
FOR (p:Practitioner) ON (p.source_format);

CREATE INDEX source_format_organization IF NOT EXISTS
FOR (o:Organization) ON (o.source_format);

CREATE INDEX source_format_practitioner_role IF NOT EXISTS
FOR (pr:PractitionerRole) ON (pr.source_format);

CREATE INDEX source_format_location IF NOT EXISTS
FOR (l:Location) ON (l.source_format);

CREATE INDEX source_format_endpoint IF NOT EXISTS
FOR (e:Endpoint) ON (e.source_format);

CREATE INDEX source_format_org_affiliation IF NOT EXISTS
FOR (oa:OrganizationAffiliation) ON (oa.source_format);

CREATE INDEX source_format_healthcareservice IF NOT EXISTS
FOR (hs:HealthcareService) ON (hs.source_format);

// ============================================
// Primary Key Indexes (universal merge key)
// primary_key = fhir_id for FHIR data,
//               npi for MR Practitioners/Orgs,
//               sha256 hash for MR Locations
// ============================================

CREATE CONSTRAINT practitioner_primary_key IF NOT EXISTS
FOR (p:Practitioner) REQUIRE p.primary_key IS UNIQUE;

CREATE CONSTRAINT organization_primary_key IF NOT EXISTS
FOR (o:Organization) REQUIRE o.primary_key IS UNIQUE;

CREATE CONSTRAINT location_primary_key IF NOT EXISTS
FOR (l:Location) REQUIRE l.primary_key IS UNIQUE;

CREATE CONSTRAINT practitioner_role_primary_key IF NOT EXISTS
FOR (pr:PractitionerRole) REQUIRE pr.primary_key IS UNIQUE;

CREATE CONSTRAINT org_affiliation_primary_key IF NOT EXISTS
FOR (oa:OrganizationAffiliation) REQUIRE oa.primary_key IS UNIQUE;

CREATE CONSTRAINT endpoint_primary_key IF NOT EXISTS
FOR (e:Endpoint) REQUIRE e.primary_key IS UNIQUE;

// ============================================
// Plan Net Network / Accepting Patients
// ============================================

CREATE INDEX accepting_patients_practitioner_role IF NOT EXISTS
FOR (pr:PractitionerRole) ON (pr.accepting_patients);

// ============================================
// InsurancePlan (NDH + Plan Net)
// NOTE: no RANGE index on array properties (alias, plan_types,
// network_references) -- Neo4j RANGE indexes have a per-value size cap and
// abort imports on large arrays. Only scalar / text properties are indexed.
// ============================================

CREATE CONSTRAINT insurance_plan_primary_key IF NOT EXISTS
FOR (ip:InsurancePlan) REQUIRE ip.primary_key IS UNIQUE;

CREATE CONSTRAINT insurance_plan_fhir_id IF NOT EXISTS
FOR (ip:InsurancePlan) REQUIRE ip.fhir_id IS UNIQUE;

CREATE INDEX import_tag_insurance_plan IF NOT EXISTS
FOR (ip:InsurancePlan) ON (ip.import_tag);

CREATE INDEX source_format_insurance_plan IF NOT EXISTS
FOR (ip:InsurancePlan) ON (ip.source_format);

CREATE INDEX status_insurance_plan IF NOT EXISTS
FOR (ip:InsurancePlan) ON (ip.status);

CREATE TEXT INDEX name_insurance_plan IF NOT EXISTS
FOR (ip:InsurancePlan) ON (ip.name);

// Speeds up OWNED_BY relationship creation (scalar reference)
CREATE INDEX reference_owned_by_insurance_plan IF NOT EXISTS
FOR (ip:InsurancePlan) ON (ip.owned_by_reference);
