-- Every view of the resolved model. The agent, the app and any report read these, and the stored tables
-- whose name starts with v_ (v_issue, v_queue, v_readiness, v_reuse_between), which tables.py writes.
-- References shown are each part's canonical reference: the spelling the BOM uses most.

-- One line of one sub-assembly in one variant.
CREATE VIEW v_content AS
SELECT o.variant_id,
       sys.canonical_ref  AS system_ref,
       sub.canonical_ref  AS subassembly_ref,
       o.per_train,
       comp.canonical_ref AS component_ref,
       comp.description   AS component_description,
       l.quantity,
       l.unit,
       c.unit_cost_eur,
       c.status           AS price_status
FROM occurrence o
JOIN bom_line l ON l.variant_id = o.variant_id AND l.parent_part_id = o.part_id AND l.level = 4
JOIN part sub  ON sub.part_id = o.part_id
JOIN part sys  ON sys.part_id = o.system_part_id
JOIN part comp ON comp.part_id = l.child_part_id
LEFT JOIN part_cost c ON c.part_id = l.child_part_id;

-- One sub-assembly in one variant, with the cost of one unit of it.
-- unit_cost_eur is a total, so it is empty while any line has no agreed quantity or price: a part with two
-- prices, or none, blocks it, and blocked_by names those components. train_cost_eur is the cost of the per_train
-- units one train needs, blocked the same way. known_cost_eur adds up the lines that are priced: a lower bound,
-- not the cost.
CREATE VIEW v_subassembly_cost AS
SELECT variant_id, system_ref, subassembly_ref, per_train,
       CASE WHEN COUNT(quantity * unit_cost_eur) = COUNT(*) THEN ROUND(SUM(quantity * unit_cost_eur), 2) END AS unit_cost_eur,
       CASE WHEN COUNT(quantity * unit_cost_eur) = COUNT(*) THEN ROUND(per_train * SUM(quantity * unit_cost_eur), 2) END AS train_cost_eur,
       ROUND(SUM(quantity * unit_cost_eur), 2) AS known_cost_eur,
       COUNT(quantity * unit_cost_eur)         AS priced_lines,
       COUNT(*)                                AS total_lines,
       GROUP_CONCAT(CASE WHEN quantity * unit_cost_eur IS NULL THEN component_ref END, ', ') AS blocked_by
FROM v_content
GROUP BY variant_id, system_ref, subassembly_ref, per_train;

-- One sub-assembly in one variant, with its verdict: whether its content is shared.
-- obsolete_parts lists the obsolete or superseded parts it holds, its own reference first; '' when there is none.
-- shared_with lists the other variants that hold the same content; '' when there is none.
-- counterpart_variants lists the variants that hold the design named in counterpart_ref.
-- corrections counts what the claims changed in how its BOM rows, and those of the variants it shares its content
-- with, are read: the verdict holds only with them. v_evidence lists them, kind 'correction'.
CREATE VIEW v_verdict AS
SELECT o.variant_id,
       sys.canonical_ref AS system_ref,
       sub.canonical_ref AS subassembly_ref,
       sub.description,
       v.verdict,
       o.verdict_bom_only,
       v.reason,
       o.obsolete_parts,
       TRIM(REPLACE(' ' || own.variants || ' ', ' ' || o.variant_id || ' ', ' ')) AS shared_with,
       other.refs        AS counterpart_ref,
       other.variants    AS counterpart_variants,
       (SELECT COUNT(*) FROM evidence e WHERE e.design_id = o.design_id AND e.kind = 'correction') AS corrections,
       o.design_id
FROM occurrence o
JOIN verdict v ON v.design_id = o.design_id
JOIN design own ON own.design_id = o.design_id
JOIN part sub  ON sub.part_id = o.part_id
JOIN part sys  ON sys.part_id = o.system_part_id
LEFT JOIN design other ON other.design_id = v.counterpart_design_id;

-- One fact behind a verdict: a BOM row it occurs in, a correction its rows were read with (a reference in another
-- spelling, a repeated row left out, a cell replaced or emptied, a unit converted), the pair it was compared with,
-- or a claim. A claim about a sub-assembly's own reference is shown for that sub-assembly only.
CREATE VIEW v_evidence AS
SELECT o.variant_id, sub.canonical_ref AS subassembly_ref, e.kind, e.detail, e.claim_id, e.source_file, e.source_row
FROM evidence e
JOIN occurrence o ON o.design_id = e.design_id
                 AND (e.variant_id = '' OR (e.variant_id = o.variant_id AND e.part_id = o.part_id))
