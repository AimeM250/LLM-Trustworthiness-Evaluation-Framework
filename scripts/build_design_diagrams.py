#!/usr/bin/env python3
"""Build editable diagrams.net diagrams and self-contained design review HTML.

Uses Python's standard library only. All content and rendering remain local.
"""
from pathlib import Path
import csv
import html
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "design"
OUT.mkdir(parents=True, exist_ok=True)
W, H = 1440, 960
COLORS = {
    "blue": ("#edf3ff", "#365cbd", "#163566"),
    "white": ("#ffffff", "#cbd5e1", "#253449"),
    "navy": ("#142b4b", "#142b4b", "#ffffff"),
    "green": ("#edf8f3", "#6a9c84", "#21533a"),
    "amber": ("#fff7e8", "#d7ae62", "#78521d"),
    "gray": ("#f4f6f9", "#cbd5e1", "#455469"),
}


class Diagram:
    def __init__(self, name, slug, subtitle):
        self.name, self.slug, self.subtitle = name, slug, subtitle
        self.nodes, self.edges = [], []

    def box(self, ident, x, y, w, h, text, tone="white", size=18, dashed=False):
        self.nodes.append(dict(id=ident, x=x, y=y, w=w, h=h, text=text, tone=tone, size=size, dashed=dashed))
        return self

    def edge(self, source, target, label="", points=None, dashed=False, color="#64748b"):
        self.edges.append(dict(source=source, target=target, label=label, points=points, dashed=dashed, color=color))
        return self


diagrams = []
d = Diagram("01 · System architecture", "01-architecture", "Local research workspace · external execution supplies evidence through files")
d.box("user", 44, 165, 220, 138, "Research team\nViewer · Researcher\nAdministrator", "navy", 19)
d.box("browser", 334, 165, 284, 138, "Browser workspace\nSign in · choose metrics\nProvide data · review results", "blue")
d.box("http", 698, 165, 300, 138, "Local HTTP API\n127.0.0.1:8765\nHost / Origin / request token", "blue")
d.box("auth", 1080, 165, 302, 138, "Access control\nSession + current role\nOwnership + metric filtering", "blue")
d.edge("user", "browser", "uses").edge("browser", "http", "same origin").edge("http", "auth", "each request")
d.box("inputs", 44, 392, 250, 150, "Research input files\ncases.jsonl\nobservations.json\nprofile.json", "white")
d.box("readiness", 368, 392, 280, 150, "Data readiness\nRequirements + starter ZIP\nNon-persistent preflight\nVerified unit / API\nand browser checks", "blue", 17)
d.box("validation", 726, 392, 270, 150, "Schema validation\nTypes · IDs · prompt hash\nScope · trace ordering\nMissingness remains explicit", "blue", 17)
d.box("scoring", 1080, 392, 302, 150, "Evaluation engine\n18 scorers + summaries\nCase-weighted statistics\nPaired comparisons", "blue", 17)
d.edge("inputs", "readiness", "upload locally").edge("readiness", "validation", "validate").edge("validation", "scoring", "valid inputs")
d.edge("http", "validation", "dispatch", points=[(848,303),(848,350),(861,350),(861,392)])
d.box("external", 44, 634, 250, 146, "External model / agent runner\nCapture responses + failures\nCapture resources + traces\nNo live provider connector", "amber", 16, True)
d.edge("external", "inputs", "captured evidence", points=[(169,634),(169,542)], dashed=True)
d.box("review", 368, 634, 280, 146, "Independent review\nReferences + claim evidence\nOutcome / safety labels\nRubric + evaluator identity", "white", 17)
d.edge("review", "inputs", "", points=[(368,708),(326,708),(326,570),(244,570),(244,542)])
d.box("database", 726, 634, 270, 146, "Local SQLite\nAccounts · sessions\nReports + owner / sample flag\nNo raw response archive", "blue", 17)
d.box("outputs", 1080, 634, 302, 146, "Reviewable outputs\nRole-filtered result pages\nJSON / Markdown exports\nManifest + coverage + caveats", "green", 17)
d.edge("scoring", "database", "save report", points=[(1150,542),(1150,590),(861,590),(861,634)])
d.edge("database", "outputs", "read")
d.box("boundary", 44, 842, 1338, 60, "DEPLOYMENT BOUNDARY   One device · loopback HTTP · local files and database · no public hosting, cloud sync or provider API calls", "gray", 17)
diagrams.append(d)

