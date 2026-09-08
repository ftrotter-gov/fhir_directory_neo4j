// Search by Practitioner Last Name and State - Combined
// 
// Purpose: Find practitioners by last name who have the state either in:
//   1. Their own address (stored as serialized JSON), OR
//   2. Work at a location in that state (via PractitionerRole → Location)
//
// This is the most comprehensive state-based search for practitioners.
//
// Usage: 
//   - Replace 'Smith' with the last name you're searching for
//   - Replace 'CA' with the state code (appears twice in query)
//
// Returns: A graph showing all practitioners matching the name and state criteria 
// (either way) and everything within 1-2 hops. Limited to 100 results to prevent 
// overwhelming the visualization.

MATCH (p:Practitioner)
WHERE p.name CONTAINS 'Smith'
  AND (
    p.addresses CONTAINS '"state": "CA"'
    OR EXISTS {
      MATCH (p)-[:HAS_ROLE]->(:PractitionerRole)-[:AT_LOCATION]->(l:Location)
      WHERE l.address CONTAINS '"state": "CA"'
    }
  )
MATCH path = (p)-[*1..2]-(connected)
RETURN path
LIMIT 100;
