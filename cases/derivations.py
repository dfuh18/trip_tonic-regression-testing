"""The sixteen hand-chosen follow-ups (B05, D21: two per seed, D22: one
relation each from the catalogue its function permits).

Kept as data beside the cases rather than inside the notebook, for the reason
the cases themselves are files: these are the choices under review, and a
choice that only exists in an output cell is hard to diff and easy to lose.
`notebooks/sim/02_expand.ipynb` applies them and shows each one beside its
seed.

**Where the hard cases are.** Venue lookup and scheduling take all eight
relations, so both of their follow-ups are directional — the relations where a
structural check can state the expected delta and therefore where the checker
earns its keep. Factual QA takes only DIR-1 besides invariance, and advisory
takes invariance alone (D22), so those four seeds are lighter by construction.

**An honest property of the light half**, worth knowing before reading their
results: a factual-QA or advisory follow-up has **no structural delta**. The
same tools run, the same nothing is written, and what changed is the content
of the answer — which only the judge can see. Their structural verdict is
inherited from the seed and will read `none` whether or not the agent
answered the new question. That is not a defect in the cases; it is where
structural verification stops and P3's scoring starts, and §3.7 should say so.

**A follow-up is a cold open, not an edit of its seed.** Every repetition
starts a fresh conversation: the trip is rebuilt, there is no chat history, and
the agent has never seen the seed's request. So a perturbation written as a
diff — "actually…", "instead…", "not a sit-down meal…", "don't draft a whole
morning…" — refers to a turn that did not happen, and a correct agent may
reasonably ask what it is being contrasted with. The relation holds *between
two cases*; it must not be visible inside either sentence.

The exception, which is not an exception: a request may contrast with **trip
state the agent can see**. "Move the tram ride to Sunday instead" is fine —
the tram ride is on Friday in the itinerary the agent reads, so "instead" has
a referent. "Where should we eat instead" does not.

**One relation that was considered and rejected**, because it is the obvious
one: "ask for something more specific, expect fewer results". `search_places`
is capped at five results per call, so a tighter constraint never reduces
`places_surfaced` — the agent issues another search and the count goes *up*.
What narrowing changes is *which* venues come back, and asking for a second
kind of place changes the shape of the answer outright. Both of those are
stated below; the count is not.
"""

from src.metamorphic import Derivation

# --- venue lookup: both directional -----------------------------------------

SEAFOOD_SECOND_TYPE = Derivation(
    relation="DIR-1",
    suffix="dir1_and_a_hotel",
    opening_turn=(
        "/find good seafood places near Cais do Sodré, nothing too pricey — and somewhere "
        "to stay nearby too"
    ),
    goal=(
        "See well-rated seafood restaurants near Cais do Sodre that three people can afford, and a "
        "place to stay in the same area. She wants names for both and is satisfied once she has them. "
        "If Tonic offers to add any of them to the trip or asks which day they fit, she says no thanks "
        "and stops there: she only wants the names."
    ),
    checks={
        # Two kinds of thing to look up, so more searching — but still bounded,
        # because a case that permits any number of searches has stopped
        # noticing an agent that flails.
        # min 1, not 2: one broad search can legitimately surface both kinds, and
        # the outcome claim is carried by places_named_types. Asserting two
        # searches asserts the route (D30).
        "tool_counts": {"search_places": {"min": 1, "max": 5}},
        "places_surfaced": {"min": 2},
        "places_named": {"min": 3},
        # The delta that a count cannot express: five restaurants and "a
        # restaurant plus a hotel" are the same number.
        "places_named_types": ["restaurant", "lodging"],
    },
    scoring_criteria=[
        "Names at least two seafood restaurants and at least one place to stay.",
        "Keeps the two answers apart rather than running them into one list.",
        "Puts the accommodation near Cais do Sodre, not somewhere else in Lisbon.",
        "Reflects the budget cue for both halves of the request.",
    ],
    notes=(
        "The strongest perturbation available to a venue-lookup case: asking for a second kind of "
        "place changes the shape of the answer rather than its wording. Chosen over the obvious "
        "'ask for something narrower and expect fewer results', which is not a relation this system "
        "has — search_places is capped at five per call, so narrowing pushes the agent to search "
        "again and the count rises."
    ),
)

