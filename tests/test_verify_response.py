import json
from pathlib import Path
from scripts.verify_response import main

def test_verifier_rejects_corrupted_gap(tmp_path):
    source=Path('docs/sample_responses/dallas_chicago.json')
    body=json.loads(source.read_text(encoding='utf-8-sig'))
    body['fuel_stops'][1]['mile_marker']=700
    target=tmp_path/'corrupt.json'; target.write_text(json.dumps(body),encoding='utf-8')
    assert main(str(target)) == 1
