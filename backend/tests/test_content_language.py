"""1.2.53 issue #5c / #1c: one content language drives titles and publish metadata."""

import pytest

from sharkyclips import config, languages, perf, youtube

KEYS = ("output_language", "content_language", "ui_language", "spanish_variant", "performance_preset",
        "processing_device", "light_checked", "light_auto_picked", "llm_enabled")


@pytest.fixture(autouse=True)
def _restore_config():
    """These tests change languages / the Light preset: later tests must not inherit them."""
    before = config.load()
    yield
    cfg = config.load()
    for k in KEYS:
        if k in before:
            cfg[k] = before[k]
        else:
            cfg.pop(k, None)
    config.save(cfg)


def test_tier1_languages():
    assert languages.codes() == ["en", "tr", "es", "pt", "ru", "de", "fr", "ar", "zh", "ja", "hu"]
    assert languages.get("pt-BR").code == "pt" and languages.get("es-419").code == "es"
    assert languages.is_rtl("ar") and not languages.is_rtl("ja")


def test_content_language_follows_the_setting_not_old_analyses():
    config.update(output_language="tr", content_language="tr", ui_language="tr")
    assert languages.content_language() == "tr"
    config.update(output_language="es", content_language="es")
    assert languages.content_language() == "es"  # the next titles: Spanish
    assert languages.content_language("fr") == "fr"  # an explicit choice for this run wins


def test_no_silent_turkish_default():
    cfg = config.load()
    for k in ("output_language", "content_language", "ui_language"):
        cfg.pop(k, None)
    config.save(cfg)
    assert config.DEFAULTS["ui_language"] == "en" and config.DEFAULTS["output_language"] == "en"
    assert languages.content_language() == "en"


def test_youtube_metadata_language_and_spanish_variant():
    config.update(output_language="es", spanish_variant="es-419")
    body = youtube.build_body("Título", "desc", [], "private", None, False, "20", None, audio_language="tr")
    assert body["snippet"]["defaultLanguage"] == "es-419"
    assert body["snippet"]["defaultAudioLanguage"] == "tr"
    config.update(spanish_variant="es-ES")
    assert youtube.build_body("x", "", [], "private", None, False, "20", "es")["snippet"]["defaultLanguage"] == "es"
    assert youtube.build_body("x", "", [], "private", None, False, "20", "pt")["snippet"]["defaultLanguage"] == "pt-BR"


def test_settings_api_content_language():
    from fastapi.testclient import TestClient

    from sharkyclips.web.app import app

    client = TestClient(app)
    r = client.put("/api/settings", json={"content_language": "ja"})
    assert r.status_code == 200 and r.json()["output_language"] == "ja"
    r = client.put("/api/settings", json={"spanish_variant": "xx"})
    assert r.status_code >= 400


def test_light_preset_on_a_weak_pc(monkeypatch):
    monkeypatch.setenv("SHARKYCLIPS_SIM_RAM_GB", "8")
    monkeypatch.setenv("SHARKYCLIPS_SIM_THREADS", "4")
    monkeypatch.setenv("SHARKYCLIPS_SIM_NO_GPU", "1")
    config.update(performance_preset="auto", processing_device="auto", light_checked=False, llm_enabled=True)
    assert perf.is_weak() and perf.device() == "cpu" and perf.light()
    k = perf.knobs()
    assert k["whisper_model"] == "small" and k["llm_model"] == perf.LIGHT_LLM and not k["voices"]
    assert k["cpu_threads"] == 2 and k["one_job"]  # physical cores
    assert perf.first_run_pick() and config.get("performance_preset") == "light"
    est = perf.estimate(17 * 60)
    assert est["slow_pc"] and est["seconds"] > 0


def test_cpu_only_and_template_titles(monkeypatch):
    monkeypatch.setenv("SHARKYCLIPS_SIM_RAM_GB", "4")
    config.update(performance_preset="light", processing_device="cpu")
    k = perf.knobs()
    assert k["device"] == "cpu" and k["template_titles"] and k["llm_model"] is None
    from sharkyclips import llm

    assert llm.placement("qwen3.5:2b", 4096)["num_gpu"] == 0  # never the integrated GPU


@pytest.mark.parametrize("gpu, dedicated", [
    ("AMD Radeon RX 7900 GRE", True), ("Intel(R) Arc(TM) B580 Graphics", True), ("Intel(R) Arc(TM) A770 Graphics", True),
    ("AMD Radeon Pro W7600", True), ("Intel(R) Arc(TM) Pro A60M Graphics", True),
    ("AMD Radeon(TM) Graphics", False), ("AMD Radeon 780M Graphics", False), ("Radeon RX Vega 11 Graphics", False),
    ("Intel(R) Arc(TM) Graphics", False), ("Intel(R) Arc(TM) Pro Graphics", False), ("Intel(R) Arc(TM) 140V GPU", False),
    ("Intel(R) UHD Graphics 620", False), ("Intel(R) Iris(R) Xe Graphics", False),
])
def test_llm_may_use_a_dedicated_amd_or_intel_card(monkeypatch, gpu, dedicated):
    """Issue #10: on a Radeon RX / Intel Arc PC the LLM was pinned to the CPU (num_gpu 0)."""
    from sharkyclips import llm

    monkeypatch.setattr(perf, "machine", lambda: perf.Machine(ram_gb=32, threads=16, cores=8, nvidia_vram_gb=None,
                                                             nvidia_name=None, apple_silicon=False, igpu=[gpu]))
    config.update(performance_preset="normal", processing_device="auto")
    assert perf.device() == "cpu"  # Whisper has no AMD / Intel GPU path: it stays on the CPU
    assert (perf.dedicated_other_gpu() == gpu) is dedicated
    assert ("num_gpu" not in llm.placement("qwen3.5:4b", 8192)) is dedicated
    config.update(processing_device="cpu")  # Settings > Performance > CPU: everything on the CPU
    assert llm.placement("qwen3.5:4b", 8192)["num_gpu"] == 0
    config.update(processing_device="auto")


def test_every_language_has_swears_and_a_relisten_prompt():
    from sharkyclips.edit import profanity
    from sharkyclips.voices import swearscan

    for code in languages.codes():
        assert profanity.DEFAULTS.get(code), code
        assert swearscan.PROMPTS.get(code), code
    samples = {"es": ["qué", "mierda", "pasó"], "pt": ["porra", "mano"], "fr": ["putain", "de", "merde"],
               "ja": ["クソ", "負けた"]}
    for code, words in samples.items():
        assert profanity.find_words([{"word": w} for w in words], code), code