SEAFOOD_NEGATION = Derivation(
    relation="DIR-4",
    suffix="dir4_not_a_meal",
    opening_turn=(
        "/find where can we get a drink by the river near Cais do Sodre?"
    ),
    goal=(
        "See bars near Cais do Sodre with a river view where three people can have a drink - not "
        "restaurants, not a meal. She wants names to look at and is satisfied once she has them. If "
        "Tonic offers to add any of them to the trip or asks which day they fit, she says no thanks "
        "and stops there: she only wants the names."
    ),
    checks={
        # Negating the meal changes the KIND of place, which is stable between
        # runs. The venues themselves are not: four runs of one seed shared one
        # place id out of six, so the previous version of this case - which
        # claimed only "a different venue set from the seed" - was satisfied by
        # noise and verified nothing.
        "places_named_types": ["bar"],
        "places_named": {"min": 2},
    },
    scoring_criteria=[
        "Names at least two bars or drinking spots rather than restaurants.",
        "Answers the river cue rather than only the neighbourhood.",
        "Distinguishes them from each other, so the reasons are not interchangeable.",
        "Places each one by a neighbourhood or a landmark, so they can be told apart on a map.",
    ],
    notes=(
        "A negation that changes what kind of place is wanted, which is the only form of negation a "
        "venue-lookup case can state structurally. The earlier version inverted the price cue and "
        "asserted nothing a check could see. Types do not move between runs the way venues do - "
        "'restaurant' and 'seafood_restaurant' appeared in every run of the seed - so this catches an "
        "agent that hears 'near Cais do Sodre' and returns its usual seafood list regardless of "
        "being told it is not a meal."
    ),
)

SINTRA_DAY_CHANGED = Derivation(
    relation="DIR-2",
    suffix="dir2_lisbon_day",
    opening_turn=(
        "/find where should we eat lunch on the last day? near the hotel in Baixa, proper local food"
    ),
    goal=(
        "See lunch places near the hotel in Baixa for the last day of the trip that are not tourist "
        "traps. He wants somewhere to consider and is satisfied once he has the names. If Tonic offers "
        "to add any of them to the trip or asks which day they fit, he says no thanks and stops there."
    ),
    checks={
        # The anchor moves with the request. Without this the case's only
        # structural claim is "different venues from the seed", which two
        # different *Sintra* restaurants satisfy — the exact answer the
        # perturbation is supposed to rule out.
        "places_near": {"anchor": "Hotel near Baixa", "within_km": 5},
    },
    scoring_criteria=[
        "Names at least two places in or near Baixa, not out in Sintra.",
        "Works out which day is meant instead of asking, and answers for the last day.",
        "Answers the 'local food' cue with something specific.",
        "Places each one by a neighbourhood or a landmark, so they can be told apart on a map.",
    ],
    fixture_depends_on=["Hotel near Baixa", "2026-11-09"],
    notes=(
        "A day change that is also a region change, which is what makes it checkable: the seed's "
        "answers are in Sintra and this one's must be in Lisbon. The delta is geographic and is "
        "asserted as such — the seed requires every named place within 8 km of Pena Palace, this one "
        "within 5 km of the hotel in Baixa, and the two anchors are 23.5 km apart so no answer can "
        "satisfy both. different_venues_from_base rides along, but it is the weaker half: a venue "
        "set can differ from the seed's and still be in the wrong town, which is what made this case "
        "read weak before the geographic check existed."
    ),
)

