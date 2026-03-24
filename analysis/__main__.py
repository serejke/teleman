"""CLI runner for analysis skills.

Usage:
    python -m analysis --scan                          Discover exported chats
    python -m analysis --list                          List available skills
    python -m analysis <skill> <chat>                  Run one skill on a chat
    python -m analysis --all <chat>                    Run all skills on a chat

<chat> can be: chat_id, username, title substring, or path to messages.jsonl.
"""

from __future__ import annotations

import json
import sys

from analysis.loader import load_messages, resolve_chat, scan_exports
from analysis.registry import get_skills, list_skills


def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__.strip(), file=sys.stderr)
        sys.exit(0)

    if args[0] == "--scan":
        from analysis.loader import EXPORTS_DIR

        exports_dir = args[1] if len(args) > 1 else str(EXPORTS_DIR)
        result = scan_exports(exports_dir)
        print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
        return

    if args[0] == "--list":
        for s in list_skills():
            print(f"  {s.name:12s}  {s.description}")
        return

    run_all = args[0] == "--all"
    if run_all:
        args = args[1:]
        if not args:
            print("Error: provide chat identifier", file=sys.stderr)
            sys.exit(1)
        path = resolve_chat(args[0])
        messages = load_messages(path)
        skills = get_skills()
        result_dict: dict[str, dict[str, object]] = {}
        for name, mod in sorted(skills.items()):
            result_dict[name] = mod.compute(messages).model_dump()
        print(json.dumps(result_dict, ensure_ascii=False, indent=2))
        return

    skill_name = args[0]
    if len(args) < 2:
        print("Error: provide chat identifier", file=sys.stderr)
        sys.exit(1)

    skills = get_skills()
    if skill_name not in skills:
        print(f"Error: unknown skill {skill_name!r}. Available: {sorted(skills)}", file=sys.stderr)
        sys.exit(1)

    path = resolve_chat(args[1])
    messages = load_messages(path)
    result = skills[skill_name].compute(messages)
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
