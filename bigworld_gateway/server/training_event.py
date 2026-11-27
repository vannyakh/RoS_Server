"""Special Distinction / Brave Book + Spec Train lobby handlers.

The client's training UI (DISTINCTION, TRAINING MISSIONS, TRAINING SUPPLY) calls exposed Athlete
base methods and waits for BraveBook / SpecTrain client callbacks. Empty replies leave the UI
stuck or partially blank.
"""

from __future__ import annotations

import os
import pickle
import struct
import athlete_requests
import bwdefs

# Season 21 aligns with default GAME_DATE=2022-04-20 in config.cmd.
PASS_GENERAL = 0
PASS_SPECIAL = 1

_BRAVE_BOOK_METHODS = frozenset({
    "requestBraveBookAllAvailableRewardsBySeasonID",
    "requestBraveBookAllExtraRewardsBySeasonID",
    "requestBraveBookTaskReward",
    "requestRefreshingBraveBookTask",
    "requestUpdatingBraveBookTask",
    "requestBuyingBraveBookPass",
    "requestBraveBookAllAvailableRewardsBySeasonIDList",
    "asClickBraveBookBtn",
})

_SPEC_TRAIN_METHODS = frozenset({
    "reqSpecTrainGroupOpenInfo",
    "reqUnlockSpecTrainRewardList",
    "reqGetSpecTrainLvReward",
    "reqGetSpecTrainAllLvReward",
    "openSpecTrainRewardMain",
    "reqLogSpecTrainInfo",
    "setHasViewedSpecTrainNewProps",
})

TRAINING_METHODS = _BRAVE_BOOK_METHODS | _SPEC_TRAIN_METHODS


def current_season() -> int:
    return int(os.environ.get("GATEWAY_CURRENT_SEASON", "21"))


def free_brave_book_pass() -> bool:
    return os.environ.get("GATEWAY_FREE_BRAVE_BOOK_PASS", "on").strip().lower() in ("1", "on", "yes", "true")


def brave_book_pass_diamonds() -> int:
    try:
        return max(0, int(os.environ.get("GATEWAY_BRAVE_BOOK_PASS_DIAMONDS", "0")))
    except ValueError:
        return 0


def encode_brave_book_data(data: dict) -> bytes:
    """BRAVE_BOOK_DATA FIXED_DICT on the wire."""
    return (
        struct.pack(
            "<iii",
            int(data.get("seasonID", current_season())),
            int(data.get("level", 1)),
            int(data.get("experience", 0)),
        )
        + bwdefs.blob(pickle.dumps(data.get("passStates") or {}, protocol=2))
        + bwdefs.blob(pickle.dumps(data.get("receivedRewards") or {}, protocol=2))
    )


def encode_brave_book_data_list(entries: list[dict]) -> bytes:
    """BRAVE_BOOK_DATA_LIST.elements ARRAY<BRAVE_BOOK_DATA>."""
    return struct.pack("<I", len(entries)) + b"".join(encode_brave_book_data(e) for e in entries)


class TrainingState:
    """Per-session Brave Book + Spec Train progress (not persisted across gateway restarts)."""

    def __init__(self):
        self.season_id = current_season()
        self.level = 1
        self.experience = 0
        self.pass_states = {PASS_GENERAL: True, PASS_SPECIAL: False}
        self.received_rewards: dict = {}
        self.spec_train_exp = 0
        self.task_refresh = 0
        self.viewed_spec_props: set[int] = set()

    def brave_book_dict(self) -> dict:
        return {
            "seasonID": self.season_id,
            "level": self.level,
            "experience": self.experience,
            "passStates": dict(self.pass_states),
            "receivedRewards": dict(self.received_rewards),
        }

    def spec_train_main_payload(self) -> tuple[bytes, bytes, bytes]:
        """onSyncSpecTrainRewardMain(INT32, PYTHON, PYTHON, INT32)."""
        now = int(athlete_requests.game_now())
        # Client tables are local; server blobs carry progress / open flags only.
        general = {
            "seasonID": self.season_id,
            "level": self.level,
            "exp": self.experience,
            "endTime": now + 34 * 86400,
        }
        special = {"passOwned": bool(self.pass_states.get(PASS_SPECIAL)), "rewards": {}}
        main_id = struct.pack("<i", self.season_id)
        tail = struct.pack("<i", self.spec_train_exp)
        py = athlete_requests.py
        return main_id, py(general) + py(special), tail


def _task_stub_list() -> list:
    """Minimal mission rows so TRAINING MISSIONS tab can render."""
    return [
        {"taskIndex": 0, "progress": 0, "target": 1, "state": 0},
        {"taskIndex": 1, "progress": 0, "target": 3, "state": 0},
        {"taskIndex": 2, "progress": 0, "target": 1, "state": 0},
    ]


def lobby_sync_calls(athlete_method):
    """Push initial training state after login (alongside other lobby stubs)."""
    st = TrainingState()
    main_id, mid, tail = st.spec_train_main_payload()
    return (
        athlete_method("_OnBraveBookDataChanged", encode_brave_book_data(st.brave_book_dict()), quiet=True)
        + athlete_method("onSyncSpecTrainExp", struct.pack("<i", st.spec_train_exp), quiet=True)
        + athlete_method("onSyncSpecTrainRewardMain", main_id + mid + tail, quiet=True)
        + athlete_method(
            "_OnBraveBookTaskDataChanged",
            athlete_requests.py(_task_stub_list())
            + struct.pack("<i", st.task_refresh)
            + struct.pack("<Q", int(athlete_requests.game_now())),
            quiet=True,
        )
    )


