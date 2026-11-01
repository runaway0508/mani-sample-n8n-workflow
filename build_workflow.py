"""Generates workflows/lead-intake.json (kept as code so the node graph is reviewable)."""
import json

SAMPLE = """return [
  { name: 'Mina Park',  email: 'mina@example.com', budget_usd: 1200, message: 'Need a weekly sales report' },
  { name: 'John Doe',   email: 'john[at]example',  budget_usd: 300,  message: 'Scrape 3 sites' },
  { name: 'Aiko Sato',  email: 'aiko@example.jp',  budget_usd: 80,   message: 'Small Google Sheets fix' },
  { name: '',           email: 'blank@example.com', budget_usd: 0,   message: '' },
].map(j => ({ json: j }));"""

VALIDATE = r"""const rate = $('USD to KRW rate').first().json.rates.KRW;
const emailOk = e => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e || '');
return $('Sample leads (replace with Webhook/Form)').all().map(({ json: l }) => {
  const problems = [];
  if (!l.name) problems.push('missing name');
  if (!emailOk(l.email)) problems.push('invalid email');
  if (!(l.budget_usd > 0)) problems.push('no budget');
  const tier = l.budget_usd >= 1000 ? 'A' : l.budget_usd >= 200 ? 'B' : 'C';
  return { json: { ...l, budget_krw: Math.round(l.budget_usd * rate), rate_date: $('USD to KRW rate').first().json.date,
                   tier, valid: problems.length === 0, problems } };
});"""

QUALIFIED = """return $input.all().map(({ json: l }) => ({ json: {
  crm_row: [l.name, l.email, l.tier, l.budget_usd, l.budget_krw, l.message],
  notify: `New ${l.tier}-tier lead: ${l.name} (${l.budget_krw.toLocaleString('en-US')} KRW)`,
}}));"""

REVIEW = """return $input.all().map(({ json: l }) => ({ json: { review: l.email || '(no email)', problems: l.problems.join(', ') } }));"""


def node(name, typ, ver, pos, params, **extra):
    return {"id": name.lower().replace(" ", "-")[:30], "name": name, "type": typ, "typeVersion": ver,
            "position": pos, "parameters": params, **extra}


nodes = [
    node("Run manually", "n8n-nodes-base.manualTrigger", 1, [0, 0], {}),
    node("Sample leads (replace with Webhook/Form)", "n8n-nodes-base.code", 2, [220, 0], {"jsCode": SAMPLE}),
    node("USD to KRW rate", "n8n-nodes-base.httpRequest", 4.2, [440, 0],
         {"url": "https://api.frankfurter.dev/v1/latest?from=USD&to=KRW", "options": {}}, executeOnce=True),
    node("Validate and score", "n8n-nodes-base.code", 2, [660, 0], {"jsCode": VALIDATE}),
    node("Valid?", "n8n-nodes-base.if", 2, [880, 0], {"conditions": {
        "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
        "conditions": [{"id": "c1", "leftValue": "={{ $json.valid }}", "rightValue": True,
                        "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
        "combinator": "and"}, "options": {}}),
    node("Qualified: CRM row + alert text", "n8n-nodes-base.code", 2, [1100, -100], {"jsCode": QUALIFIED}),
    node("Needs human review", "n8n-nodes-base.code", 2, [1100, 100], {"jsCode": REVIEW}),
]
link = lambda to: {"main": [[{"node": to, "type": "main", "index": 0}]]}
connections = {
    "Run manually": link("Sample leads (replace with Webhook/Form)"),
    "Sample leads (replace with Webhook/Form)": link("USD to KRW rate"),
    "USD to KRW rate": link("Validate and score"),
    "Validate and score": link("Valid?"),
    "Valid?": {"main": [[{"node": "Qualified: CRM row + alert text", "type": "main", "index": 0}],
                         [{"node": "Needs human review", "type": "main", "index": 0}]]},
}
wf = {"id": "maniLeadIntake01", "name": "MANI sample - lead intake, validate, convert, route", "nodes": nodes,
      "connections": connections, "settings": {"executionOrder": "v1"}, "active": False, "pinData": {}}
json.dump(wf, open("workflows/lead-intake.json", "w"), indent=2, ensure_ascii=False)
print("wrote workflows/lead-intake.json", len(nodes), "nodes")
