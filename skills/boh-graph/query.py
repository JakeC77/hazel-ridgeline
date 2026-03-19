#!/usr/bin/env python3
"""
BOH Graph Query Tool
Usage: python3 query.py "<cypher query>" [--format table|json]
"""
import sys, json, os
from neo4j import GraphDatabase

uri  = os.getenv("BOH_NEO4J_URI",      "bolt://localhost:7687")
user = os.getenv("BOH_NEO4J_USER",     "neo4j")
pwd  = os.getenv("BOH_NEO4J_PASSWORD", "")

if len(sys.argv) < 2:
    print("Usage: query.py \"<cypher>\"")
    sys.exit(1)

query = sys.argv[1]

try:
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    with driver.session() as session:
        results = [dict(r) for r in session.run(query)]
    driver.close()
    print(json.dumps(results, default=str, indent=2))
except Exception as e:
    print(json.dumps({"error": str(e)}))
    sys.exit(1)
