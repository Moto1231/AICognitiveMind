from pathlib import Path

from aicognitive_mind.body.genesis_avatar import build_genesis_vrm


OUTPUT = Path("src/aicognitive_mind/static/genesis.vrm")


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(build_genesis_vrm())
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