d = Diagram("02 · Data provision and readiness", "02-data-readiness", "Prepare only the evidence your selected metrics need; validation is not scientific validation")
d.box("step1", 44, 150, 400, 142, "01  Choose scope\nSector + use case + systems\nSelect metrics allowed by your role\nDefine population and failure criteria", "blue", 18)
d.box("step2", 518, 150, 400, 142, "02  Download starter files\nSelected metric profile + synthetic example\nRead metric-specific requirements\nReplace fixtures with your own evidence", "blue", 18)
d.box("step3", 992, 150, 400, 142, "03  Capture and review\nRun systems outside the web workspace\nRetain every declared trial and failure\nAdd required annotations / complete traces", "white", 18)
d.edge("step1", "step2").edge("step2", "step3")
d.box("cases", 44, 372, 400, 160, "cases.jsonl  ·  Test definition\nIDs · sector · provenance · prompts\nReferences or scope flags as required\nGroups / canaries / agent policy if used\nOwner: dataset author + domain reviewer", "white", 18)
d.box("observations", 518, 372, 400, 160, "observations.json  ·  Evidence\nSystems + versions + declared trials\nResponse or error + canonical prompt hash\nMeasurements / labels / trace events\nOwner: collection engineer + adjudicators", "white", 18)
d.box("profile", 992, 372, 400, 160, "profile.json  ·  Measurement plan\nSector + selected metric identifiers\nGrouping dimensions + minimum_cases\nVersion + empty thresholds object\nOwner: study lead", "white", 18)
d.edge("step3", "observations", "assemble all three", points=[(1192,292),(1192,330),(718,330),(718,372)])
d.box("preflight", 44, 630, 400, 146, "04  Check readiness\nValidate all three files and prompt hashes\nShow per-metric evidence availability\nExplain missing / inapplicable inputs\nNo report saved by this check", "amber", 18)
d.box("run", 518, 630, 400, 146, "05  Run evaluation\nRevalidate the current input files\nScore each declared case/system/trial\nAggregate cases; show coverage\nSave only the derived report", "blue", 18)
d.box("inspect", 992, 630, 400, 146, "06  Inspect evidence\nRead scope + denominators + warnings\nCheck failures alongside quality means\nExport report and retain source inputs\nPublish only claims supported by evidence", "green", 18)
d.edge("cases", "preflight", "three-file check", points=[(244,532),(244,630)])
d.edge("observations", "preflight", points=[(718,532),(718,581),(380,581),(380,630)])
d.edge("profile", "preflight", points=[(1192,532),(1192,605),(425,605),(425,630)])
d.edge("preflight", "run", "valid structure").edge("run", "inspect", "saved report")
d.box("states", 44, 845, 1348, 58, "SCORING STATES   Scored = evidence supplied   ·   Missing = required evidence absent   ·   Error = declared failure   ·   N/A = outside the metric’s scope", "gray", 17)
diagrams.append(d)

d = Diagram("03 · Request and evaluation sequence", "03-run-sequence", "Authorization applies to direct API requests; the evaluation endpoint never trusts an earlier preflight")
lanes = [("ui", "Browser", 48), ("api", "HTTP handler", 290), ("auth", "Auth + access", 532), ("val", "Validator / scorer", 774), ("db", "SQLite workspace", 1058)]
for ident, title, x in lanes:
    d.box(ident, x, 145, 216, 68, title, "navy", 18)
    d.box(ident + "line", x + 107, 234, 2, 622, "", "gray", 1)
def seq(ident, a, b, y, label, dashed=False):
    xs = {v[0]: v[2] + 108 for v in lanes}
    d.edge(a + "line", b + "line", label, [(xs[a], y), (xs[b], y)], dashed)