SINTRA_CONSTRAINT_ADDED = Derivation(
    relation="DIR-1",
    suffix="dir1_coffee_not_lunch",
    opening_turn=(
        "/find where can we get a coffee and a pastry near the palace on the Sintra day?"
    ),
    goal=(
        "See cafes or pastry shops near Pena Palace for the Sintra day. He wants somewhere to "
        "consider for a mid-morning stop and is satisfied once he has the names. If Tonic offers to "
        "add any of them to the trip or asks which day they fit, he says no thanks."
    ),
    checks={
        "places_named_types": ["cafe"],
        "places_named": {"min": 2},
    },
    scoring_criteria=[
        "Names at least two cafes or pastry shops rather than full restaurants.",
        "Names at least two places in or near Sintra, not back in Lisbon.",
        "Works out which day is meant instead of asking, and answers for the Sintra day.",
        "Places each one by a neighbourhood or a landmark, so they can be told apart on a map.",
    ],
    notes=(
        "The constraint that changes is the kind of place, so the delta is checkable: the seed's "
        "answers are restaurants and this one's must be cafes or pastry shops. The earlier version "
        "added a dietary constraint, which changed no check except to loosen a search bound - its "
        "constraints were strictly weaker than its seed's, so it could not detect anything the seed "
        "missed. The geographic anchor is inherited unchanged, because the perturbation did not move "
        "the place: 8 km of Pena Palace still applies."
    ),
)

# --- scheduling: both directional -------------------------------------------

BELEM_DAY_CHANGED = Derivation(
    relation="DIR-2",
    suffix="dir2_on_the_9th",
    opening_turn=(
        "/plan can you put together a Belém morning for the 9th? two or three stops, we already have "
        "the monastery saved"
    ),
    goal=(
        "Get a draft for the morning of the 9th in Belem with two or three stops, so the group can "
        "settle them one by one. She is satisfied as soon as a draft for that morning exists: she "
        "settles the individual stops herself on the itinerary rather than asking Tonic to revise it, "
        "and if Tonic offers anything further she says that is all she needed."
    ),
    checks={"slot_days": ["2026-11-09"]},
    scoring_criteria=[
        "Summarises the morning in a few sentences and makes clear it is Belem, on the 9th, without "
        "reciting every stop back.",
        "Gives a reason each stop belongs in this morning rather than listing them flat.",
        "Treats the monastery as a stop the trip already has rather than as a new find.",
        "Sequences the stops so the morning is walkable: things near each other are near each other "
        "in the plan.",
    ],
    fixture_depends_on=["Jerónimos Monastery", "2026-11-09"],
    notes=(
        "The cleanest directional claim in the suite: one word changes and one check changes with it. "
        "The 9th is chosen over the 8th because the 8th already holds Pena Palace, and a draft that "
        "has to work around an existing stop has two defensible answers rather than one."
    ),
)

BELEM_COUNT_CHANGED = Derivation(
    relation="DIR-3",
    suffix="dir3_a_full_day",
    opening_turn=(
        "/plan can you put together a full Belém day for the 7th? five or six stops, we already have "
        "the monastery saved"
    ),
    goal=(
        "Get a draft for the whole of the 7th in Belem with five or six stops, so the group can settle "
        "them one by one. She is satisfied as soon as a draft for that day exists: she settles the "
        "individual stops herself on the itinerary rather than asking Tonic to revise it, and if Tonic "
        "offers anything further she says that is all she needed."
    ),
    checks={
        "slot_count": {"min": 5, "max": 7},
        # A day, not a morning: the seed's window would fail every afternoon
        # stop the member explicitly asked for.
        "draft_slot_starts_between": ["07:00", "19:00"],
        "tool_counts": {
            # 7, not 5: the recorded run used exactly 5, so the cap had no margin
            # and a sixth search - which more stops is a reason for - would have
            # failed a correct agent.
            "search_places": {"min": 1, "max": 7},
            "propose_plan": {"min": 1, "max": 2},
            "get_weather": {"min": 0, "max": 1},
        },
    },
    scoring_criteria=[
        "Summarises the day in a few sentences and makes clear it is Belem, on the 7th, without "
        "reciting every stop back.",
        "Gives a reason each stop belongs in this day rather than listing them flat.",
        "Treats the monastery as a stop the trip already has rather than as a new find.",
        "Paces the day so it is walkable and leaves room to eat.",
    ],
    notes=(
        "The count the member asks for is the delta, and the morning window has to go with it — a "
        "perturbation that makes one of the seed's checks untrue must drop it rather than leave it "
        "to fail. More stops is also more searching, so that bound widens too."
    ),
)

