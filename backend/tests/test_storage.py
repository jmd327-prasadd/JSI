from __future__ import annotations

from pathlib import Path

from app.storage.zip_extract import safe_extract
from tests.fixtures.builder import write_fixture_project, zip_dir


def test_extraction_skips_git_and_other_noise_dirs(tmp_path):
    """Regression test: .git contains deeply-nested, long-named object files
    that, combined with this app's UUID-heavy storage path, can exceed
    Windows' 260-char MAX_PATH and fail extraction with a misleading
    "No such file or directory" error. .git (and other SKIP-listed dirs)
    must never be extracted at all -- they're never analyzed anyway.
    """
    src = write_fixture_project(tmp_path / "src", {
        "dbt_project.yml": "name: 'x'\nversion: '1.0.0'\nprofile: 'x'\n",
        "models/m.sql": "select 1\n",
        # a git-object-shaped path -- realistic long hash-named file
        ".git/objects/02/897eea6f6e991c79b3ffe22eee36299cded085": "binary-ish content",
        ".git/HEAD": "ref: refs/heads/main\n",
        "node_modules/some_pkg/index.js": "module.exports = {};\n",
    })
    zip_path = zip_dir(src, tmp_path / "project.zip")

    dest = tmp_path / "extracted"
    safe_extract(zip_path, dest)

    assert (dest / "dbt_project.yml").exists()
    assert (dest / "models" / "m.sql").exists()
    assert not (dest / ".git").exists()
    assert not (dest / "node_modules").exists()
