import json
from datetime import datetime
from agents.timeline import generate_timelines
from agents.chaos import apply_chaos
from agents.regret import analyze_regret
from agents.comparator import compare_timelines
from agents.letter import write_future_letter

def run_simulation(decision: str, context: dict, save_output: bool = True):
    print("1. Generating timelines...")
    timelines = generate_timelines(decision, context)
    
    print("2. Injecting chaos...")
    chaotic_timelines = {}
    for name, timeline in timelines.items():
        chaotic_timelines[name] = apply_chaos(timeline)
    
    print("3. Analyzing regret...")
    regrets = {}
    for name, timeline in chaotic_timelines.items():
        regrets[name] = analyze_regret(timeline)
    
    print("4. Comparing across timelines...")
    # Combine timelines and regrets for comparator
    combined = {
        name: {
            "timeline": chaotic_timelines[name],
            "regret": regrets[name]
        }
        for name in chaotic_timelines.keys()
    }
    comparison = compare_timelines(combined)
    
    print("5. Writing future self letters...")
    letters = {}
    for name in chaotic_timelines.keys():
        letters[name] = write_future_letter(chaotic_timelines[name], regrets[name])
    
    result = {
        "timestamp": datetime.now().isoformat(),
        "decision": decision,
        "context": context,
        "timelines": chaotic_timelines,
        "regrets": regrets,
        "comparison": comparison,
        "letters": letters
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
    print("🔮 SIMULATION RESULTS")
    print("="*70)
    
    for timeline_name, timeline_data in result["timelines"].items():
        print(f"\n{'─'*70}")
        print(f"📌 {timeline_name}")
        print(f"{'─'*70}")
        for year, desc in timeline_data.items():
            print(f"{year}: {desc}")
        
        regret = result["regrets"][timeline_name]
        print(f"\n💔 Regret in this path:")
        print(f"   Lost opportunity: {regret['lost_opportunity']}")
        print(f"   Missed identity: {regret['missed_identity']}")
        print(f"   Emotional cost: {regret['emotional_cost']}")
        
        print(f"\n📫 Letter from your future self in {timeline_name}:")
        print(f"\n{result['letters'][timeline_name]}")
    
    print(f"\n{'─'*70}")
    print("🔍 COMPARISON ACROSS ALL TIMELINES")
    print(f"{'─'*70}")
    comp = result["comparison"]
    print(f"Common patterns: {comp['common_patterns']}")
    print(f"Key differences: {comp['key_differences']}")
    print(f"\n⚡ The real hinge point: {comp['hinge_point']}")
    
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

