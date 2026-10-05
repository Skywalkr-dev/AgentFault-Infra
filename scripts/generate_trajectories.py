#!/usr/bin/env python3

import argparse
import os
import random
import subprocess
import sys
import time

SERVICES = ("api", "worker", "database")

CALC_TEMPLATES = (
    "What is {a} {op} {b}?",
    "Calculate {a} {op} {b}.",
    "Compute {a} {op} {b}.",
    "Find the value of {a} {op} {b}.",
)

STATUS_TEMPLATES = (
    "Check the {svc} service status.",
    "Is the {svc} healthy right now?",
    "Run a health check on {svc} and report the result.",
    "How is the {svc} service doing?",
    "Check {svc} and report whether it looks healthy.",
)

GENERAL_STATUS = (
    "What is the current system status?",
    "Check the current system status and summarize it.",
    "Is everything healthy?",
    "Check the system status and explain whether everything looks healthy.",
    "Run a health check and tell me if anything is degraded.",
    "Which services are currently unhealthy?",
)

KNOWLEDGE = (
    "What is AgentFault?",
    "How does AgentFault evaluate agent reliability?",
    "What is a trajectory?",
    "Which events can a trajectory record?",
    "What does fault injection modify?",
    "What is AgentFault-500?",
    "How are trajectories labeled as faulty?",
    "Do trajectories include handoffs and errors?",
    "What is stored in a trajectory event stream?",
    "How do you know which step caused a fault?",
    "What are fault-injected trajectories used for?",
    "Explain the difference between clean and injected trajectories.",
    "What kind of sequence does an agent execution produce?",
    "Are tool calls part of a trajectory?",
    "How does retrieval appear in a trajectory?",
    "What is a labeled faulty trajectory?",
    "How does AgentFault capture agent executions?",
    "What makes a trajectory part of AgentFault-500?",
    "Describe the contents of a trajectory record.",
    "Why record model calls in a trajectory?",
    "What happens to a trajectory during fault injection?",
    "Can a trajectory contain errors and tool results?",
    "What information does AgentFault keep about executions?",
    "How is a trajectory different from a log?",
    "What does AgentFault do with agent handoffs?",
    "What is the goal of the AgentFault framework?",
    "How are agent failures represented in AgentFault?",
    "What role do retrieval operations play in a trajectory?",
    "How does AgentFault label faulty executions?",
    "What kinds of events mark the start and end of a trajectory?",
    "Is AgentFault a framework or a dataset?",
    "What does an injected trajectory record contain?",
    "How does AgentFault support failure detection research?",
    "What sequence does an agent execution produce in AgentFault?",
    "Why are clean trajectories kept alongside injected ones?",
)


def build_prompt_pool(seed: int) -> list[str]:
    rng = random.Random(seed)
    pool = []

    operators = ("+", "-", "*")
    for _ in range(120):
        operator = rng.choice(operators)
        a = rng.randint(100, 99999)
        b = rng.randint(3, 999)
        if operator == "*":
            a = rng.randint(12, 999)
        pool.append(rng.choice(CALC_TEMPLATES).format(a=a, op=operator, b=b))

    for _ in range(25):
        dividend = rng.randint(12, 4999)
        divisor = rng.randint(3, 400)
        pool.append(
            rng.choice(CALC_TEMPLATES).format(
                a=dividend * divisor,
                op="/",
                b=divisor,
            )
        )

    for _ in range(15):
        pool.append(f"What is {rng.randint(11, 999)} squared?")

    for service in SERVICES:
        for template in STATUS_TEMPLATES:
            pool.append(template.format(svc=service))

    pool.extend(GENERAL_STATUS)
    pool.extend(KNOWLEDGE)

    unique = []
    seen = set()
    for prompt in pool:
        if prompt not in seen:
            seen.add(prompt)
            unique.append(prompt)

    return unique


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--count", type=int, default=160)
    parser.add_argument("--delay", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--provider", choices=("mock", "gemini"), default="mock")
    parser.add_argument("--ingest", action="store_true")
    args = parser.parse_args()

    pool = build_prompt_pool(args.seed)
    rng = random.Random(args.seed + 1)

    if args.count <= len(pool):
        prompts = rng.sample(pool, args.count)
    else:
        prompts = list(rng.sample(pool, len(pool)))
        prompts += [rng.choice(pool) for _ in range(args.count - len(pool))]
        print(f"Warning: only {len(pool)} unique prompts available")

    print(f"Generating {args.count} baseline trajectories ({args.provider} LLM)...")

    failures = 0
    env = os.environ.copy()
    env["AGENTFAULT_LLM"] = args.provider
    env["INGESTION_ENABLED"] = "1" if args.ingest else "0"

    for i, prompt in enumerate(prompts, 1):
        print(f"\n[{i}/{args.count}] {prompt}")

        result = subprocess.run(
            [sys.executable, "main.py", prompt],
            stdin=subprocess.DEVNULL,
            env=env,
        )

        if result.returncode != 0:
            failures += 1
            print(f"Run failed with exit code {result.returncode}")

        if args.delay:
            time.sleep(args.delay)

    print(f"\nFinished: {args.count - failures}/{args.count} runs succeeded")
    print("Trajectories saved under data/trajectories/baseline/")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
