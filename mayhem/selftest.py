import json
from fhir.resources.patient import Patient
from fhir.resources.organization import Organization
from pydantic import ValidationError

p = Patient.model_validate_json('{"resourceType":"Patient","id":"ex","gender":"male","active":true}')
assert p.id == "ex", p.id
assert p.gender == "male", p.gender
assert p.active is True, p.active
d = json.loads(p.model_dump_json())
assert d["gender"] == "male", d
try:
    Patient.model_validate_json('{"resourceType":"Patient","gender":12345}')
    raise SystemExit("BUG: invalid gender accepted")
except ValidationError:
    pass
o = Organization.model_validate({"resourceType":"Organization","name":"Acme"})
assert o.name == "Acme", o.name
print("SELFTEST_PASS patient_gender=%s org_name=%s" % (p.gender, o.name))