def handle_training(
    name: str,
    rd: athlete_requests.Reader,
    *,
    state: TrainingState,
    athlete_method,
    settle,
    int_array,
    log,
) -> bytes | None:
    if name not in TRAINING_METHODS:
        return None
    py = athlete_requests.py
    now = int(athlete_requests.game_now())

    if name == "openSpecTrainRewardMain":
        main_id, mid, tail = state.spec_train_main_payload()
        log(f"openSpecTrainRewardMain season={state.season_id}")
        return athlete_method("onSyncSpecTrainRewardMain", main_id + mid + tail)

    if name == "reqSpecTrainGroupOpenInfo":
        log("reqSpecTrainGroupOpenInfo")
        return athlete_method(
            "onSyncSpecTrainGroupOpenInfo",
            struct.pack("<i", state.season_id) + py({"open": True}) + py({}),
        )

    if name == "reqUnlockSpecTrainRewardList":
        track, level = rd.i8(), rd.i32()
        log(f"reqUnlockSpecTrainRewardList track={track} level={level}")
        return athlete_method("onSyncSpecTrainRewards", struct.pack("<bii", track, level, 1))

    if name in ("reqGetSpecTrainLvReward", "reqGetSpecTrainAllLvReward"):
        if name == "reqGetSpecTrainLvReward":
            track, level = rd.i8(), rd.i32()
            log(f"reqGetSpecTrainLvReward track={track} level={level}")
            return athlete_method("onSyncSpecTrainRewards", struct.pack("<bii", track, level, 2))
        log("reqGetSpecTrainAllLvReward")
        main_id, mid, tail = state.spec_train_main_payload()
        return athlete_method("onSyncSpecTrainRewardMain", main_id + mid + tail)

    if name == "reqLogSpecTrainInfo":
        _ = rd.string()
        return b""

    if name == "setHasViewedSpecTrainNewProps":
        prop_id = rd.i32()
        state.viewed_spec_props.add(int(prop_id))
        return b""

    if name == "asClickBraveBookBtn":
        return b""

    if name == "requestUpdatingBraveBookTask":
        log("requestUpdatingBraveBookTask")
        return athlete_method(
            "_OnBraveBookTaskDataChanged",
            py(_task_stub_list()) + struct.pack("<i", state.task_refresh) + struct.pack("<Q", now),
        )

    if name in ("requestBraveBookAllAvailableRewardsBySeasonID", "requestBraveBookAllExtraRewardsBySeasonID"):
        season = rd.i32()
        log(f"{name} season={season}")
        return athlete_method(
            "_OnRequestBraveBookAllAvailableRewardsBySeasonIDFinished",
            struct.pack("<ii", 0, int(season)) + py([]),
        )

    if name == "requestBraveBookAllAvailableRewardsBySeasonIDList":
        seasons = rd.i32_array()
        log(f"requestBraveBookAllAvailableRewardsBySeasonIDList seasons={seasons}")
        return athlete_method(
            "_OnRequestBraveBookAllAvailableRewardsBySeasonIDListFinished",
            struct.pack("<i", 0) + int_array(seasons) + py([]),
        )

    if name == "requestBraveBookTaskReward":
        task_index = rd.i32()
        log(f"requestBraveBookTaskReward index={task_index}")
        return athlete_method(
            "_OnRequestBraveBookTaskRewardFinished",
            struct.pack("<ii", 0, int(task_index)),
        )

    if name == "requestRefreshingBraveBookTask":
        task_index = rd.i32()
        state.task_refresh += 1
        log(f"requestRefreshingBraveBookTask index={task_index}")
        return (
            athlete_method("_OnRequestRefreshingBraveBookTaskFinished", struct.pack("<ii", 0, int(task_index)))
            + athlete_method(
                "_OnBraveBookTaskDataChanged",
                py(_task_stub_list()) + struct.pack("<i", state.task_refresh) + struct.pack("<Q", now),
            )
        )

    if name == "requestBuyingBraveBookPass":
        pass_type, extra = rd.i32(), rd.i32()
        cost = 0 if free_brave_book_pass() else brave_book_pass_diamonds()
        if cost and not settle(cost, [], f"brave-book-pass:{pass_type}"):
            log(f"requestBuyingBraveBookPass pass={pass_type} refused (need {cost} diamonds)")
            return athlete_method(
                "_OnRequestBuyingBraveBookPassFinished",
                struct.pack("<iii", 1, int(pass_type), int(extra)),
            )
        old_owned = bool(state.pass_states.get(int(pass_type)))
        state.pass_states[int(pass_type)] = True
        log(f"requestBuyingBraveBookPass pass={pass_type} extra={extra} (cost={cost})")
        calls = b""
        if cost:
            # settle() already applied balance on the session; caller appends diamond props.
            pass
        calls += athlete_method(
            "_OnBraveBookPassStateChanged",
            struct.pack("<iB", int(pass_type), 1 if old_owned else 0),
        )
        calls += athlete_method("_OnBraveBookDataChanged", encode_brave_book_data(state.brave_book_dict()))
        calls += athlete_method(
            "_OnRequestBuyingBraveBookPassFinished",
            struct.pack("<iii", 0, int(pass_type), int(extra)),
        )
        main_id, mid, tail = state.spec_train_main_payload()
        calls += athlete_method("onSyncSpecTrainRewardMain", main_id + mid + tail)
        return calls

    return b""