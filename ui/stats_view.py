"""Turns the recorded search statistics into text for the HUD, the AI panel and the results screen.

Read-only: every number comes from `Metrics` (real A*, Minimax and MCTS runs) or from the GameState.
Nothing is estimated, rounded up, or randomised. When an algorithm has not run yet the text says so
instead of showing a made-up number."""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple

from game.state import GameState, Winner

ASTAR_ROLES = (("demogorgon", "Demogorgon A*"), ("eleven", "Eleven A*"), ("radar", "Radar A*"))


# ---------------------------------------------------------------- one-line stats (also used by tests)
def stats_lines(tm) -> List[str]:
    """Stat lines straight from the recorded search statistics (nothing is estimated)."""
    out = []
    for role, label in ASTAR_ROLES:
        st = tm.metrics.astar.get(role)
        if not st:
            continue
        reused = f", {st.cache_hits} reused" if st.cache_hits else ""
        out.append(f"{label}: {st.calls} searches, {st.nodes_explored} nodes, avg {st.avg_time_ms:.2f} ms{reused}")
    mm = tm.metrics.minimax
    if mm.calls:
        last = mm.last
        mode = "AB" if last.alpha_beta else "plain"
        out.append(f"Vecna Minimax {mode} d{last.depth}: {mm.calls} searches, "
                   f"{mm.nodes_evaluated} evaluated, {mm.branches_pruned} pruned")
        out.append(f"  last: {last.action.value} score {last.score:.1f}, {last.nodes_evaluated} evaluated, "
                   f"{last.branches_pruned} pruned, {last.time_ms:.2f} ms")
    for role, label in (("eleven", "Eleven MCTS"), ("mind_flayer", "Mind Flayer MCTS")):
        mc = tm.metrics.mcts.get(role)
        if mc and mc.calls:
            last = mc.last
            name = last.goal.label if role == "eleven" else last.label
            out.append(f"{label}: {mc.calls} searches, {mc.simulations} simulations, avg {mc.avg_time_ms:.1f} ms")
            out.append(f"  last: {name} ({last.visits}/{last.simulations} visits, value {last.value:+.2f}), "
                       f"{last.nodes_created} nodes, depth {last.max_depth}")
    return out


# ---------------------------------------------------------------- AI panel sections
@dataclass
class Section:
    title: str
    lines: List[str]
    has_data: bool          # False -> the algorithm has not run yet (panel shows it dimmed)


def _astar_section(tm) -> Section:
    lines = []
    for role, label in ASTAR_ROLES:
        st = tm.metrics.astar.get(role)
        if not st or not (st.calls or st.cache_hits):
            continue
        reused = f" +{st.cache_hits} reused" if st.cache_hits else ""
        lines.append(f"{label.replace(' A*', '')}: {st.calls} searches, {st.nodes_explored} nodes")
        lines.append(f"   avg {st.avg_time_ms:.2f} ms{reused}")
    if not lines:
        return Section("A* pathfinding", ["no search yet"], False)
    return Section("A* pathfinding", lines, True)


def _vecna_section(tm) -> Section:
    mm = tm.metrics.minimax
    if not mm.calls:
        return Section("Vecna: Minimax", ["no search yet"], False)
    last = mm.last
    mode = "Alpha-Beta" if last.alpha_beta else "plain"
    lines = [f"{mode}, depth {last.depth}: {mm.calls} searches",
             f"total {mm.nodes_evaluated} evaluated, {mm.branches_pruned} pruned",
             f"last: {last.action.value}  score {last.score:+.1f}",
             f"   {last.nodes_evaluated} evaluated, {last.branches_pruned} pruned, {last.time_ms:.2f} ms"]
    if last.root_values:
        sign = "<=" if last.alpha_beta else "="
        parts = []
        for name, value in sorted(last.root_values.items(), key=lambda kv: -kv[1])[:4]:
            parts.append(f"{name} {'=' if name == last.action.value else sign}{value:+.0f}")
        lines.append("   options: " + "  ".join(parts))
    return Section("Vecna: Minimax", lines, True)