seq("s1", "ui", "api", 272, "1. GET bootstrap / sign in")
seq("s2", "api", "auth", 318, "2. Resolve session and current role")
seq("s3", "auth", "db", 364, "3. Read user + session; never expose password hashes")
seq("s4", "ui", "api", 425, "4. POST /api/validate · three file contents")
seq("s5", "api", "val", 473, "5. Authenticate + authorize + validate + assess availability")
seq("s6", "val", "ui", 521, "6. Return readiness only · no saved evaluation", True)
seq("s7", "ui", "api", 587, "7. POST /api/runs · current three files + name")
seq("s8", "api", "val", 635, "8. Revalidate · score · aggregate · hash inputs and code")
seq("s9", "val", "db", 685, "9. Save derived report with creator owner_id")
seq("s10", "db", "api", 735, "10. Ownership check + allowed metric filtering", True)
seq("s11", "api", "ui", 785, "11. Return report; later reads repeat access checks", True)
d.box("note", 48, 875, 1292, 44, "INVALID RUN → 400; INVALID PREFLIGHT → 200 + valid:false   ·   NO SESSION → 401   ·   NO PERMISSION → 403   ·   INACCESSIBLE REPORT → 404   ·   BUSY EVALUATOR → 409", "gray", 14)
diagrams.append(d)

d = Diagram("04 · Logical data and evidence model", "04-data-model", "SQLite stores identity and derived reports; source input files are retained separately by the research team")
d.box("users", 44, 153, 320, 180, "users\nid (PK) · name · email (unique)\nrole: viewer / researcher / admin\nsalt · password_hash · created\nContains identity, not model credentials", "blue", 17)
d.box("sessions", 438, 153, 320, 180, "sessions\ntoken_hash (PK)\nuser_id · csrf · expires\n12-hour expiration\nCurrent role resolved per request", "blue", 17)
d.box("runs", 832, 153, 550, 180, "runs\nid (PK) · name\nowner_id · shared_sample\nreport: serialized JSON, definitions + results + manifest\nOnly original seed examples are shared", "blue", 17)
d.edge("users", "sessions", "1 : many").edge("users", "runs", "logical owner relationship", points=[(204,333),(204,373),(920,373),(920,333)])
d.box("attempts", 44, 420, 320, 130, "auth_attempts\naddress · attempted\nIndex on address + attempted\nBounded login / registration attempts", "gray", 16)
d.box("manifest", 832, 420, 550, 130, "Report manifest\ndataset_sha256 · observations_sha256\nprofile_sha256 · code_sha256\nSelected cases · trials · bootstrap settings", "green", 18)
d.edge("runs", "manifest", "embedded", points=[(1107,333),(1107,420)])
d.box("cases", 44, 650, 320, 166, "Case dataset  ·  JSONL\nCase ID + messages + sector\nReference / scopes / groups\nCanaries / agent policy (optional)\nCanonical messages digest per case", "white", 17)
d.box("bundle", 438, 650, 436, 166, "Observation bundle  ·  JSON\nSystems + versions + generation settings\nRecords keyed by (system_id, case_id, trial)\nPrompt hash binds each record to messages\nResponse/error + resources + labels + trace", "white", 17)
d.box("profile", 948, 650, 434, 166, "Evaluation profile  ·  JSON\nID + version + sector\nSelected metrics + grouping dimensions\nminimum_cases (starter: 20)\nthresholds: {} in v0.1", "white", 17)
d.edge("cases", "bundle", "case link")
d.edge("bundle", "manifest", "SHA-256", points=[(656,650),(656,590),(998,590),(998,550)])
d.edge("profile", "manifest", "SHA-256", points=[(1165,650),(1165,550)])
d.box("note", 44, 862, 1338, 55, "Relationships shown are logical; the current SQLite schema does not declare SQL foreign keys. Hashes support reconstruction, not provider authentication or tamper-proof custody.", "amber", 16)
diagrams.append(d)

