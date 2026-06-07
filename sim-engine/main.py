import json
from datetime import datetime
from agents.timeline import generate_timelines
from agents.chaos import apply_chaos
from agents.synthesis import batch_synthesis

TIMELINE_KEYS = ["Timeline A", "Timeline B", "Timeline C"]

def run_simulation(decision: str, context: dict, save_output: bool = True):
    print("1. Generating timelines...")
    timelines_raw = generate_timelines(decision, context)

    print("2. Injecting chaos...")
    chaos_events = {}
    for tl in TIMELINE_KEYS:
        year1 = timelines_raw.get(tl, {}).get("_causal", {}).get("Year1", {})
        chaos_events[tl] = apply_chaos(year1, personality_key=tl[-1]).get("events", [])

    timelines_raw = generate_timelines(decision, context, chaos_events=chaos_events)

    print("3. Extracting timelines...")
    timelines = {
        name: tl for name, tl in timelines_raw.items() if not name.startswith("_")
    }

    print("4. Running batched synthesis (regret + comparison + letters)...")
    synthesis = batch_synthesis(timelines, decision, context)

    result = {
        "timestamp": datetime.now().isoformat(),
        "decision": decision,
        "context": context,
        "timelines": timelines,
        "regrets": synthesis.get("regrets", {}),
        "comparison": synthesis.get("comparison", {}),
        "letters": synthesis.get("letters", {}),
    }

    if save_output:
        import os
        os.makedirs("outputs", exist_ok=True)
        filename = f"outputs/sim_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nSaved to {filename}")

    return result

def display_results(result):
    print("\n" + "="*70)
    print("SIMULATION RESULTS")
    print("="*70)
    
    for timeline_name, timeline_data in result["timelines"].items():
        print(f"\n{'─'*70}")
        print(f"{timeline_name}")
        print(f"{'─'*70}")
        for year in ("Year1", "Year3", "Year5", "Year10"):
            narrative = timeline_data.get(year, "")
            causal = timeline_data.get("_causal", {}).get(year, {})
            income_score = causal.get("income", "?")
            health_score = causal.get("health", "?")
            rel_score = causal.get("relationships", "?")
            happy_score = causal.get("happiness", "?")
            stress_score = causal.get("stress", "?")
            if narrative:
                print(f"\n{year}  (inc={income_score} h={health_score} r={rel_score} ha={happy_score} s={stress_score})")
                print(f"  {narrative}")
        
        regret = result["regrets"].get(timeline_name, {})
        print(f"\n  Regret in this path:")
        print(f"    Lost opportunity: {regret.get('lost_opportunity', '')}")
        print(f"    Missed identity: {regret.get('missed_identity', '')}")
        print(f"    Emotional cost: {regret.get('emotional_cost', '')}")
        
        letter = result["letters"].get(timeline_name, "")
        print(f"\n  Letter from your future self:")
        print(f"\n{letter}")
    
    print(f"\n{'─'*70}")
    print("COMPARISON ACROSS ALL TIMELINES")
    print(f"{'─'*70}")
    comp = result.get("comparison", {})
    if comp.get("common_patterns"):
        print(f"\n  Common patterns: {comp['common_patterns']}")
    if comp.get("key_differences"):
        print(f"\n  Key differences: {comp['key_differences']}")
    if comp.get("hinge_point"):
        print(f"\n  The real hinge point: {comp['hinge_point']}")
    
    print("\n" + "="*70)
    print("Remember: These are simulations, not predictions. The future bends.")
    print("="*70)

if __name__ == "__main__":
    context = {
        "age": 20,
        "location": "Bangalore",
        "risk_tolerance": "high",
        "financial_condition": "lower middle class",
        "interests": ["entrepreneurship", "tech"]
    }
    decision = "Should I drop out of college to start a business?"
    
    output = run_simulation(decision, context)
    display_results(output)

