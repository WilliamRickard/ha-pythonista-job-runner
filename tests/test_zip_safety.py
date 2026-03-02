# Version: 0.1.0

import zipfile
from io import BytesIO


def test_zip_path_traversal_example_is_detectable_by_policy():
    # Placeholder test; real validator will be implemented later.
    bio = BytesIO()
    with zipfile.ZipFile(bio, "w") as zf:
        zf.writestr("../evil.txt", "nope")
    bio.seek(0)
    with zipfile.ZipFile(bio, "r") as zf:
        names = zf.namelist()
    assert any(n.startswith("..") for n in names)