TRAM_DAY_CHANGED = Derivation(
    relation="DIR-2",
    suffix="dir2_sunday_afternoon",
    opening_turn="/reschedule can you move the tram ride to Sunday afternoon instead? around 4",
    goal=(
        "Move the Tram 28 ride off Friday morning to Sunday afternoon, around four. Once it has moved "
        "she is done; if Tonic offers to fill the freed Friday morning or to add anything else, she "
        "says no thanks."
    ),
    checks={
        "slot_moved": {
            "block": "Tram 28 ride through Alfama",
            "day": "2026-11-08",
            "starts_between": ["15:30", "16:30"],
            "duration_minutes": {"min": 45, "max": 90},
            "clear_of_other_slots": True,
        }
    },
    fixture_depends_on=["Tram 28 ride through Alfama", "2026-11-06", "2026-11-08"],
    notes=(
        "A day change onto a day that already holds Pena Palace until 13:00, so clear_of_other_slots "
        "is doing real work rather than passing by default — the agent has to land the ride in the "
        "free part of an occupied day. Sunday afternoon is chosen deliberately over Sunday morning, "
        "where the palace occupies the window the member named and the correct behaviour is arguable."
    ),
)

TRAM_SCHEDULE_THE_MONASTERY = Derivation(
    relation="DIR-1",
    suffix="dir1_put_the_monastery_on",
    opening_turn="/reschedule can you put the monastery on the itinerary on the 7th at 10?",
    user_profile=(
        "Ines, 29, the organiser. Direct, and says when she means the way people do: a day and a "
        "rough time."
    ),
    goal=(
        "Get the monastery the trip already has, and which is not on the itinerary yet, put on the "
        "7th at 10. Once it is on she is done; if Tonic offers to add anything else or to fill the "
        "rest of the morning, she says no thanks."
    ),
    expected_tool_sequence=["schedule_block"],
    checks={
        # The only case that reaches schedule_block, and it reaches it because
        # of the slash command: /plan exposes propose_plan and NOT the live
        # edit tools, so the first version of this case - written against the
        # planning seed - could not call schedule_block however it was worded,
        # and a correct agent drafted instead. The coverage report caught that
        # on the first run (D50).
        "tool_counts": {
            "schedule_block": {"min": 1, "max": 2},
            # Permitted and never satisfying, as in the seed. The standing
            # "check conditions during the trip dates" instruction is not
            # scoped to a command, so forbidding a probe here while the seed
            # and the sibling permit it would be two answers to one question.
            "get_weather": {"min": 0, "max": 1},
        },
        # Verifying that schedule_block RAN is not verifying that it did what
        # was asked: the request names a day and an hour, and without this an
        # agent that put the monastery on the 9th at 18:00 satisfied every
        # other check. slot_moved cannot serve - it reads UPDATE rows, and
        # scheduling an unscheduled stop is an INSERT.
        "slot_scheduled": {
            "block": "Jerónimos Monastery",
            "day": "2026-11-07",
            "starts_between": ["09:30", "10:30"],
            "duration_minutes": {"min": 60, "max": 180},
        },
        "mutation_counts": {
            "trip_blocks.INSERT": 0,
            "itinerary_slots.INSERT": {"min": 1, "max": 1},
            "itinerary_slots.UPDATE": 0,
            "ai_suggestions.INSERT": 0,
        },
        "edits": {"schedule": {"min": 1, "max": 1}, "move": 0, "unschedule": 0},
        # A stop the trip already has, scheduled: one more slot, and NOT one
        # more stop. An agent that creates a second monastery fails on blocks.
        "trip_after": {"blocks": "fixture", "slots": 4},
        "turn_errors": "none",
        "tool_errors": "corrected",
    },
    drop_checks=("slot_moved", "mutation_changed_keys"),
    scoring_criteria=[
        "Confirms the monastery is on the 7th at 10, in one short confirmation.",
        "Treats it as a stop the trip already has rather than as a new find.",
        "Does not move or drop anything else on the itinerary.",
    ],
    fixture_depends_on=["Jerónimos Monastery", "2026-11-07"],
    notes=(
        "The seed moves a stop that is already on the itinerary; this one puts on a stop that is "
        "saved and not scheduled, which is the other half of what a rescheduling request can mean "
        "and the only case in the suite that exercises schedule_block. It replaced a follow-up that "
        "moved the same stop to a different hour of the same day: that case isolated time resolution "
        "from date resolution, which is real, but move_slot was already covered by the seed and by "
        "the day-change follow-up, while schedule_block was covered by nothing. The trade is stated "
        "rather than hidden. The monastery is saved but unscheduled in the fixture, which is what "
        "makes the request answerable without inventing a stop."
    ),
)

