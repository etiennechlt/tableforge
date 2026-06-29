import pytest

from tableforge.config import ProviderConfig
from tableforge.providers import SeedreamProvider, build_request, summarize_request


def _cfg():
    return ProviderConfig(base_url="https://ark.x/api/v3", api_key_env="ARK_API_KEY",
                          model="seedream-5-0-260128")


def test_build_request_shapes_extra_body():
    req = build_request(model="m", size="64x64", refs=["data:..a", "data:..b"],
                        watermark=False, output_format="png")
    assert req["model"] == "m"
    assert req["size"] == "64x64"
    assert req["extra_body"]["image"] == ["data:..a", "data:..b"]
    assert req["extra_body"]["watermark"] is False
    assert req["extra_body"]["output_format"] == "png"


def test_build_request_omits_image_when_no_refs():
    req = build_request(model="m", size="64x64", refs=[], watermark=False, output_format="png")
    assert "image" not in req["extra_body"]


def test_summarize_hides_data_urls():
    req = build_request(model="m", size="64x64", refs=["a", "b"], watermark=False, output_format="png")
    summary = summarize_request(req)
    assert summary["extra_body"]["image"] == "[2 référence(s), data-URLs omises]"


def test_from_config_requires_key(monkeypatch):
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ARK_API_KEY"):
        SeedreamProvider.from_config(_cfg())


def test_from_config_reads_key(monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "secret")
    provider = SeedreamProvider.from_config(_cfg())
    assert provider.api_key == "secret"
    assert provider.model == "seedream-5-0-260128"


def test_provider_build_injects_prompt(monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "secret")
    provider = SeedreamProvider.from_config(_cfg())
    req = provider.build("hello", size="32x32", refs=["a"])
    assert req["prompt"] == "hello"
    assert req["size"] == "32x32"