d = Diagram("05 · Requirement-to-evidence chain", "05-evidence-traceability", "A traceable claim links a business need to executable behavior, a check, and preserved evidence")
d.box("need", 44, 161, 382, 142, "Business need\nBR-001…BR-028 in evidence-matrix.csv\nIntended user outcome + acceptance rule\nScope, owner and status are explicit", "navy", 18)
d.box("design", 528, 161, 382, 142, "Technical design\nArchitecture + contracts + roles\nMetric prerequisites + missingness\nDecisions and production gaps", "blue", 18)
d.box("code", 1010, 161, 382, 142, "Implementation\nNamed module and function\nServer checks + scoring rules\nNative UI supports the user journey", "blue", 18)
d.edge("need", "design", "specifies").edge("design", "code", "realizes")
d.box("checks", 1010, 416, 382, 150, "Verification\nNamed unit / API / browser tests\nCommands + dated output\nReadiness + access checks verified\nTest presence alone is not a pass record", "white", 18)
d.edge("code", "checks", "checks behavior", points=[(1201,303),(1201,416)])
d.box("evidence", 528, 416, 382, 150, "Evidence artifact\nReport + manifest + input snapshot\nRubric + reviewer record + raw capture\nVersion / runtime / command log\nOnly derived reports live in SQLite", "green", 18)
d.edge("checks", "evidence", "supports review", points=[(1010,491),(910,491)])
d.box("claim", 44, 416, 382, 150, "Permissible conclusion\nImplementation behavior is testable\nSynthetic outcomes prove fixture behavior\nReal sector performance needs real data\nNo certification or validated global score", "amber", 18)
d.edge("evidence", "claim", "bounds the claim", points=[(528,491),(426,491)])
d.box("research", 44, 678, 640, 158, "Research basis\nP-4: reproducibility and multiple evaluation dimensions\nP-5: clinical context, grounding and privacy\nP-6: disaggregation and controlled pairs\nP-7: threat models, attacks and utility retention", "gray", 17)
d.box("extensions", 758, 678, 634, 158, "Next evidence milestone\nFreeze one independently reviewed sector dataset\nCapture a real single-agent baseline + agent candidate\nValidate rubrics, trace completeness and sample design\nRetain adverse outcomes and matched compute budgets", "gray", 17)
d.edge("research", "claim", "thematic inputs", points=[(204,678),(204,566)], dashed=True)
d.edge("extensions", "evidence", "future substantiation", points=[(948,678),(948,611),(720,611),(720,566)], dashed=True)
d.box("note", 44, 881, 1348, 38, "Paper alignment is thematic. Multi-agent metrics and product authorization rules are implementation extensions; neither is established as validated by the supplied papers.", "white", 15)
diagrams.append(d)


def endpoints(edge, nodes):
    if edge["points"]:
        return edge["points"]
    a, b = nodes[edge["source"]], nodes[edge["target"]]
    if b["x"] >= a["x"] + a["w"]:
        return [(a["x"] + a["w"], a["y"] + a["h"] / 2), (b["x"], b["y"] + b["h"] / 2)]
    return [(a["x"] + a["w"] / 2, a["y"] + a["h"]), (b["x"] + b["w"] / 2, b["y"])]