TRAM_UNSCHEDULE = Derivation(
    relation="DIR-4",
    suffix="dir4_off_the_itinerary",
    opening_turn="/reschedule can you take the tram ride off the itinerary?",
    goal=(
        "Take the Tram 28 ride off the itinerary entirely - not moved to another day, removed. The "
        "stop should stay saved in the trip; she may still want it later. Once it is off she is "
        "done; if Tonic offers to put it somewhere else or to fill the freed Friday morning, she "
        "says no thanks."
    ),
    expected_tool_sequence=["unschedule_block"],
    checks={
        # max 2, not 1: with tool_errors "corrected", recovering from an
        # unschedule error means calling the tool again, which a cap of one
        # forbids - so the two keys contradicted each other and an error failed
        # under both branches whatever the agent did.
        "tool_counts": {
            "unschedule_block": {"min": 1, "max": 2},
            "get_weather": {"min": 0, "max": 1},
        },
        "mutation_counts": {
            "trip_blocks.INSERT": 0,
            "itinerary_slots.INSERT": 0,
            "itinerary_slots.UPDATE": 0,
            "ai_suggestions.INSERT": 0,
        },
        "edits": {"unschedule": {"min": 1, "max": 1}, "move": 0, "schedule": 0},
        # The distinction the request turns on, and the one an agent is most
        # likely to get wrong: unscheduling takes the stop off the itinerary
        # and leaves it saved in the trip. One slot fewer, the same stops.
        "trip_after": {"blocks": "fixture", "slots": 2},
        "turn_errors": "none",
        "tool_errors": "corrected",
    },
    drop_checks=("slot_moved", "mutation_changed_keys"),
    scoring_criteria=[
        "Confirms the tram ride is off the itinerary, in one short confirmation.",
        "Makes clear the stop is still saved in the trip rather than deleted.",
        "Does not silently move it somewhere else instead of removing it.",
    ],
    notes=(
        "A negation of the seed - not moved, removed - and the only case that exercises "
        "unschedule_block, which no case named and no execution called before it. trip_after carries "
        "the claim that matters: one slot fewer and the same number of stops, which is how an agent "
        "that deletes the stop instead of unscheduling it is caught. itinerary_slots.DELETE is "
        "deliberately not asserted - the mutation trigger's coverage of deletes is not something "
        "this case should be the first to depend on, and the edits journal plus trip_after already "
        "say the slot went."
    ),
)

# --- factual QA: DIR-1 is the only directional relation the catalogue allows --

ALFAMA_DIFFERENT_FACT = Derivation(
    relation="DIR-1",
    suffix="dir1_the_earthquake",
    opening_turn="@Tonic what happened to Alfama in the 1755 earthquake?",
    goal=(
        "Learn how Alfama fared in the 1755 earthquake. He wants the answer and nothing else; if Tonic "
        "offers to add anything to the trip he says no thanks."
    ),
    scoring_criteria=[
        "Says nothing the reference contradicts.",
        "Answers the earthquake question specifically rather than giving the district's whole history.",
        "Says what survived: the district kept its labyrinth of narrow streets and small squares "
        "rather than being rebuilt to a new plan.",
    ],
    notes=(
        "A different fact from the same stored article, so no new reference is needed and the seed's "
        "reference still governs. Structurally this is identical to its seed by design: the same tool "
        "answers it and nothing is written, so the delta is entirely in the content and only the "
        "judge can see it. That is the honest limit of a factual-QA directional relation."
    ),
)

