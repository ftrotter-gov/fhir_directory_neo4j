# Da Vinci PDex Plan-Net test fixtures

These NDJSON files are a Plan-Net-profiled provider-directory sample used to
exercise the `fhir_plannet` import path (NPDV-528). The public CMS NPD bulk
download is entirely NDH-profiled, so it does not cover the Plan-Net branch.

## Provenance

Assembled from the example resources shipped in the HL7 Da Vinci PDex Plan-Net
Implementation Guide FHIR package (`hl7.fhir.us.davinci-pdex-plan-net`,
<https://hl7.org/fhir/us/davinci-pdex-plan-net/>). Each example's
`meta.profile[0]` is a `davinci-pdex-plan-net` StructureDefinition, which is what
`registry.get_source_format_string()` keys on to stamp `source_format =
fhir_plannet`.

The resources are the IG's interconnected "Acme of CT" payer scenario, so
references resolve within the set: InsurancePlan `ownedBy`/`network` point at
Organizations present here, and OrganizationAffiliation carries the Plan-Net
`network[]` used for `IN_NETWORK` relationships.

HL7 publishes these IG examples for implementation use; the example instances are
not normative content. One resource object per line, grouped by resourceType.

## Contents

| File | Records |
| --- | --- |
| Organization.ndjson | 11 |
| HealthcareService.ndjson | 10 |
| Location.ndjson | 9 |
| OrganizationAffiliation.ndjson | 7 |
| PractitionerRole.ndjson | 6 |
| Practitioner.ndjson | 3 |
| InsurancePlan.ndjson | 2 |
| Endpoint.ndjson | 1 |

## Regenerating

Download the IG package and regroup the `example/*.json` instances by
`resourceType` into `<ResourceType>.ndjson` (compact, one object per line):

```
curl -fsSL https://hl7.org/fhir/us/davinci-pdex-plan-net/package.tgz -o package.tgz
tar xzf package.tgz   # resources land in package/example/
```
