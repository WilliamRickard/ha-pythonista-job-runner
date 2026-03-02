# Version: 0.1.0

"""GhKit Pythonista entrypoint (scaffold)."""

from __future__ import annotations

from ghkit.version import __version__


def main() -> None:
    """Main entry point."""
    print(f"GhKit scaffold version: {__version__}")
    print("1) Probe (placeholder)")
    print("2) Exit")
    choice = input("Select: ").strip()
    if choice == "1":
        print("Probe is not implemented yet.")
    print("Done.")


if __name__ == "__main__":
    main()