ALFAMA_PARAPHRASE = Derivation(
    relation="INV-1",
    suffix="inv1_paraphrase",
    opening_turn="@Tonic give me the short version of how Alfama came to be what it is",
    notes=(
        "Paraphrase is the stronger of the two wording relations — a model that handles typos may "
        "still latch onto surface phrasing — so it is the invariance relation this seed gets."
        "Structurally this case is its seed: the same tools run, the same nothing is written, and what changed is the content of the answer. Its structural verdict is inherited and will read 'none' whether or not the agent answered the new question - only the judge sees the delta. That is where structural verification stops and scoring starts, and it is said here because a reader meeting 'none' in a failure report would otherwise believe something was checked."
    ),
)

WEATHER_DIFFERENT_FACT = Derivation(
    relation="DIR-1",
    suffix="dir1_july_instead",
    opening_turn="@Tonic what's the weather usually like in Lisbon in July?",
    goal=(
        "Know what the weather is usually like in Lisbon in July. She wants the figures and nothing "
        "else; if Tonic offers to change anything on the trip she says no thanks."
    ),
    scoring_criteria=[
        "Gives typical July figures for Lisbon that agree with a reference: a daily high near 28 C "
        "and a low near 18 C.",
        "Places July among the driest months of the Lisbon year, not the wettest.",
        "Says which source or kind of data the figures come from.",
        "Distinguishes a typical July from any particular one.",
    ],
    notes=(
        "The month is the perturbation, and the stored climate references carry every month, so the "
        "seed's references still serve. It is also the sharper half of the pair: November and July "
        "sit at opposite ends of the Lisbon year, so an agent answering from the wrong month is "
        "obvious in the scoring rather than arguable."
        "Structurally this case is its seed: the same tools run, the same nothing is written, and what changed is the content of the answer. Its structural verdict is inherited and will read 'none' whether or not the agent answered the new question - only the judge sees the delta. That is where structural verification stops and scoring starts, and it is said here because a reader meeting 'none' in a failure report would otherwise believe something was checked."
    ),
)

WEATHER_PARAPHRASE = Derivation(
    relation="INV-1",
    suffix="inv1_paraphrase",
    opening_turn="@Tonic roughly what sort of weather should we expect in Lisbon at this time of year?",
    notes=(
        "Paraphrased, and deliberately vaguer: 'this time of year' makes the agent resolve the month "
        "from the trip rather than from the sentence, which is the part of the seed's behaviour most "
        "likely to break under rewording."
        "Structurally this case is its seed: the same tools run, the same nothing is written, and what changed is the content of the answer. Its structural verdict is inherited and will read 'none' whether or not the agent answered the new question - only the judge sees the delta. That is where structural verification stops and scoring starts, and it is said here because a reader meeting 'none' in a failure report would otherwise believe something was checked."
    ),
)

# --- advisory: invariance only (D22) ----------------------------------------

PACKING_PARAPHRASE = Derivation(
    relation="INV-1",
    suffix="inv1_paraphrase",
    opening_turn="@Tonic we're trying to work out what to bring — any thoughts for the three of us?",
    notes=(
        "Advisory takes invariance alone: there is no directional perturbation of 'what should we "
        "pack' whose expected delta a case could state without inventing a rule about advice."
        "Structurally this case is its seed: the same tools run, the same nothing is written, and what changed is the content of the answer. Its structural verdict is inherited and will read 'none' whether or not the agent answered the new question - only the judge sees the delta. That is where structural verification stops and scoring starts, and it is said here because a reader meeting 'none' in a failure report would otherwise believe something was checked."
    ),
)

PACKING_IRRELEVANT_DETAIL = Derivation(
    relation="INV-3",
    suffix="inv3_irrelevant_detail",
    opening_turn=(
        "@Tonic what should the three of us pack for this trip? we just bought a huge new suitcase "
        "so space isn't really a problem"
    ),
    scoring_criteria=[
        # Without this the case cannot see the thing it exists for: all four
        # inherited criteria are satisfied by a reply that lets the luggage
        # remark inflate the list, so the perturbation had no detector at all.
        "Does not let the luggage-capacity remark change the advice: the list is no longer or more "
        "indulgent for it.",
        "Ties at least one item to something specific about this trip - the Sintra hills, the "
        "cobbled streets, or November rain - rather than reading as a generic city-break list.",
        "Fits the season and the places in the summary: November, Lisbon and Sintra, a day at a "
        "hilltop palace.",
        "Names specific items rather than describing categories.",
        "Writes for the group rather than for one traveller.",
    ],
    notes=(
        "The added detail is deliberately almost-relevant rather than nonsense: luggage capacity "
        "sounds like it bears on a packing list and does not, so an agent that lets it steer the "
        "answer has been distracted by something a person would discount."
        "Structurally this case is its seed: the same tools run, the same nothing is written, and what changed is the content of the answer. Its structural verdict is inherited and will read 'none' whether or not the agent answered the new question - only the judge sees the delta. That is where structural verification stops and scoring starts, and it is said here because a reader meeting 'none' in a failure report would otherwise believe something was checked."
    ),
)

