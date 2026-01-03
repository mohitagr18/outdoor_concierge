import json
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.adapters.nps_adapter import parse_nps_events, parse_nps_things_to_do, _parse_bool

def test_events_parsing():
    # Load sample
    with open("data_samples/nps/raw/ZION/events.json", "r") as f:
        data = json.load(f)
    
    events = parse_nps_events(data)
    print(f"Parsed {len(events)} events")
    
    for e in events:
        print(f"Event: {e.title}")
        print(f"  Dates: {len(e.dates)} specific dates")
        print(f"  Images: {len(e.images)}")
        print(f"  Is Free: {e.is_free} (Type: {type(e.is_free)})")
        
        # Verify critical fixes
        if not e.date_start:
            print("  ERROR: date_start missing")
        if not isinstance(e.is_free, bool):
             print(f"  ERROR: is_free is not bool: {type(e.is_free)}")
        if e.images:
            if not e.images[0].url.startswith("http"):
                print(f"  ERROR: Image URL is not absolute: {e.images[0].url}")

def test_things_parsing():
    with open("data_samples/nps/raw/ZION/thingstodo.json", "r") as f:
        data = json.load(f)
        
    things = parse_nps_things_to_do(data)
    print(f"\nParsed {len(things)} things to do")
    
    for t in things[:3]:
        print(f"Thing: {t.title}")
        print(f"  Pets: {t.arePetsPermitted} (Type: {type(t.arePetsPermitted)})")
        print(f"  Fee: {t.doFeesApply} (Type: {type(t.doFeesApply)})")
        print(f"  Tags: {t.tags}")

if __name__ == "__main__":
    try:
        test_events_parsing()
        test_things_parsing()
        print("\n✅ Verification Successful")
    except Exception as e:
        print(f"\n❌ Verification Failed: {e}")
        import traceback
        traceback.print_exc()
