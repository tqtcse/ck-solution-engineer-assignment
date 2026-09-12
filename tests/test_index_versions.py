import json
import re

import pytest

from app import config, retrieval

VERSIONS = ("v1", "v2")


@pytest.mark.parametrize("version", VERSIONS)
def test_both_versions_are_shipped(version):
    assert config.index_path(version).exists()
    assert config.chunks_path(version).exists()


@pytest.mark.parametrize("version", VERSIONS)
def test_vectors_and_chunks_line_up(version):
    vecs, chunks = retrieval._index(version)
    assert len(vecs) == len(chunks)
    assert vecs.shape[1] == config.EMBED_DIM


@pytest.mark.parametrize("version", VERSIONS)
def test_every_chunk_knows_its_page(version):
    _, chunks = retrieval._index(version)
    assert all(isinstance(c.get("page"), int) for c in chunks)


def test_the_two_versions_are_actually_different():
    _, v1 = retrieval._index("v1")
    _, v2 = retrieval._index("v2")
    assert [c["text"] for c in v1] != [c["text"] for c in v2]


def test_v2_carries_metadata_prefixes_and_v1_does_not():
    _, v1 = retrieval._index("v1")
    _, v2 = retrieval._index("v2")
    prefix = re.compile(r"^\[page \d+")
    assert sum(bool(prefix.match(c["text"])) for c in v2) == len(v2)
    assert sum(bool(prefix.match(c["text"])) for c in v1) == 0


@pytest.mark.parametrize("figure", ["596", "493"])
def test_v1_lost_figures_that_v2_keeps(figure):
    _, v1 = retrieval._index("v1")
    _, v2 = retrieval._index("v2")
    assert figure not in json.dumps([c["text"] for c in v1])
    assert figure in json.dumps([c["text"] for c in v2])


def test_dockerfile_ships_every_version_the_switch_can_select():
    dockerfile = (config.ROOT / "Dockerfile").read_text(encoding="utf8")
    for version in VERSIONS:
        assert f"index_{version}.npz" in dockerfile
        assert f"chunks_{version}.jsonl" in dockerfile


def test_terraform_default_selects_a_shipped_version():
    tf = (config.ROOT / "infra" / "variables.tf").read_text(encoding="utf8")
    default = re.search(r'variable "index_version".*?default\s*=\s*"(\w+)"', tf, re.S).group(1)
    assert default in VERSIONS
    assert f"index_{default}.npz" in (config.ROOT / "Dockerfile").read_text(encoding="utf8")
