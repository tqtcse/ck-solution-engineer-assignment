from app.agent import run_turn
from app.session import get


def main():
    state = get("cli")
    print("Type your question (Press Ctrl-C to exit)\n")
    while True:
        try:
            text = input("you > ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if not text:
            continue
        print("bot > ", end="", flush=True)
        for kind, payload in run_turn(state, text):
            if kind == "token":
                print(payload, end="", flush=True)
            elif kind == "tool_start":
                print(f"\n  [calling tool: {payload}]\n  ", end="", flush=True)
        print("\n")


if __name__ == "__main__":
    main()