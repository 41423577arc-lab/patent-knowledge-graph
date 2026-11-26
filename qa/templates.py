"""Read-only Cypher. Only fixed query text and named parameter values reach Neo4j."""
from qa import intents as I

SCOPE = """
MATCH (p:Patent)
RETURN count(p) AS patents, count(CASE WHEN p.patent_id IN $probes THEN 1 END) AS matched
LIMIT 1
"""
WINDOW = "($start_year IS NULL OR p.apply_year >= $start_year AND p.apply_year <= $end_year)"
TECHNICAL = "NOT p.patent_type CONTAINS '外观设计'"
SOURCE = "UNWIND $members AS name MATCH (a:Applicant {name: name})-[:APPLIES_FOR]->(p:Patent)"
TOP = f"""
MATCH (a:Applicant)-[:APPLIES_FOR]->(p:Patent)
WHERE {WINDOW} AND (NOT $enterprise_only OR a.type = '企业')
RETURN a.name AS applicant_std, count(DISTINCT p) AS patent_count
ORDER BY patent_count DESC, applicant_std LIMIT $limit
"""
INFLUENCE = """
MATCH (p:Patent)-[:CITES]->(q:Patent)<-[:APPLIES_FOR]-(a:Applicant)
WHERE NOT $enterprise_only OR a.type = '企业'
RETURN a.name AS applicant_std, count(DISTINCT [p.patent_id, q.patent_id]) AS cited_count
ORDER BY cited_count DESC, applicant_std LIMIT $limit
"""
IPC = f"""
{SOURCE}-[r:HAS_IPC]->(i:IPC)
WHERE {WINDOW} AND {TECHNICAL} AND ($ipc_scope = 'all' OR r.is_main = true)
WITH a, p, i ORDER BY a.name, p.patent_id
RETURN i.code AS ipc_code, count(DISTINCT p) AS patent_count,
       head(collect({{applicant: a.name, patent: p.patent_id}})) AS evidence
ORDER BY patent_count DESC, ipc_code LIMIT $limit
"""
COOP = """
UNWIND $members AS name
MATCH (a:Applicant {name: name})-[r:CO_APPLIED_WITH]-(b:Applicant)
WHERE NOT b.name IN $members
WITH b, a, r ORDER BY r.weight DESC, a.name
RETURN b.name AS partner, sum(r.weight) AS weight,
       collect({applicant: startNode(r).name, partner: endNode(r).name, weight: r.weight})[..5] AS evidence
ORDER BY weight DESC, partner LIMIT $limit
"""
COOP_WINDOW = f"""
{SOURCE}<-[:APPLIES_FOR]-(b:Applicant)
WHERE {WINDOW} AND NOT b.name IN $members
WITH a, b, p ORDER BY a.name, p.patent_id
RETURN b.name AS partner, count(DISTINCT p) AS weight,
       head(collect({{applicant:a.name, partner:b.name, patent:p.patent_id}})) AS evidence
ORDER BY weight DESC, partner LIMIT $limit
"""
COOP_EVIDENCE = """
UNWIND $members AS name
MATCH (a:Applicant {name: name})-[r:CO_APPLIED_WITH]-(b:Applicant)
WHERE b.name IN $partners
RETURN DISTINCT startNode(r).name AS applicant, endNode(r).name AS partner, r.weight AS weight
ORDER BY weight DESC, applicant, partner LIMIT $evidence_limit
"""
TREND = f"""
MATCH (t:Technology {{name: $topic}})<-[:INVOLVES]-(p:Patent)
WHERE {WINDOW} AND {TECHNICAL}
RETURN t.name AS topic, p.apply_year AS year, count(DISTINCT p) AS count
ORDER BY year LIMIT 201
"""
GROWTH = f"""
MATCH (t:Technology)<-[:INVOLVES]-(p:Patent)
WHERE {WINDOW} AND {TECHNICAL} AND NOT t.name ENDS WITH '（未细分）'
RETURN t.name AS topic, p.apply_year AS year, count(DISTINCT p) AS count
ORDER BY topic, year LIMIT 20000
"""
TOPICS = f"""
{SOURCE}-[:INVOLVES]->(t:Technology)-[:BELONGS_TO]->(d:Domain)
WHERE {WINDOW} AND {TECHNICAL}
WITH a, p, t, d ORDER BY a.name, p.patent_id
RETURN t.name AS topic, d.name AS domain, count(DISTINCT p) AS patent_count,
       head(collect({{applicant: a.name, patent: p.patent_id}})) AS evidence
ORDER BY patent_count DESC, topic, domain LIMIT $limit
"""
LAYOUT = f"""
UNWIND $partners AS name
MATCH (a:Applicant {{name: name}})-[:APPLIES_FOR]->(p:Patent)-[:INVOLVES]->(t:Technology)-[:BELONGS_TO]->(d:Domain)
WHERE {WINDOW} AND {TECHNICAL}
WITH a, p, t, d ORDER BY p.patent_id
WITH a, t, d, count(DISTINCT p) AS patent_count, head(collect(p.patent_id)) AS patent
ORDER BY patent_count DESC, t.name, d.name
WITH a, collect({{topic:t.name, domain:d.name, patent_count:patent_count, patent:patent}})[..3] AS top
UNWIND top AS item
RETURN a.name AS partner, item.topic AS topic, item.domain AS domain,
       item.patent_count AS patent_count, item.patent AS patent
ORDER BY partner, patent_count DESC, topic, domain LIMIT $evidence_limit
"""
CITATION = f"""
{SOURCE}-[:CITES]->(q:Patent)<-[:APPLIES_FOR]-(b:Applicant)
WHERE {WINDOW} AND NOT b.name IN $members
WITH DISTINCT b, p, q, a ORDER BY p.patent_id, q.patent_id, a.name
WITH b, count(DISTINCT [p.patent_id,q.patent_id]) AS citation_count,
     collect(DISTINCT q) AS cited,
     collect({{applicant:a.name, patent:p.patent_id, cited:q.patent_id}})[..3] AS evidence
ORDER BY citation_count DESC, b.name LIMIT $limit
UNWIND cited AS q
OPTIONAL MATCH (q)-[:HAS_IPC]->(i:IPC)
WITH b, citation_count, evidence, collect(DISTINCT i.code) AS ipc_codes, collect(DISTINCT q) AS cited
UNWIND cited AS q
OPTIONAL MATCH (q)-[:INVOLVES]->(t:Technology)-[:BELONGS_TO]->(d:Domain)
WITH b, citation_count, evidence, ipc_codes, collect(DISTINCT t.name) AS topics,
     collect(DISTINCT d.name) AS domains
RETURN b.name AS applicant_std, citation_count, ipc_codes, topics, domains, evidence
ORDER BY citation_count DESC, applicant_std LIMIT $limit
"""
CITATION_LAYOUT = """
UNWIND $patent_ids AS patent_id
MATCH (q:Patent {patent_id: patent_id})
OPTIONAL MATCH (q)-[:HAS_IPC]->(i:IPC)
WITH q, collect(DISTINCT i.code)[..3] AS ipc_codes
OPTIONAL MATCH (q)-[:INVOLVES]->(t:Technology)-[:BELONGS_TO]->(d:Domain)
RETURN q.patent_id AS patent, ipc_codes, collect(DISTINCT {topic:t.name, domain:d.name})[..3] AS topics
ORDER BY patent LIMIT $evidence_limit
"""
DEPENDENCY = f"""
{SOURCE}
WHERE {WINDOW}
RETURN DISTINCT p.patent_id AS patent_id
ORDER BY patent_id SKIP $offset LIMIT $batch_size
"""
PATENTS = f"""
{SOURCE}
WHERE {WINDOW}
WITH p, collect(DISTINCT a.name) AS applicants
OPTIONAL MATCH (q:Patent)-[:CITES]->(p)
RETURN p.patent_id AS patent_id, p.title AS title, p.apply_year AS year, p.patent_type AS patent_type,
       count(DISTINCT q) AS cited_count, applicants
ORDER BY cited_count DESC, year DESC, patent_id LIMIT $limit
"""
TOPIC_APPLICANTS = f"""
MATCH (t:Technology {{name: $topic}})<-[:INVOLVES]-(p:Patent)<-[:APPLIES_FOR]-(a:Applicant)
WHERE {WINDOW} AND {TECHNICAL} AND (NOT $enterprise_only OR a.type = '企业')
WITH p, a ORDER BY p.patent_id
RETURN a.name AS applicant_std, count(DISTINCT p) AS patent_count, head(collect(p.patent_id)) AS patent
ORDER BY patent_count DESC, applicant_std LIMIT $limit
"""

QUERIES = {
    I.TOP: TOP, I.INFLUENCE: INFLUENCE, I.IPC: IPC, I.COOP: COOP,
    I.TREND: TREND, I.GROWTH: GROWTH, I.TOPICS: TOPICS, I.LAYOUT: LAYOUT,
    I.CITATION: CITATION, I.DEPENDENCY: DEPENDENCY, I.PATENTS: PATENTS,
    I.TOPIC_APPLICANTS: TOPIC_APPLICANTS,
}
