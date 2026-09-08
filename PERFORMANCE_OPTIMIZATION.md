# Neo4j Import Performance Optimization

> This document records performance guidance for the current importers. FHIR
> NDJSON, Bundle JSON, and single-resource JSON are supported. CMS
> machine-readable JSON import is not yet implemented.

## Current Performance Issue

Importing is currently very slow (~1.9 seconds per record). This document outlines the bottlenecks and solutions.

## Root Causes

### 1. **Missing or Outdated Indexes**
The most critical issue. Without proper indexes, MERGE operations are extremely slow.

**Solution:**
```bash
# First, ensure indexes are created BEFORE importing data
docker exec -i fhir_neo4j_analysis cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" < schema/indexes.cypher
```

### 2. **Batch Size Too Small**
Default batch size of 1000 may be too conservative.

**Solution:**
```bash
# Try larger batch sizes
python scripts/import_or_update_ndjson.py /path/to/data --batch-size 5000
python scripts/import_or_update_ndjson.py /path/to/data --batch-size 10000
```

### 3. **Relationship Creation During Node Import**
Creating relationships (especially to Endpoints that don't exist yet) slows down imports.

**Solution: Two-Pass Import**
1. Import all nodes first (fast)
2. Create relationships in a second pass (after all nodes exist)

## Recommended Import Process

### Step 1: Prepare Database
```bash
# Start Neo4j
docker-compose up -d

# Wait for Neo4j to start (30 seconds)
sleep 30

# Create indexes and constraints
docker exec -i fhir_neo4j_analysis cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" < schema/indexes.cypher
```

### Step 2: Import Nodes Only (Fast)
```bash
# Import with large batch size
python scripts/import_ndjson_fast.py /path/to/data --batch-size 10000

# Or test with limit first
python scripts/import_ndjson_fast.py /path/to/data --batch-size 10000 --limit 1000
```

### Step 3: Reconcile Relationships When Needed

Relationships are created during import. References to nodes that have not yet
been loaded do not create relationships. After all nodes exist, rerun the safe
importer to fill many missing relationships. A dedicated second-pass script is
not currently implemented.

## Performance Benchmarks

### Expected Performance (with proper indexes):
- **With indexes**: 0.01-0.05s per record (20-100x faster)
- **Without indexes**: 1-2s per record (current state)

### Batch Size Impact:
- **batch-size=1000**: ~30-50 records/second
- **batch-size=5000**: ~100-200 records/second  
- **batch-size=10000**: ~200-500 records/second

## Quick Performance Test

```bash
# Test with 100 records
python scripts/import_or_update_ndjson.py /path/to/data --limit 100 --batch-size 100

# If this takes >10 seconds, indexes are missing or not being used
```

## Troubleshooting Slow Imports

### Check 1: Verify Indexes Exist
```cypher
// In Neo4j browser or cypher-shell
SHOW INDEXES;
SHOW CONSTRAINTS;
```

You should see:
- Constraints on `fhir_id` for all resource types
- Indexes on `npi`, `npis`, `name`, etc.

### Check 2: Check Neo4j Memory Settings
Edit `docker-compose.yml`:
```yaml
environment:
  - NEO4J_server_memory_heap_initial__size=2G
  - NEO4J_server_memory_heap_max__size=4G
  - NEO4J_server_memory_pagecache_size=2G
```

### Check 3: Disable Unnecessary Features During Import
```yaml
environment:
  - NEO4J_dbms_tx__log_rotation_retention__policy=false
```

### Check 4: Use APOC for Bulk Operations
If available, APOC procedures can speed up imports significantly.

## Alternative: CSV Import (Fastest)

For very large datasets, Neo4j's offline native bulk importer may be faster
than Cypher imports. This repository does not currently include the required
FHIR-to-Neo4j bulk-file exporter, so this is a possible future optimization
rather than an available workflow.

## Monitoring Import Progress

The import script shows:
- Records processed
- Time elapsed
- Time per record

Watch for sudden slowdowns - these usually indicate:
1. Index not being used
2. Memory pressure
3. Disk I/O bottleneck

## Summary

**Critical Actions:**
1. ✅ Create indexes BEFORE importing (most important!)
2. ✅ Use large batch sizes (5000-10000)
3. ✅ Allocate sufficient memory to Neo4j
4. ✅ Import nodes first, relationships second

**Expected Result:**
- From: 1.9s per record (53 minutes for 2000 records)
- To: 0.01s per record (20 seconds for 2000 records)
- **~5000x speedup with proper optimization!**