JOIN part sub ON sub.part_id = o.part_id;

-- One differing line between two sub-assemblies that are near or functionally equivalent.
-- cost_gap_eur is the cost on side b minus the cost on side a, for one unit; empty when a price is missing.
CREATE VIEW v_pair_diff AS
SELECT p.pair_id, p.kind,
       a.refs AS ref_a, a.variants AS variants_a,
       b.refs AS ref_b, b.variants AS variants_b,
       pa.canonical_ref AS component_a,
       pb.canonical_ref AS component_b,
       d.qty_a, d.qty_b, d.explanation, d.claim_id, ROUND(d.cost_gap_eur, 2) AS cost_gap_eur,
       p.separating_options
FROM pair_diff d
JOIN pair p   ON p.pair_id = d.pair_id
JOIN design a ON a.design_id = p.design_a
JOIN design b ON b.design_id = p.design_b
LEFT JOIN part pa ON pa.part_id = d.part_a
LEFT JOIN part pb ON pb.part_id = d.part_b;

-- One design, with the reference each variant uses for it.
CREATE VIEW v_reuse_map AS
SELECT sys.canonical_ref AS system_ref, d.design_id, d.refs,
       MIN(sub.description) AS description,
       MAX(CASE WHEN o.variant_id = 'V1' THEN sub.canonical_ref END) AS V1,
       MAX(CASE WHEN o.variant_id = 'V2' THEN sub.canonical_ref END) AS V2,
       MAX(CASE WHEN o.variant_id = 'V3' THEN sub.canonical_ref END) AS V3,
       MAX(CASE WHEN o.variant_id = 'V4' THEN sub.canonical_ref END) AS V4,
       MAX(CASE WHEN o.variant_id = 'V5' THEN sub.canonical_ref END) AS V5,
       MAX(CASE WHEN o.variant_id = 'V6' THEN sub.canonical_ref END) AS V6,
       v.verdict
FROM design d
JOIN occurrence o ON o.design_id = d.design_id
JOIN part sub ON sub.part_id = o.part_id
JOIN part sys ON sys.part_id = d.system_part_id
JOIN verdict v ON v.design_id = d.design_id
GROUP BY d.design_id;

-- The sub-assemblies of V1, the oldest variant, as a starting point for a tender.
CREATE VIEW v_tender_start AS
SELECT v.subassembly_ref,
       CASE WHEN v.obsolete_parts <> '' THEN 'replace'
            WHEN v.verdict = 'reused' THEN 'reuse' WHEN v.verdict = 'reusable' THEN 'adapt' ELSE 'keep' END AS action,
       v.reason,
       v.obsolete_parts,
       c.train_cost_eur AS cost_eur,
       c.priced_lines, c.total_lines, c.blocked_by AS cost_blocked_by
FROM v_verdict v
LEFT JOIN v_subassembly_cost c ON c.variant_id = v.variant_id AND c.subassembly_ref = v.subassembly_ref
WHERE v.variant_id = 'V1';

-- One bought part: every reference it is written under, its suppliers and its prices.
-- total_quantity is the quantity needed for one train of each variant, added up.
CREATE VIEW v_purchasing AS
SELECT part.canonical_ref,
       part.spellings AS refs,
       part.description,
       (SELECT GROUP_CONCAT(DISTINCT s.name) FROM price pr JOIN supplier s ON s.supplier_id = pr.supplier_id
         WHERE pr.part_id = part.part_id) AS suppliers,
       (SELECT MIN(cost_per_base_unit_eur) FROM price pr WHERE pr.part_id = part.part_id) AS min_cost_eur,
       (SELECT MAX(cost_per_base_unit_eur) FROM price pr WHERE pr.part_id = part.part_id) AS max_cost_eur,
       (SELECT ROUND(SUM(l.quantity * o.per_train), 3) FROM bom_line l
          JOIN occurrence o ON o.variant_id = l.variant_id AND o.part_id = l.parent_part_id
         WHERE l.child_part_id = part.part_id AND l.level = 4) AS total_quantity
FROM part
WHERE part.part_id IN (SELECT part_id FROM price);
