#! /usr/bin/env python3
import atheris
import json
import random
import sys

import fuzz_helpers

with atheris.instrument_imports(include=['fhir.resources', 'fhir_core']):
    from fhir.resources import get_fhir_model_class
    from fhir.resources.patient import Patient
    from fhir.resources.organization import Organization
    from pydantic import ValidationError

# Representative FHIR R5 resource types exercised by the generic-parse path. A curated list keeps
# harness startup fast (importing all ~200 models would stall the fuzzer's first iterations).
available_class_names = [
    'Patient', 'Organization', 'Observation', 'Condition', 'Encounter', 'Procedure',
    'MedicationRequest', 'Bundle', 'Practitioner', 'AllergyIntolerance', 'DiagnosticReport',
    'Immunization', 'CarePlan', 'Goal', 'Device', 'Location', 'Medication',
    'DocumentReference', 'Coverage', 'Claim', 'ServiceRequest', 'Specimen', 'RelatedPerson',
    'Appointment', 'CodeableConcept', 'Quantity', 'HumanName', 'Address', 'ContactPoint',
]

# ---------------------------------------------------------------------------------------------
# Mutation-based seeding: this repo has no committed seed corpus (see mayhem/Mayhemfile — Mayhem's
# server-tar accumulation is structurally broken for this project's dotted upstream name, and a
# local-only file:// seed is itself a forbidden gate form). Feeding raw fuzzer bytes straight into
# model_validate_json() means json.loads() rejects nearly every input before any real FHIR
# validation logic runs (confirmed: ~3 edges covered, all in the JSON-decode-failure path).
# Instead, start from a known-valid FHIR resource (a full nested Patient with extensions,
# identifiers, contained resources, etc.) and let the fuzzer mutate individual leaf values —
# JSON structure/keys stay intact so parsing succeeds, and the fuzzer-controlled entropy lands on
# the actual field CONTENT (dates, codes, references, enums, decimals) that pydantic/FHIR
# validation exercises.
# ---------------------------------------------------------------------------------------------
_PATIENT_TEMPLATE = json.loads(r'''
{"resourceType": "Patient", "identifier": [{"period": {"start": "2001-05-06"}, "assigner": {"display": "Acme Healthcare"}, "use": "usual", "system": "urn:oid:1.2.36.146.595.217.0.1", "value": "12345"}], "managingOrganization": {"reference": "Organization/1936778"}, "_active": {"extension": [{"url": "http://example.org/fhir/StructureDefinition/recordStatus", "valueCode": "archived"}]}, "name": [{"given": ["Peter", "James"], "use": "official", "family": "Chalmers"}, {"given": ["Jim"], "use": "usual"}], "extension": [{"url": "http://example.org/fhir/StructureDefinition/patientAvatar", "valueReference": {"reference": "#pic1", "display": "Duck image"}}, {"url": "http://example.org/fhir/StructureDefinition/complexExtensionExample", "extension": [{"url": "nestedA", "valueCoding": {"system": "http://demo.org/id/4", "code": "AB45", "extension": [{"url": "http://example.org/fhir/StructureDefinition/extraforcodingWithExt", "extension": [{"url": "extra1", "valueString": "extra info"}]}, {"url": "http://example.org/fhir/StructureDefinition/extraforcodingWithValue", "valueInteger": 45}]}}, {"url": "nestedB", "id": "q4", "extension": [{"url": "nestedB1", "valueString": "hello"}]}]}], "modifierExtension": [{"url": "http://example.org/fhir/StructureDefinition/pi", "valueDecimal": 3.141592653589793}, {"url": "http://example.org/fhir/StructureDefinition/max-decimal-precision", "valueDecimal": 1.0006502214162465}], "gender": "male", "_gender": {"fhir_comments": "This is comment for Gender"}, "birthDate": "1974-12", "deceasedBoolean": true, "address": [{"fhir_comments": "This is comment for Address.No 1", "use": "home", "line": ["534 Erewhon St"], "city": "PleasantVille", "state": "Vic", "postalCode": "3999"}], "maritalStatus": {"extension": [{"url": "http://example.org/fhir/StructureDefinition/nullFlavor", "valueCode": "ASKU", "fhir_comments": "This is comment for maritalStatus. Ext 1"}]}, "multipleBirthInteger": 3, "contact": [{"name": {"family": "du Marche", "given": ["Benedicte", "Denise", "Marie"]}, "relationship": [{"coding": [{"system": "http://example.org/fhir/CodeSystem/patient-contact-relationship", "code": "partner"}]}], "telecom": [{"system": "phone", "value": "+33 (237) 998327"}]}], "generalPractitioner": [{"reference": "#org3141"}], "telecom": [{"use": "home"}, {"system": "phone", "value": "(03) 5555 6473", "use": "work"}], "meta": {"tag": [{"system": "http://terminology.hl7.org/CodeSystem/v3-ActReason", "code": "HTEST", "display": "test health data"}]}}
''')

_ORGANIZATION_TEMPLATE = {
    "resourceType": "Organization",
    "identifier": [{"system": "urn:ietf:rfc:3986", "value": "2.16.840.1.113883.19.5"}],
    "active": True,
    "name": "Good Health Clinic",
    "alias": ["GHC"],
    "telecom": [{"system": "phone", "value": "(03) 5555 6473", "use": "work"}],
    "address": [{"use": "work", "line": ["534 Erewhon St"], "city": "PleasantVille", "state": "Vic", "postalCode": "3999"}],
    "contact": [{"purpose": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/contactentity-type", "code": "ADMIN"}]}}],
}


def _mutate(obj, fdp, budget):
    """Walk a valid template, replacing a fraction of leaf string/number values with
    fuzzer-controlled data while leaving the JSON structure (keys, nesting, types) intact."""
    if budget[0] <= 0:
        return obj
    if isinstance(obj, dict):
        return {k: _mutate(v, fdp, budget) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_mutate(v, fdp, budget) for v in obj]
    if isinstance(obj, str):
        budget[0] -= 1
        if fdp.ConsumeBool():
            return fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 24))
        return obj
    if isinstance(obj, (int, float)) and not isinstance(obj, bool):
        budget[0] -= 1
        if fdp.ConsumeBool():
            return fdp.ConsumeRegularFloat() if isinstance(obj, float) else fdp.ConsumeInt(4)
        return obj
    return obj


def TestOneInput(data):
    fdp = fuzz_helpers.EnhancedFuzzedDataProvider(data)
    test = fdp.ConsumeIntInRange(0, 2)
    # Bound how many leaves get mutated per input so long-running fuzzer bytes are exhausted
    # gracefully rather than raising once ConsumeBool()/ConsumeInt() run out of entropy.
    budget = [fdp.ConsumeIntInRange(0, 40)]

    try:
        if test == 0:
            mutated = _mutate(json.loads(json.dumps(_ORGANIZATION_TEMPLATE)), fdp, budget)
            Organization.model_validate(mutated)
        elif test == 1:
            mutated = _mutate(json.loads(json.dumps(_PATIENT_TEMPLATE)), fdp, budget)
            Patient.model_validate(mutated)
        elif test == 2:
            mutated = _mutate(json.loads(json.dumps(_PATIENT_TEMPLATE)), fdp, budget)
            klass = get_fhir_model_class(fdp.PickValueInList(available_class_names))
            klass.model_validate(mutated)
    except (ValidationError, json.JSONDecodeError, ValueError, TypeError, KeyError, AttributeError):
        return -1
    except LookupError as e:
        if random.random() > 0.9:
            raise e
        return -1


def main():
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
