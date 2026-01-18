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

## 12. Context Inheritance (Follow-up Questions)
| Step | Question | Expected |
|------|----------|----------|
| 1 | "Reviews for The Narrows" | Response about Zion's The Narrows |
| 2 | "What else can I do there?" | Should stay on Zion, not switch to Yosemite |
| 3 | "Tell me about Half Dome" | Should now switch to Yosemite |
| 4 | "What's the weather?" | Should use Yosemite context |

---

## 13. Multi-Part Queries (Trail + Amenities)
| Question | Expected |
|----------|----------|
| "What equipment do I need for The Narrows and where can I rent it from nearby?" | Trail info + nearby rental shops |
| "Tell me about Angels Landing and where can I buy gear?" | Trail details + gear stores |
| "What's the best hike and where can I eat after?" | Trail recommendation + restaurant suggestions |

---

## 14. Unsupported/Unloaded Parks
| Question | Expected |
|----------|----------|
| "Tell me about Death Valley" | Guides to Park Explorer to fetch data |
| "Plan a trip to Glacier" | Message about loading data first |
| "Yellowstone trails" | Prompts to fetch park data |

---

## 15. No Park Specified
| Question | Expected |
|----------|----------|
| "Show me some trails" (fresh session) | Asks user to specify a park |
| "What's the weather?" (no context) | Lists supported parks, asks for choice |

---

## Testing Tips
- Test each park (BRCA, ZION, YOSE, GRCA) for consistency
- Check that links are clickable
- Verify images render properly
- Confirm alerts are cross-referenced with trails
- Test context inheritance across multiple messages
- Verify dropdown syncs when chat infers a different park
