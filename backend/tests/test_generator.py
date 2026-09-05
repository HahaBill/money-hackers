import json

from eval.generator import BACKEND_ROOT, generate


def test_generator_is_seeded_and_emits_ingestible_truth(tmp_path):
    config = BACKEND_ROOT / "data/scenarios/b_product_mix.yaml"
    first = generate(config, tmp_path / "first", seed=7)
    second = generate(config, tmp_path / "second", seed=7)
    assert first == second
    assert sum(first["attribution_truth"].values())
    manifest = json.loads((tmp_path / "first/manifest.json").read_text())
    assert manifest["rows"] > 0
    assert (tmp_path / "first/transactions.csv").exists()
