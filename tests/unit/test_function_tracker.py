from tools.function_tracker import FunctionTracker


def test_tracker_records_stages_and_redacts_secrets():
    tracker = FunctionTracker(hot_sample_rate=1)
    try:
        with tracker.track(
            function_id="auth.login",
            feature="authentication",
            function_name="login",
            player_id="player-1",
        ) as execution:
            execution.mark("REQUEST_RECEIVED")
            execution.mark("AUTHORIZATION")
            raise RuntimeError("Bearer secret-token")
    except RuntimeError:
        pass
    else:
        raise AssertionError("error was swallowed")
    record = tracker.records[0]
    assert record["status"] == "error"
    assert record["error_message"] == "[redacted]"
    assert "secret-token" not in str(record)
    assert record["stages"] == ["REQUEST_RECEIVED", "AUTHORIZATION"]
    assert record["player_id"] == "player-1"
    assert record["duration_ms"] >= 0


def test_hot_path_sampling_drops_tick_records():
    tracker = FunctionTracker(hot_sample_rate=0)
    with tracker.track(function_id="game.tick", feature="gameplay", function_name="tick", hot=True):
        pass
    assert tracker.records == []