def write_diagrams():
    mx = ET.Element("mxfile", host="app.diagrams.net", agent="LTEF local design generator", version="24.7.17", type="device")
    for d in diagrams:
        page = ET.SubElement(mx, "diagram", id=d.slug, name=d.name)
        model = ET.SubElement(page, "mxGraphModel", dx=str(W), dy=str(H), grid="1", gridSize="10", guides="1", tooltips="1", connect="1", arrows="1", fold="1", page="1", pageScale="1", pageWidth=str(W), pageHeight=str(H), math="0", shadow="0")
        root = ET.SubElement(model, "root")
        ET.SubElement(root, "mxCell", id="0")
        ET.SubElement(root, "mxCell", id="1", parent="0")
        all_nodes = [dict(id="title", x=44, y=32, w=1350, h=48, text=d.name, tone="white", size=30, dashed=False), dict(id="subtitle", x=44, y=88, w=1350, h=35, text=d.subtitle, tone="white", size=18, dashed=False)] + d.nodes
        by_id = {n["id"]: n for n in all_nodes}
        svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title-{d.slug}">', f'<title id="title-{d.slug}">{html.escape(d.name)}</title>', '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b"/></marker></defs>', '<rect width="1440" height="960" fill="white"/>']
        for i, edge in enumerate(d.edges):
            points = endpoints(edge, by_id)
            style = f'edgeStyle=orthogonalEdgeStyle;rounded=0;html=0;strokeColor={edge["color"]};strokeWidth=1.6;endArrow=block;endFill=1;fontFamily=Helvetica;fontSize=12;fontColor=#455469;labelBackgroundColor=#ffffff;' + ('dashed=1;' if edge['dashed'] else '')
            source, target = by_id[edge["source"]], by_id[edge["target"]]
            sx, sy = (points[0][0]-source["x"])/source["w"], (points[0][1]-source["y"])/source["h"]
            tx, ty = (points[-1][0]-target["x"])/target["w"], (points[-1][1]-target["y"])/target["h"]
            style += f"exitX={sx};exitY={sy};exitPerimeter=0;entryX={tx};entryY={ty};entryPerimeter=0;"
            cell = ET.SubElement(root, "mxCell", id=f"edge{i}", value=edge["label"], style=style, edge="1", parent="1", source=edge["source"], target=edge["target"])
            geom = ET.SubElement(cell, "mxGeometry", relative="1", **{"as": "geometry"})
            ET.SubElement(geom, "mxPoint", x=str(points[0][0]), y=str(points[0][1]), **{"as": "sourcePoint"})
            ET.SubElement(geom, "mxPoint", x=str(points[-1][0]), y=str(points[-1][1]), **{"as": "targetPoint"})
            if len(points) > 2:
                arr = ET.SubElement(geom, "Array", **{"as": "points"})
                for x, y in points[1:-1]:
                    ET.SubElement(arr, "mxPoint", x=str(x), y=str(y))
            poly = ' '.join(f'{x},{y}' for x, y in points)
            dash = ' stroke-dasharray="7 5"' if edge["dashed"] else ''
            svg.append(f'<polyline points="{poly}" fill="none" stroke="{edge["color"]}" stroke-width="1.6" marker-end="url(#arrow)"{dash}/>')
            if edge["label"]:
                a, b = points[0], points[1]
                x, y = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2 - 10
                label = edge["label"]
                # Long sequence labels fit between their participating lanes.
                size = 14 if len(label) < 60 else 13
                if len(points) == 2 and abs(b[0] - a[0]) < 180:
                    size = 12
                if a[0] == b[0]:
                    x += 16
                svg.append(f'<text x="{x}" y="{y}" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-size="{size}" fill="#455469" stroke="white" stroke-width="5" paint-order="stroke">{html.escape(label)}</text>')
        for n in all_nodes:
            fill, stroke, fg = COLORS[n["tone"]]
            # Keep previews legible and text within native shapes.
            if n["id"] not in ("title", "subtitle") and n["text"]:
                longest = max(len(line) for line in n["text"].split("\n"))
                n["size"] = min(n["size"], (n["w"] - 24) / max(1, longest * .57))
            special = n["id"] in ("title", "subtitle")
            style = f'rounded=1;whiteSpace=wrap;html=0;fillColor={fill};strokeColor={"none" if special else stroke};fontColor={fg};fontFamily=Helvetica;fontSize={n["size"]};align={"left" if special else "center"};verticalAlign=middle;spacing=12;arcSize=8;' + ('dashed=1;' if n['dashed'] else '')
            cell = ET.SubElement(root, "mxCell", id=n["id"], value=n["text"], style=style, vertex="1", parent="1")
            ET.SubElement(cell, "mxGeometry", x=str(n["x"]), y=str(n["y"]), width=str(n["w"]), height=str(n["h"]), **{"as": "geometry"})
            if not special:
                dash = ' stroke-dasharray="7 5"' if n["dashed"] else ''
                svg.append(f'<rect x="{n["x"]}" y="{n["y"]}" width="{n["w"]}" height="{n["h"]}" rx="10" fill="{fill}" stroke="{stroke}"{dash}/>')
            lines = n["text"].split('\n')
            y0 = n["y"] + n["h"] / 2 - (len(lines) - 1) * n["size"] * .68 + n["size"] * .32
            anchor = "start" if special else "middle"
            x = n["x"] if special else n["x"] + n["w"] / 2
            for i, line in enumerate(lines):
                weight = "700" if i == 0 and n["id"] != "subtitle" else "400"
                svg.append(f'<text x="{x}" y="{y0 + i * n["size"] * 1.36}" text-anchor="{anchor}" font-family="Arial,Helvetica,sans-serif" font-size="{n["size"]}" font-weight="{weight}" fill="{fg}">{html.escape(line)}</text>')
        svg.append('</svg>')
        (OUT / (d.slug + ".svg")).write_text('\n'.join(svg), encoding="utf-8")
    ET.indent(mx, space="  ")
    ET.ElementTree(mx).write(OUT / "LTEF-technical-design.drawio", encoding="utf-8", xml_declaration=True)


