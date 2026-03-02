# Version: 0.1.0

import json


def test_manifest_schema_placeholder():
    data = {"schema_version": 1, "operations": []}
    assert json.loads(json.dumps(data))["schema_version"] == 1
