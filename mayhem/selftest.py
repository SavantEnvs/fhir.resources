# Ported to the pydantic-v1-era fhir.resources API at UPSTREAM (parse_raw/parse_obj/.dict()/.json()) —
# the current live selftest.py uses pydantic-v2 methods (model_validate_json/model_dump_json) that
# do not exist at this commit.
import json
from fhir.resources.patient import Patient
from fhir.resources.organization import Organization
from pydantic.error_wrappers import ValidationError

p = Patient.parse_raw('{"resourceType":"Patient","id":"ex","gender":"male","active":true}')
assert p.id == "ex", p.id
assert p.gender == "male", p.gender
assert p.active is True, p.active
d = json.loads(p.json())
assert d["gender"] == "male", d
try:
    # fhirtypes.Code requires at least one non-whitespace char (regex ^[^\s]+(\s[^\s]+)*$); an
    # empty string can never match, but a bare int like 12345 pydantic-coerces to "12345" and
    # passes — FHIR's Code type is an unbound string, not an enum, so digits are a valid code.
    Patient.parse_raw('{"resourceType":"Patient","gender":""}')
    raise SystemExit("BUG: invalid gender accepted")
except ValidationError:
    pass
o = Organization.parse_obj({"resourceType": "Organization", "name": "Acme"})
assert o.name == "Acme", o.name
print("SELFTEST_PASS patient_gender=%s org_name=%s" % (p.gender, o.name))
