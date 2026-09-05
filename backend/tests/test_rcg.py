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
        value=999.0,
        inputs=["n_src"],
    )
    assert n1.id == n2.id


def test_raw_data_content_changes_node_id():
    store = GraphStore()
    first = store.add(type="data", period="2026-08", run_id="r_1", label="rows", value={"n": 1})
    changed = store.add(type="data", period="2026-08", run_id="r_2", label="rows", value={"n": 2})
    assert first.id != changed.id
