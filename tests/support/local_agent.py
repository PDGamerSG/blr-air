"""Unpublished, ephemeral BLR Air process for scripts/check_live.py only."""

import argparse
import secrets
from pathlib import Path

from uagents.resolver import RulesBasedResolver

from blr_air.agent_runtime import create_agent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--receiver-address", required=True)
    parser.add_argument("--receiver-endpoint", required=True)
    parser.add_argument("--data-dir", required=True, type=Path)
    args = parser.parse_args()
    create_agent(
        secrets.token_urlsafe(48),
        port=args.port,
        local=True,
        data_dir=args.data_dir,
        resolver=RulesBasedResolver({args.receiver_address: args.receiver_endpoint}),
    ).run()


if __name__ == "__main__":
    main()