def inline(text):
    text = html.escape(text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    return text


def build_html():
    md = (OUT / "technical-design.md").read_text(encoding="utf-8")
    parts, toc = [], []
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("```"):
            code = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            parts.append('<pre><code>' + html.escape('\n'.join(code)) + '</code></pre>')
        elif line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            title = line[level:].strip()
            ident = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
            parts.append(f'<h{level} id="{ident}">{inline(title)}</h{level}>')
            if level == 2:
                toc.append(f'<a href="#{ident}">{html.escape(title)}</a>')
        elif line.startswith("!["):
            match = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', line)
            if match:
                asset = OUT / match.group(2)
                parts.append('<figure>' + asset.read_text(encoding="utf-8") + '<figcaption>' + inline(match.group(1)) + '</figcaption></figure>')
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                row = [v.strip() for v in lines[i].strip('|').split('|')]
                if not all(re.fullmatch(r'[: -]+', v) for v in row):
                    rows.append(row)
                i += 1
            parts.append('<div class="table-wrap"><table><thead><tr>' + ''.join('<th>' + inline(v) + '</th>' for v in rows[0]) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + inline(v) + '</td>' for v in row) + '</tr>' for row in rows[1:]) + '</tbody></table></div>')
            i -= 1
        elif re.match(r'^(- |\d+\. )', line):
            ordered = not line.startswith('- ')
            tag = 'ol' if ordered else 'ul'
            rows = []
            while i < len(lines) and re.match(r'^(- |\d+\. )', lines[i]):
                rows.append(re.sub(r'^(- |\d+\. )', '', lines[i]))
                i += 1
            parts.append('<' + tag + '>' + ''.join('<li>' + inline(v) + '</li>' for v in rows) + '</' + tag + '>')
            i -= 1
        elif line.startswith('> '):
            parts.append('<aside class="callout">' + inline(line[2:]) + '</aside>')
        else:
            para = [line]
            while i + 1 < len(lines) and lines[i+1].strip() and not re.match(r'^(#|\||!\[|```|> |[-] |\d+\. )', lines[i+1]):
                i += 1
                para.append(lines[i])
            parts.append('<p>' + inline(' '.join(para)) + '</p>')
        i += 1
    matrix = list(csv.DictReader((OUT / "evidence-matrix.csv").open(encoding="utf-8")))
    matrix_html = '<h2 id="full-evidence-matrix">Appendix · Complete evidence matrix</h2><p>Each row identifies a need, an observable acceptance criterion, implementation evidence, and the remaining limit. Paths are relative to the LTEF project root. Named tests require a dated execution record before being described as passing.</p><div class="matrix">'
    for row in matrix:
        matrix_html += '<article class="requirement"><div class="req-head"><span>' + html.escape(row['BR ID']) + '</span><span class="status">' + html.escape(row['Status']) + '</span></div><h3>' + html.escape(row['Business need']) + '</h3><p><strong>Acceptance:</strong> ' + html.escape(row['Acceptance criterion']) + '</p><dl>'
        for key in ('Implementation', 'File / function', 'Test / evidence', 'Gap / next action', 'Responsible role'):
            matrix_html += '<dt>' + html.escape(key) + '</dt><dd>' + html.escape(row[key]) + '</dd>'
        matrix_html += '</dl></article>'
    matrix_html += '</div>'
    css = '''
:root{--ink:#18273d;--muted:#55657a;--blue:#305ecb;--line:#dfe5ed;--pale:#f5f7fb}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f5f7fb;color:var(--ink);font:16px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif}a{color:var(--blue);text-decoration-thickness:1px;text-underline-offset:3px}.shell{display:grid;grid-template-columns:260px minmax(0,1fr);max-width:1600px;margin:auto}.nav{padding:42px 25px;position:sticky;top:0;align-self:start;max-height:100vh;overflow:auto}.brand{font-weight:750;letter-spacing:.18em;font-size:17px}.tag{font-size:12px;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);margin:10px 0 24px}.nav a{display:block;font-size:13px;line-height:1.4;text-decoration:none;color:var(--muted);margin:0 0 13px}.nav a:hover{color:var(--blue)}main{min-width:0;background:white;padding:60px clamp(28px,5vw,84px) 90px;border-left:1px solid var(--line)}.eyebrow{color:var(--blue);font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.15em}h1{font-family:Georgia,serif;font-weight:400;font-size:clamp(36px,4vw,58px);letter-spacing:-.04em;line-height:1.08;max-width:860px;margin:20px 0 24px}h2{font-size:26px;font-weight:650;letter-spacing:-.025em;margin:66px 0 18px;padding-top:18px;border-top:1px solid var(--line);scroll-margin-top:20px}h3{font-size:19px;line-height:1.4;margin:30px 0 10px}p,li{max-width:88ch}p{margin:0 0 18px}li{padding-left:5px;margin:0 0 10px}strong{font-weight:650}code{font:13px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace;background:#f1f4f8;padding:2px 5px;border-radius:4px;overflow-wrap:anywhere}pre{background:#142b4b;color:#e9f0fc;padding:24px;border-radius:12px;overflow:auto;font-size:13px}pre code{color:inherit;background:none;padding:0}.callout{border-left:3px solid var(--blue);background:#f0f5ff;padding:20px 24px;margin:24px 0;font-size:15px}.table-wrap{overflow:auto;margin:24px 0 30px}table{width:100%;border-collapse:collapse;font-size:13px;line-height:1.6}th{text-align:left;background:#eef2f8;font-weight:650;color:#304058;padding:13px;vertical-align:top}td{border-bottom:1px solid var(--line);padding:13px;vertical-align:top}figure{margin:28px -10px 36px;border:1px solid var(--line);border-radius:12px;padding:12px;background:#fff;break-inside:avoid}figure svg{display:block;width:100%;height:auto}figcaption{padding:8px 12px;color:var(--muted);font-size:12px}.matrix{display:grid;grid-template-columns:1fr;gap:18px}.requirement{border:1px solid var(--line);border-radius:10px;padding:22px;break-inside:avoid}.requirement h3{margin:12px 0}.requirement p{font-size:14px}.req-head{display:flex;gap:16px;justify-content:space-between;color:var(--blue);font-size:12px;font-weight:700;letter-spacing:.03em}.status{color:var(--muted);background:#f0f3f8;padding:2px 8px;border-radius:20px}dl{display:grid;grid-template-columns:145px minmax(0,1fr);font-size:12px;gap:8px 15px;margin:0}dt{color:var(--muted);font-weight:650}dd{margin:0;overflow-wrap:anywhere}.footer{margin-top:55px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:20px}@media(max-width:950px){.shell{display:block}.nav{position:static;max-height:none;padding:20px 28px}.nav nav{display:none}main{border:0;padding-top:35px}figure{margin-left:0;margin-right:0}.brand{font-size:15px}.tag{margin-bottom:0}dl{grid-template-columns:1fr;gap:4px}dd{margin-bottom:9px}}@media print{@page{size:A4;margin:17mm 14mm}body{background:white;font-size:10pt;line-height:1.45}.shell{display:block;max-width:none}.nav{display:none}main{border:0;padding:0}h1{font-size:34pt}h2{font-size:19pt;margin-top:26pt;break-after:avoid}h3{font-size:13pt;break-after:avoid}p,li{max-width:none}a{color:#163566}table{font-size:8pt}th,td{padding:7pt}figure{margin:16pt 0;page-break-inside:avoid}figure svg{max-height:155mm}pre{white-space:pre-wrap;font-size:8pt}.callout{padding:12pt;font-size:10pt}.requirement{padding:12pt}.requirement p{font-size:9pt}dl{font-size:8pt}code{font-size:8pt}.req-head{font-size:8pt}.table-wrap{overflow:visible}.status{background:none}.footer{font-size:8pt}}
'''
    document = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="LTEF local technical design, data provision guide, diagrams and BRD implementation evidence matrix"><title>LTEF · Technical design and evidence matrix</title><style>' + css + '</style></head><body><div class="shell"><aside class="nav"><div class="brand">LTEF</div><div class="tag">Research implementation<br>Design review · 20 Sep 2026</div><nav>' + ''.join(toc) + '<a href="#full-evidence-matrix">Complete evidence matrix</a></nav></aside><main><div class="eyebrow">Technical design / Business requirements / Implementation evidence</div>' + ''.join(parts) + matrix_html + '<div class="footer">Prepared from the local LTEF source and research protocol. Keep source inputs and dated verification logs alongside this review package. Editable diagrams: LTEF-technical-design.drawio.</div></main></div></body></html>'
    (OUT / "technical-design.html").write_text(document, encoding="utf-8")


if __name__ == "__main__":
    write_diagrams()
    build_html()
    print("Generated five SVG previews, five-page native draw.io source, and standalone technical-design.html")