def _mcts_section(tm, role: str, title: str) -> Section:
    mc = tm.metrics.mcts.get(role)
    if not mc or not mc.calls:
        return Section(title, ["no search yet"], False)
    last = mc.last
    name = last.goal.label if role == "eleven" else last.label
    lines = [f"{mc.calls} searches, {mc.simulations} simulations, avg {mc.avg_time_ms:.1f} ms",
             f"last: {name}  ({last.visits}/{last.simulations} visits)",
             f"   value {last.value:+.2f}, {last.nodes_created} nodes, depth {last.max_depth}"]
    if last.root:
        top = sorted(last.root, key=lambda r: -r[1])[:3]
        lines.append("   top: " + "  ".join(f"{label} {visits}" for label, visits, _ in top))
    return Section(title, lines, True)


def stats_sections(tm) -> List[Section]:
    """The four AI-panel cards: A*, Vecna Minimax, Eleven MCTS, Mind Flayer MCTS."""
    return [_astar_section(tm), _vecna_section(tm),
            _mcts_section(tm, "eleven", "Eleven: MCTS goal"),
            _mcts_section(tm, "mind_flayer", "Mind Flayer: MCTS")]


# ---------------------------------------------------------------- results screen
@dataclass
class Results:
    headline: str                       # "ELEVEN ESCAPED!" / "ELEVEN FELL" / "TURN LIMIT REACHED"
    eleven_won: bool
    rows: List[Tuple[str, str]]         # (label, value) for the summary table
    ai_rows: List[Tuple[str, str]]      # search statistics


def turns_played(state: GameState) -> int:
    """The final turn is not advanced when the game ends, so it still counts as played."""
    return state.turn + (1 if state.game_over else 0)


def demogorgons_defeated(state: GameState) -> int:
    """Normal Demogorgons killed (temporary Mind Flayer creatures are not counted)."""
    return sum(1 for d in state.demogorgons if not d.alive and not d.temporary)


def build_results(state: GameState, tm) -> Results:
    """Summary of the finished (or current) game, taken only from the state and the Metrics."""
    if state.winner == Winner.ELEVEN:
        headline, won = "ELEVEN ESCAPED!", True
    elif state.eleven_hp <= 0:
        headline, won = "ELEVEN FELL", False
    elif state.game_over:
        headline, won = "TURN LIMIT REACHED", False
    else:
        headline, won = "GAME IN PROGRESS", False
    total_normal = sum(1 for d in state.demogorgons if not d.temporary)
    mf = "defeated" if state.mind_flayer.defeated else ("awake" if state.mind_flayer.active else "never woke")
    rows = [
        ("Winner", "Eleven" if won else ("Enemies" if state.game_over else "-")),
        ("Turns played", f"{turns_played(state)} / {state.max_turns}"),
        ("Friends rescued", f"{len(state.rescued)} / 4"),
        ("Demogorgons defeated", f"{demogorgons_defeated(state)} / {total_normal}"),
        ("Mind Flayer", mf),
        ("Final HP", str(state.eleven_hp)),
        ("Final power", str(state.eleven_power)),
    ]
    m = tm.metrics
    ai_rows: List[Tuple[str, str]] = []
    for role, label in (("eleven", "Eleven MCTS"), ("mind_flayer", "Mind Flayer MCTS")):
        mc = m.mcts.get(role)
        if mc and mc.calls:
            ai_rows.append((label, f"{mc.simulations} simulations in {mc.calls} searches, avg {mc.avg_time_ms:.1f} ms"))
        else:
            ai_rows.append((label, "did not run"))
    if m.minimax.calls:
        mode = "Alpha-Beta" if m.minimax.last.alpha_beta else "plain"
        ai_rows.append(("Vecna Minimax", f"{m.minimax.nodes_evaluated} nodes evaluated, "
                                          f"{m.minimax.branches_pruned} pruned ({mode}, depth {m.minimax.last.depth})"))
    else:
        ai_rows.append(("Vecna Minimax", "did not run"))
    astar_total = sum(st.nodes_explored for st in m.astar.values())
    astar_calls = sum(st.calls for st in m.astar.values())
    ai_rows.append(("A* total", f"{astar_total} nodes explored in {astar_calls} searches"))
    for role, label in ASTAR_ROLES:
        st = m.astar.get(role)
        if st and st.calls:
            ai_rows.append((f"  {label}", f"{st.calls} searches, {st.nodes_explored} nodes"))
    return Results(headline, won, rows, ai_rows)
