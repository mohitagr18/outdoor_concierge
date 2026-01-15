# Chat Concierge Test Questions

Test scenarios for the AI Park Ranger chat feature.

---

## 1. Broad Park Overview
| Question | Expected |
|----------|----------|
| "Tell me about Bryce Canyon" | Structured overview with conditions, alerts, trails, events |
| "Zion" | Same format |
| "Hello" | Greeting + park intro |

---

## 2. Itinerary Planning
| Question | Expected |
|----------|----------|
| "Plan a 3 day trip to Yosemite" | Day-by-day schedule |
| "Plan a weekend trip to Zion with kids" | Family-friendly itinerary |

---

## 3. Trail Queries
| Question | Expected |
|----------|----------|
| "What are the best hikes in Bryce Canyon?" | Trail list with links, grouped by difficulty |
| "Show me easy trails" | Filtered to easy only |
| "What trails are open right now?" | Alert-aware list |

---

## 4. Event Queries
| Question | Expected |
|----------|----------|
| "What events are happening at Zion?" | Events list, NO trails |
| "Any events today?" | Today's events only |

---

## 5. Activity Queries
| Question | Expected |
|----------|----------|
| "What activities can I do besides hiking?" | Tours, museums, drives |
| "What are the things to do at Yosemite?" | Non-hiking activities |

---

## 6. Photography
| Question | Expected |
|----------|----------|
| "Best photo spots for sunrise at Bryce?" | Photo spots with best times |
| "Where should I take pictures?" | Curated locations |

---

## 7. Entity Lookup
| Question | Expected |
|----------|----------|
| "Tell me about The Narrows" | Specific trail details |
| "How long is Angels Landing?" | Length/elevation info |

---

## 8. Reviews
| Question | Expected |
|----------|----------|
| "What are people saying about Angels Landing?" | Review summary |
| "Reviews for The Narrows" | Ratings + comments |

---

## 9. Safety/Conditions
| Question | Expected |
|----------|----------|
| "Is it safe to hike today?" | Safety status + alerts |
| "What's the weather like?" | Current weather |
| "Are there any closures?" | Active alerts |

---

## 10. Amenity Queries
| Question | Expected |
|----------|----------|
| "Where can I get gas near Zion?" | Gas stations list |
| "Where can I rent snowshoes?" | Gear rental locations |
| "Any restaurants nearby?" | Food options |
| "Where's the nearest pharmacy?" | Medical services |

---

## 11. Alert Cross-Reference
| Question | Expected |
|----------|----------|
| "Tell me about Bryce Canyon" | Navajo Loop should show closure warning |
| "What trails are open at Yosemite?" | Tioga Road closure mentioned |

---

## Testing Tips
- Test each park (BRCA, ZION, YOSE, GRCA) for consistency
- Check that links are clickable
- Verify images render properly
- Confirm alerts are cross-referenced with trails
