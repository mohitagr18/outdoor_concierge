import re

def fuzzy_match_trail_name(target: str, trail_name: str) -> bool:
    """
    Fuzzy match trail names to handle variations like:
    - 'Bridalveil Falls trail' vs 'Bridalveil Fall Trailhead'
    - 'Cathedral Lakes Trail' vs 'Cathedral Lakes Trailhead'
    
    Requires the PRIMARY distinctive word(s) to match, not just common words like 'fall'.
    """   
    target_lower, trail_lower = target.lower(), trail_name.lower()
    
    # Remove common suffixes that shouldn't affect matching
    SUFFIXES = ['trail', 'trailhead', 'hike', 'path', 'loop']
    for suffix in SUFFIXES:
        target_lower = re.sub(rf'\b{suffix}s?\b', '', target_lower).strip()
        trail_lower = re.sub(rf'\b{suffix}s?\b', '', trail_lower).strip()
    
    # Extract significant words (>3 chars to avoid matching just 'fall')
    target_words = [w for w in target_lower.split() if len(w) > 3]
    trail_words = [w for w in trail_lower.split() if len(w) > 3]
    
    if not target_words or not trail_words:
        # Fallback to simple contains check if words are too short
        return target_lower in trail_lower or trail_lower in target_lower
    
    # Count matching words (handles plural/singular)
    def word_matches(tw, trw):
        return tw == trw or tw.rstrip('s') == trw or tw == trw.rstrip('s')
    
    matches = 0
    for tw in target_words:
        if any(word_matches(tw, trw) for trw in trail_words):
            matches += 1
    
    # Require ALL significant target words to match (strict)
    # This prevents 'Bridalveil Falls' from matching 'Vernal Falls' (only 'falls' matches)
    return matches == len(target_words)
