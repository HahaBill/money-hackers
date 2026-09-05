from rcg.store import GraphStore, node_id


def test_node_ids_are_stable():
    a = node_id("attribution", "2026-08", "Milk unit-cost", ["n_aaa", "n_bbb"])
    b = node_id("attribution", "2026-08", "Milk unit-cost", ["n_aaa", "n_bbb"])
    assert a == b
    assert a.startswith("n_")
    assert len(a) == 8


def test_identical_writes_reuse_id():
    store = GraphStore()
    n1 = store.add(
        type="metric",
        period="2026-08",
        run_id="r_1",
        label="revenue",
        value=100.0,
        inputs=["n_src"],
    )
    n2 = store.add(
        type="metric",
        period="2026-08",
        run_id="r_2",
        label="revenue",
        value=100.0,
        inputs=["n_src"],
    )
    assert n1.id == n2.id


def test_corrected_value_gets_new_id():
    store = GraphStore()
    original = store.add(
        type="relationship_flag",
        period="2026-08",
        run_id="r1",
        label="fixed_cost_step",
        value={"leaf": "labor", "dollars": 100},
    )
    corrected = store.add(
        type="relationship_flag",
        period="2026-08",
        run_id="r1",
        label="fixed_cost_step",
        value={"leaf": "other", "dollars": 25},
    )
    assert original.id != corrected.id
    assert len(store.nodes(type="relationship_flag")) == 2


def test_raw_data_content_changes_node_id():
    store = GraphStore()
    first = store.add(type="data", period="2026-08", run_id="r_1", label="rows", value={"n": 1})
    changed = store.add(type="data", period="2026-08", run_id="r_2", label="rows", value={"n": 2})
    assert first.id != changed.id
