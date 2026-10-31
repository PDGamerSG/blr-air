import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv
from uagents import Agent, Context
from uagents.communication import send_sync_message
from uagents.resolver import RulesBasedResolver
from uagents_core.identity import Identity

from blr_air.models import WindowRequest, WindowResponse


async def direct_call(args, seed):
    response = await send_sync_message(
        destination=args.address,
        message=make_request(args),
        response_type=WindowResponse,
        sender=Identity.from_seed(seed, 0),
        resolver=RulesBasedResolver({args.address: args.endpoint}),
        timeout=35,
    )
    if not isinstance(response, WindowResponse):
        print(f"Agent did not return a window: {response}", file=sys.stderr)
        return 1
    print(response.json(indent=2))
    return 0 if response.status == "ok" else 1


def make_request(args):
    return WindowRequest(
        latitude=args.latitude, longitude=args.longitude, hours=args.hours, activity=args.activity
    )


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Day planner that hires BLR Air via a typed message"
    )
    parser.add_argument("--address", default=os.getenv("BLR_AIR_ADDRESS"))
    parser.add_argument("--endpoint", help="Direct /submit URL for the local signed-message demo")
    parser.add_argument("--latitude", type=float, default=12.9116)
    parser.add_argument("--longitude", type=float, default=77.6389)
    parser.add_argument("--hours", type=int, choices=(1, 2), default=2)
    parser.add_argument(
        "--activity", choices=("run", "cycle", "walk", "commute", "kids"), default="walk"
    )
    args = parser.parse_args()
    seed = os.getenv("CALLER_SEED")
    if not seed or not args.address:
        parser.error("Run python -m blr_air init and set BLR_AIR_ADDRESS or pass --address.")
    if args.endpoint:
        sys.exit(asyncio.run(direct_call(args, seed)))
    planner = Agent(
        name="day-planner-demo",
        seed=seed,
        port=8002,
        mailbox=True,
        publish_agent_details=False,
        store_message_history=False,
    )
    state = {"sent": False}

    @planner.on_interval(period=30)
    async def hire(ctx: Context):
        if not state["sent"]:
            ctx.logger.info("Hiring BLR Air at %s", args.address)
            status = await ctx.send(args.address, make_request(args))
            # Do not flood the agent while waiting for its reply.
            state["sent"] = True
            ctx.logger.info("Request delivery: %s. Restart caller to send another request.", status)

    @planner.on_message(model=WindowResponse)
    async def hired(ctx: Context, sender: str, msg: WindowResponse):
        if sender == args.address:
            ctx.logger.info("BLR Air reply:\n%s", msg.summary)

    planner.run()
