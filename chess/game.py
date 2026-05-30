#!/usr/bin/env python3
"""
Community chess for a GitHub profile README.
Triggered by a GitHub Action when someone opens an issue titled e.g. `chess|move|e2e4|7`.
Validates the move with python-chess, redraws chess/board.svg, and rewrites the
section of README.md between the <!-- chess-start --> / <!-- chess-end --> markers.

Inspired by github.com/timburgan — reimplemented with python-chess for full rules
(castling, en passant, promotion, check / checkmate / stalemate).
"""
import os
import json
from urllib.parse import quote

import chess
import chess.svg

README_PATH = os.environ.get("README_PATH", "README.md")
STATE_PATH  = os.environ.get("STATE_PATH", "chess/state.json")
BOARD_PATH  = os.environ.get("BOARD_PATH", "chess/board.svg")
REPO   = os.environ.get("REPO") or os.environ.get("GITHUB_REPOSITORY") or "USER/REPO"
BRANCH = os.environ.get("BRANCH", "main")
TITLE  = (os.environ.get("ISSUE_TITLE") or "").strip()
AUTHOR = (os.environ.get("ISSUE_AUTHOR") or "anonymous").strip()

START = "<!-- chess-start -->"
END   = "<!-- chess-end -->"

BODY = ("Just press the green **Create** / **Submit new issue** button below — "
        "you do not need to type or change anything. The board on the profile "
        "updates automatically in about 30 seconds. Thanks for playing! :)")

COLORS = {
    "square light": "#e7eaef",
    "square dark": "#9aa4b0",
    "square light lastmove": "#f2d479",
    "square dark lastmove": "#d8b24a",
    "margin": "#0d1117",
    "coord": "#768390",
}


def new_state():
    return {
        "fen": chess.STARTING_FEN,
        "moveCount": 0,
        "lastUci": None,
        "recent": [],
        "leaderboard": {},
        "message": "Fresh game — White to move. Anyone can play.",
    }


def load_state():
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except Exception:
        return new_state()


def save_state(state):
    d = os.path.dirname(STATE_PATH)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def issue_url(title):
    return (f"https://github.com/{REPO}/issues/new"
            f"?title={quote(title, safe='')}&body={quote(BODY, safe='')}")


def write_board_svg(board, state):
    last = None
    if state.get("lastUci"):
        try:
            last = chess.Move.from_uci(state["lastUci"])
        except Exception:
            last = None
    check_sq = board.king(board.turn) if board.is_check() else None
    svg = chess.svg.board(
        board, size=380, lastmove=last, check=check_sq,
        coordinates=True, colors=COLORS,
    )
    d = os.path.dirname(BOARD_PATH)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(BOARD_PATH, "w") as f:
        f.write(svg)


def render_section(board, state):
    token = state["moveCount"]
    turn_white = board.turn == chess.WHITE
    side = "WHITE" if turn_white else "BLACK"
    over = board.is_game_over()

    write_board_svg(board, state)

    out = [START, "", "### `$ ./chess --play`", ""]

    if over:
        if board.is_checkmate():
            winner = "Black" if turn_white else "White"
            status = f"**Checkmate — {winner} wins.** `{board.result()}`"
        elif board.is_stalemate():
            status = "**Stalemate — it's a draw.**"
        elif board.is_insufficient_material():
            status = "**Draw — insufficient material.**"
        else:
            status = f"**Game over — `{board.result()}`.**"
        out.append(f"> {status}")
    else:
        out.append(
            f"> **It's your move — anyone can play.** Move a **{side.lower()}** "
            f"piece: click a destination link below, press **Create** on the issue "
            f"that opens, and the board redraws in ~30s."
        )
    out.append("")
    out.append(
        f'<img src="https://raw.githubusercontent.com/{REPO}/{BRANCH}/{BOARD_PATH}?v={token}" '
        f'width="380" alt="chess board — {side.lower()} to move" />'
    )
    out.append("")

    if not over:
        by_from = {}
        for mv in board.legal_moves:
            if mv.promotion and mv.promotion != chess.QUEEN:
                continue  # offer queen-promotion only, to keep the list clean
            frm = chess.square_name(mv.from_square).upper()
            by_from.setdefault(frm, []).append(mv)

        out.append(f"**{side} to move** &nbsp;·&nbsp; pick a piece, then a destination:")
        out.append("")
        out.append("| piece | move it to |")
        out.append("| :---: | :--- |")
        for frm in sorted(by_from):
            tos = []
            for mv in sorted(by_from[frm], key=lambda m: m.uci()):
                to = chess.square_name(mv.to_square).upper()
                tos.append(f"[{to}]({issue_url('chess|move|' + mv.uci() + '|' + str(token))})")
            out.append(f"| **{frm}** | {' &nbsp; '.join(tos)} |")
        out.append("")
    else:
        out.append(f"[**▸ start a new game**]({issue_url('chess|new|' + str(token))})")
        out.append("")

    if state.get("recent"):
        out.append("<details><summary><sub>recent moves &amp; players</sub></summary>")
        out.append("")
        out.append("| move | by |")
        out.append("| :--- | :--- |")
        for r in list(reversed(state["recent"]))[:8]:
            out.append(f"| `{r['move']}` | [@{r['who']}](https://github.com/{r['who']}) |")
        out.append("")
        out.append("</details>")
        out.append("")

    out.append(
        "<sub>♟ real game · a GitHub Action validates each move with "
        "[python-chess](https://python-chess.readthedocs.io) and redraws the board · "
        "idea from [@timburgan](https://github.com/timburgan)</sub>"
    )
    out.append("")
    out.append(END)
    return "\n".join(out)


def update_readme(section):
    with open(README_PATH, encoding="utf-8") as f:
        txt = f.read()
    if START in txt and END in txt:
        pre = txt.split(START, 1)[0]
        post = txt.split(END, 1)[1]
        txt = pre + section + post
    else:
        txt = txt.rstrip() + "\n\n" + section + "\n"
    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(txt)


def main():
    state = load_state()
    board = chess.Board(state["fen"])
    parts = TITLE.split("|") if TITLE else []

    if len(parts) >= 2 and parts[0] == "chess":
        action = parts[1]

        if action == "new":
            if board.is_game_over():
                state = new_state()
                board = chess.Board(state["fen"])
                state["message"] = f"@{AUTHOR} started a fresh game."
            else:
                state["message"] = "A game is already in progress — please finish it first."

        elif action == "move" and len(parts) >= 4:
            uci, token = parts[2], parts[3]
            if str(state["moveCount"]) != str(token):
                state["message"] = ("That link was stale — someone moved first. "
                                    "The board has refreshed; try again.")
            else:
                try:
                    mv = chess.Move.from_uci(uci)
                except Exception:
                    mv = None
                if mv and mv in board.legal_moves:
                    frm = chess.square_name(mv.from_square).upper()
                    to = chess.square_name(mv.to_square).upper()
                    board.push(mv)
                    state["fen"] = board.fen()
                    state["lastUci"] = uci
                    state["moveCount"] += 1
                    state["recent"] = (state.get("recent", []) + [{"move": f"{frm}-{to}", "who": AUTHOR}])[-16:]
                    lb = state.get("leaderboard", {})
                    lb[AUTHOR] = lb.get(AUTHOR, 0) + 1
                    state["leaderboard"] = lb
                    state["message"] = f"@{AUTHOR} played {frm}-{to}."
                else:
                    state["message"] = "That move was illegal or stale — board refreshed."

    state["fen"] = board.fen()
    section = render_section(board, state)
    update_readme(section)
    save_state(state)
    print(state.get("message", ""))


if __name__ == "__main__":
    main()
