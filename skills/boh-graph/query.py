#!/usr/bin/env python3
"""
BOH Graph Query Tool
Usage: python3 query.py "<cypher query>" [--format table|json]
"""
import sys, json, os, time
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError

uri  = os.getenv("BOH_NEO4J_URI",      "bolt://localhost:7687")
user = os.getenv("BOH_NEO4J_USER",     "neo4j")
pwd  = os.getenv("BOH_NEO4J_PASSWORD", "")

CONNECT_TIMEOUT = 10   # seconds to establish connection
MAX_RETRIES     = 3
RETRY_DELAY     = 2    # seconds between retries

if len(sys.argv) < 2:
    print("Usage: query.py \"<cypher>\"")
    sys.exit(1)

query = sys.argv[1]

def run_query(cypher, retries=MAX_RETRIES):
    driver = GraphDatabase.driver(
        uri,
        auth=(user, pwd),
        connection_timeout=CONNECT_TIMEOUT,
        max_connection_lifetime=300,
        max_connection_pool_size=5,
    )
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            with driver.session() as session:
                results = [dict(r) for r in session.run(cypher)]
            driver.close()
            return results
        except (ServiceUnavailable, SessionExpired, TransientError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(RETRY_DELAY)
        except Exception as e:
            driver.close()
            raise
    driver.close()
    raise last_err

try:
    results = run_query(query)
    print(json.dumps(results, default=str, indent=2))
except Exception as e:
    print(json.dumps({"error": str(e)}))
    sys.exit(1)
