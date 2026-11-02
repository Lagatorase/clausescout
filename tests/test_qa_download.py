"""Where the QA model is loaded from: my own models/ folder first, then the Hub, all mocked.

Nothing here downloads anything: the Hugging Face calls are replaced with fakes that record what
they were asked for.
"""

import json
from pathlib import Path

import huggingface_hub
import pytest
import transformers
import yaml

from clausescout.models.qa import QAExtractor, resolve_model

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = {"Governing Law": "Which law governs?", "Parties": "Who are the parties?"}


class FakeTokenizer:
    pad_token_id = 0

    def __call__(self, text, add_special_tokens=True, **kw):
        return {"input_ids": list(range(len(text.split())))}


class FakeModel:
    def to(self, device):
        return self

    def eval(self):
        return self


@pytest.fixture
def calls(monkeypatch, tmp_path):
    # Records every load, so each test can check where the model came from.
    seen = {"tokenizer": [], "model": [], "download": []}

    def tokenizer(source, revision=None, **kw):
        seen["tokenizer"].append((str(source), revision))
        return FakeTokenizer()

    def model(source, revision=None, **kw):
        seen["model"].append((str(source), revision))
        return FakeModel()

    def download(repo, filename, revision=None, **kw):
        seen["download"].append((repo, filename, revision))
        path = tmp_path / "cache" / filename
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(QUESTIONS), encoding="utf-8")
        return str(path)

    monkeypatch.setattr(transformers.AutoTokenizer, "from_pretrained", tokenizer)
    monkeypatch.setattr(transformers.AutoModelForQuestionAnswering, "from_pretrained", model)
    monkeypatch.setattr(huggingface_hub, "hf_hub_download", download)
    return seen


def test_local_model_wins_and_nothing_is_downloaded(calls, tmp_path):
    local = tmp_path / "qa"
    local.mkdir()
    (local / "config.json").write_text("{}", encoding="utf-8")
    (local / "questions.json").write_text(json.dumps(QUESTIONS), encoding="utf-8")

    qa = QAExtractor(local, device="cpu", hub_repo="someone/model", hub_revision="abc")
    assert calls["model"] == [(str(local), None)]
    assert calls["tokenizer"] == [(str(local), None)]
    assert calls["download"] == []
    assert qa.windows.categories == ["Parties", "Governing Law"]


def test_missing_local_model_comes_from_the_pinned_hub_commit(calls, tmp_path):
    qa = QAExtractor(tmp_path / "not-trained", device="cpu", hub_repo="someone/model",
                     hub_revision="abc123")
    assert calls["model"] == [("someone/model", "abc123")]
    assert calls["tokenizer"] == [("someone/model", "abc123")]
    assert calls["download"] == [("someone/model", "questions.json", "abc123")]
    assert set(qa.windows.categories) == set(QUESTIONS)


def test_no_local_model_and_no_repo_is_a_clear_error(calls, tmp_path):
    with pytest.raises(FileNotFoundError, match="hub_repo"):
        resolve_model(tmp_path / "not-trained")
    assert calls["download"] == []


def test_app_configs_pin_the_hub_model_to_one_commit():
    # A branch name like "main" could change under the app; a full commit hash can't.
    qa = yaml.safe_load((ROOT / "config" / "app-qa.yaml").read_text(encoding="utf-8"))["params"]
    hybrid = yaml.safe_load(
        (ROOT / "config" / "app-hybrid.yaml").read_text(encoding="utf-8"))["params"]
    assert qa["hub_repo"] == hybrid["qa_hub_repo"] == "Lagatorase/clausescout-deberta-v3-small-cuad"
    assert qa["hub_revision"] == hybrid["qa_hub_revision"]
    assert len(qa["hub_revision"]) == 40 and int(qa["hub_revision"], 16) >= 0