SINTRA_ADVICE_PARAPHRASE = Derivation(
    relation="INV-1",
    suffix="inv1_paraphrase",
    opening_turn="@Tonic do you reckon Sintra needs a whole day, or would half of one do?",
    notes="The same question in the register a person actually uses.",
)

SINTRA_ADVICE_GERMAN = Derivation(
    relation="INV-4",
    suffix="inv4_german",
    opening_turn="@Tonic lohnt sich Sintra für einen ganzen Tag oder reicht ein halber?",
    user_profile=(
        "Tom, 41, weighing the schedule, wants a recommendation with a reason. Writes to Tonic in "
        "German, which is his first language."
        "Structurally this case is its seed: the same tools run, the same nothing is written, and what changed is the content of the answer. Its structural verdict is inherited and will read 'none' whether or not the agent answered the new question - only the judge sees the delta. That is where structural verification stops and scoring starts, and it is said here because a reader meeting 'none' in a failure report would otherwise believe something was checked."
    ),
    goal=(
        "Decide whether Sintra deserves the whole of the Sunday or half of it. He asks in German and "
        "expects an answer he can read. He wants a recommendation; if Tonic offers to change the "
        "itinerary he says no thanks, he is only asking."
    ),
    scoring_criteria=[
        "Answers in the language the member wrote in.",
        "Comes down on full day or half day and gives the reason.",
        "Refers to Pena Palace, which the summary shows is already on that day.",
        "Names what the choice costs: what a half day gives up, or what a full day leaves no room "
        "for.",
    ],
    notes=(
        "The language switch, which no other case in the suite uses. It replaced a typo perturbation "
        "of this same seed, and the reason is that the typo case and its sibling paraphrase tested "
        "one property between them - tolerance to how the sentence is written - so a single "
        "robustness regression would break both and the pair would buy one finding for eight "
        "executions. A language switch tests what the paraphrase cannot: whether the agent answers "
        "in the member's language, and whether it still reaches the trip's own state to refer to "
        "Pena Palace when the request is not in English. The cost, stated: the judge scores a German "
        "reply against English criteria, which the criteria are worded to survive."
    ),
)

#: seed case_id -> its follow-ups. Two each (D21), except the two
#: scheduling seeds, which take a third to reach schedule_block and
#: unschedule_block - tools no other case could name, because they belong
#: to the scheduling function and both of its seeds had spent their pair
#: on stronger relations (D50).
DERIVATIONS: dict[str, tuple[Derivation, ...]] = {
    "venue_lookup_seafood_lisbon": (SEAFOOD_SECOND_TYPE, SEAFOOD_NEGATION),
    "venue_lookup_sintra_lunch": (SINTRA_DAY_CHANGED, SINTRA_CONSTRAINT_ADDED),
    "scheduling_belem_morning": (BELEM_DAY_CHANGED, BELEM_COUNT_CHANGED),
    "scheduling_move_tram": (TRAM_DAY_CHANGED, TRAM_SCHEDULE_THE_MONASTERY, TRAM_UNSCHEDULE),
    "factual_qa_alfama_history": (ALFAMA_DIFFERENT_FACT, ALFAMA_PARAPHRASE),
    "factual_qa_lisbon_november_weather": (WEATHER_DIFFERENT_FACT, WEATHER_PARAPHRASE),
    "advisory_packing_list": (PACKING_PARAPHRASE, PACKING_IRRELEVANT_DETAIL),
    "advisory_sintra_full_or_half_day": (SINTRA_ADVICE_PARAPHRASE, SINTRA_ADVICE_GERMAN),
}
