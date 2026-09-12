import argparse
import json
import time
from datetime import datetime, timedelta, timezone

import boto3

NAMESPACE = "CkAgent"
METRICS = ["TtftMs", "LatencyMs", "TokensIn", "TokensOut", "RetrievalTop1",
           "KbMiss", "VerificationFailures", "TurnErrors", "BedrockThrottles"]
SECRETS = ["6789", "5678", "4321", "1990-01-05", "1985-07-22", "1978-11-30",
           "alice@ck1.com", "bob@ck2.com", "carol@ck123.com", "123-45-6789"]
META = {"ts", "event", "trace_id", "session_id"}


def rule(title=""):
    print("─" * 74)
    if title:
        print(f"  {title}")
        print("─" * 74)


def fetch_logs(logs, group, since, session):
    pattern = f'{{ $.session_id = "{session}" }}' if session else "{ $.event = * }"
    pages = logs.get_paginator("filter_log_events").paginate(
        logGroupName=group, startTime=since, filterPattern=pattern)
    out = []
    for page in pages:
        for event in page["events"]:
            try:
                out.append(json.loads(event["message"]))
            except json.JSONDecodeError:
                pass
    return out


def show_logs(records):
    if not records:
        print("  (no structured log lines — talk to the app first)")
        return
    for r in records:
        extra = {k: v for k, v in r.items() if k not in META}
        print(f"  {r['trace_id']:<12}  {r['session_id']:<24}  {r['event']:<14}  "
              f"{json.dumps(extra, ensure_ascii=False)[:88]}")
    turns = {(r["trace_id"], r["session_id"]) for r in records}
    sessions = {s for _, s in turns}
    print()
    print(f"  {len(records)} lines · {len(turns)} turns · {len(sessions)} conversation(s)")
    if len(sessions) == 1 and len(turns) > 1:
        print("  one session_id across many trace_ids — the unit of debugging is the conversation")


def show_metrics(cw, minutes):
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=minutes)
    print(f"  {'metric':<22}{'n':>5}{'avg':>12}{'max':>12}{'sum':>12}")
    for name in METRICS:
        resp = cw.get_metric_statistics(
            Namespace=NAMESPACE, MetricName=name, StartTime=start, EndTime=end,
            Period=86400, Statistics=["Average", "Maximum", "Sum", "SampleCount"])
        points = resp["Datapoints"]
        if not points:
            print(f"  {name:<22}{'-':>5}{'-':>12}{'-':>12}{'-':>12}")
            continue
        p = max(points, key=lambda x: x["Timestamp"])
        print(f"  {name:<22}{int(p['SampleCount']):>5}{p['Average']:>12.2f}"
              f"{p['Maximum']:>12.2f}{p['Sum']:>12.2f}")


def show_alarms(cw, prefix):
    alarms = cw.describe_alarms(AlarmNamePrefix=prefix)["MetricAlarms"]
    if not alarms:
        print("  (no alarms found)")
        return
    for a in sorted(alarms, key=lambda x: x["AlarmName"]):
        stat = a.get("Statistic") or a.get("ExtendedStatistic")
        print(f"  {a['StateValue']:<18}{a['AlarmName']:<34}"
              f"{stat} {a['MetricName']} {a['ComparisonOperator']} {a['Threshold']:g}")
        print(f"  {'':<18}{a['StateReason'][:100]}")


def strings_in(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from strings_in(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from strings_in(v)


def show_pii(records):
    print("  Checked against the VALUES of log fields, never the raw line: a 13-digit")
    print("  epoch timestamp ending in 6789 is not a leaked SSN.")
    print()
    haystack = []
    for r in records:
        haystack.extend(strings_in({k: v for k, v in r.items() if k not in {"ts"}}))
    blob = "\n".join(haystack)
    worst = 0
    for secret in SECRETS:
        leaked = secret in blob
        worst += leaked
        print(f"  {'LEAKED  ' if leaked else 'clean   '}{secret}")
    print()
    print(f"  {len(haystack)} string values scanned · "
          f"{'ALL CLEAN' if not worst else str(worst) + ' LEAK(S) — FIX BEFORE SUBMITTING'}")


def main():
    ap = argparse.ArgumentParser(description="Inspect what the deployed agent reports.")
    ap.add_argument("--minutes", type=int, default=30)
    ap.add_argument("--session", default="")
    ap.add_argument("--name", default="ck-agent-dev")
    ap.add_argument("--region", default="us-east-1")
    args = ap.parse_args()

    group = f"/aws/lambda/{args.name}"
    since = int((time.time() - args.minutes * 60) * 1000)
    logs = boto3.client("logs", region_name=args.region)
    cw = boto3.client("cloudwatch", region_name=args.region)

    records = fetch_logs(logs, group, since, args.session)

    rule(f"STRUCTURED LOGS   {group}   last {args.minutes}m"
         + (f"   session={args.session}" if args.session else ""))
    show_logs(records)

    print()
    rule(f"EMF METRICS   namespace {NAMESPACE}   last {args.minutes}m")
    show_metrics(cw, args.minutes)

    print()
    rule("ALARMS")
    show_alarms(cw, args.name)

    print()
    rule("PII CHECK")
    show_pii(records)


if __name__ == "__main__":
    main()
