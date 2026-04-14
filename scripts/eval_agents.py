"""Wanderlisted Agent Evaluation Runner.

Uploads the golden dataset to LangSmith and runs experiments with
code-based evaluators, RAG evaluators, and LLM-as-Judge.

All evaluation runs exclusively through LangSmith — no external
evaluation frameworks required.

Usage:
    # Upload dataset only
    python scripts/eval_agents.py --upload-dataset

    # Run full evaluation (agent + RAG)
    python scripts/eval_agents.py --run

    # Run agent evaluators only
    python scripts/eval_agents.py --run --mode agent

    # Run RAG evaluators only
    python scripts/eval_agents.py --run --mode rag

    # Run with a specific experiment prefix
    python scripts/eval_agents.py --run --prefix "v5-gpt4o-mini"
"""

import argparse
import asyncio
import os
import sys
import uuid

from dotenv import load_dotenv

load_dotenv()

# Must be set before importing LangSmith
os.environ.setdefault("LANGSMITH_TRACING", "true")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langsmith import Client  # noqa: E402
from langsmith import evaluate  # noqa: E402

from src.evaluation.evaluators import (  # noqa: E402
    correct_destination,
    correct_tool_routing,
    valid_routing_decision,
    budget_completeness,
    non_empty_response,
    handbook_section_completeness,
    travel_quality_judge,
    # RAG evaluators
    context_precision,
    context_recall,
    context_entity_recall,
    noise_sensitivity,
    response_relevancy,
    faithfulness,
)
from src.evaluation.golden_dataset import GOLDEN_DATASET  # noqa: E402

DATASET_NAME = "Wanderlisted Travel Planning Golden Dataset"
RAG_DATASET_NAME = "Wanderlisted RAG Golden Dataset"


# ── RAG evaluation dataset ───────────────────────────────────────────────
# Best practice: ≥50 examples, 2-3 per destination, varied question types,
# edge cases, and negative cases. Reference answers grounded in KB content.
RAG_GOLDEN_DATASET = [
    # ── Bangkok (3) ──────────────────────────────────────────────────────
    {
        "inputs": {"question": "What are the best temples to visit in Bangkok?"},
        "outputs": {
            "reference": (
                "Top temples in Bangkok include Wat Pho (Reclining Buddha), "
                "Wat Arun (Temple of Dawn), and the Grand Palace with Wat Phra Kaew."
            ),
        },
    },
    {
        "inputs": {"question": "What street food should I try in Bangkok?"},
        "outputs": {
            "reference": (
                "Must-try Bangkok street food: Pad Thai (~50 baht), Som Tam (papaya salad), "
                "satay (5-10 baht/skewer), Khao Man Gai (chicken rice), Tom Yum Kung. "
                "Yaowarat (Chinatown) has huge BBQ prawns (~300 baht/kg). "
                "Say 'mai pet' for less spicy."
            ),
        },
    },
    {
        "inputs": {"question": "What scams should I avoid in Bangkok?"},
        "outputs": {
            "reference": (
                "Common Bangkok scams: gem scam (tuk-tuk drivers offer 10-baht 'tours' "
                "ending at worthless gem shops), 'attraction is closed' scam (strangers "
                "redirect you to touts), taxi drivers not using meters. Always insist on "
                "the meter ('mee-TOE, khap'). Don't trust taxi restaurant recommendations."
            ),
        },
    },
    # ── Tokyo (3) ────────────────────────────────────────────────────────
    {
        "inputs": {"question": "What is the best time to visit Tokyo?"},
        "outputs": {
            "reference": (
                "The best time to visit Tokyo is spring (March-May) for cherry blossoms "
                "or autumn (October-November) for fall foliage and pleasant temperatures."
            ),
        },
    },
    {
        "inputs": {"question": "How safe is Tokyo for solo travelers?"},
        "outputs": {
            "reference": (
                "Tokyo is extremely safe — one of the safest cities in the world. "
                "Street crime is nearly nonexistent even late at night. Main concern is "
                "groping on crowded trains (yell 'Chikan!'). Women-only cars available "
                "during rush hour. Avoid touts in Roppongi. Small police stations (koban) "
                "every few blocks for assistance."
            ),
        },
    },
    {
        "inputs": {"question": "Where to eat on a budget in Tokyo?"},
        "outputs": {
            "reference": (
                "Budget eating in Tokyo: noodle shops (¥300-1000, ticket vending machines), "
                "donburi chains like Matsuya/Yoshinoya (~¥450), kaitenzushi (conveyor belt "
                "sushi), convenience store onigiri (¥100) and bento (¥500). "
                "Supermarkets discount after 19:00 — look for half-price stickers."
            ),
        },
    },
    # ── Paris (3) ────────────────────────────────────────────────────────
    {
        "inputs": {"question": "What are the most common scams in Paris?"},
        "outputs": {
            "reference": (
                "Paris scams: string/bracelet muggers at Sacré-Cœur, fake petition/deaf "
                "charity collectors (pickpocket cover), 'found ring' con along the Seine, "
                "3-card monte on bridges, clip joints near Barbès/Moulin Rouge (€200-500 "
                "bills for a drink), ticket machine cons at metro stations."
            ),
        },
    },
    {
        "inputs": {"question": "How to eat well on a budget in Paris?"},
        "outputs": {
            "reference": (
                "Budget eating in Paris: bakery breakfast (~€5), street lunch (crêpe, "
                "falafel on Rue des Rosiers ~€5, banh mi), then €20-40 prix-fixe dinner. "
                "Self-catering with baguette + cheese + wine (€3-5/bottle) for Seine picnics. "
                "Markets on Rue Mouffetard and Place Buci."
            ),
        },
    },
    {
        "inputs": {"question": "How to get from CDG airport to central Paris?"},
        "outputs": {
            "reference": (
                "Take the RER B from CDG to central Paris (€13, every 10 minutes). "
                "Metro 14 runs from Orly (€13). Noctilien night buses available for "
                "late arrivals. Paris is organized in 20 arrondissements in a clockwise spiral."
            ),
        },
    },
    # ── Rome (3) ─────────────────────────────────────────────────────────
    {
        "inputs": {"question": "What should I know about pickpocketing in Rome?"},
        "outputs": {
            "reference": (
                "Pickpocketing in Rome is extreme — second only to Barcelona. "
                "Gangs of young girls on the Metro, moped bag-snatchers, beggar kid "
                "distractions. Hotspots: Termini station, bus 64, Trevi Fountain. "
                "Use taxi apps (Free Now, itTaxi) to avoid taxi scams."
            ),
        },
    },
    {
        "inputs": {
            "question": "Where to find authentic food in Rome, not tourist traps?"
        },
        "outputs": {
            "reference": (
                "Best food in Rome is off the tourist trail in residential areas like "
                "Monte Verde Vecchio and Trastevere. Avoid guidebook restaurants near "
                "major sights. Roman pizza is thin-crusted (eat with fork and knife). "
                "Pizza al Taglio (by weight) is cheap grab-and-go (~€3.50). "
                "For gelato, look for dull natural colors — bright means artificial."
            ),
        },
    },
    {
        "inputs": {"question": "What are the must-see historical sites in Rome?"},
        "outputs": {
            "reference": (
                "Must-see in Rome: Colosseum, Vatican City (St. Peter's Basilica, "
                "Sistine Chapel), Pantheon, Roman Forum, Trevi Fountain, Piazza Navona. "
                "Many shops close 2 weeks in August ('Chiuso per ferie')."
            ),
        },
    },
    # ── London (3) ───────────────────────────────────────────────────────
    {
        "inputs": {"question": "Best ethnic food neighborhoods in London?"},
        "outputs": {
            "reference": (
                "London ethnic food clusters: Brick Lane (Bangladeshi, salt beef beigels), "
                "Brixton (African/Caribbean), Chinatown, Edgware Road (Middle Eastern), "
                "Tooting and Southall (Indian). Borough Market for artisan food. "
                "Vegan hotspots in Hackney, Dalston, Islington, Soho."
            ),
        },
    },
    {
        "inputs": {"question": "What safety concerns should I know about in London?"},
        "outputs": {
            "reference": (
                "London is generally safe. Main crime: phone snatching (often by moped "
                "riders). Scams: cup-and-ball game on Westminster Bridge (lookouts "
                "pickpocket watchers), ATM skimming, clip joints in Soho, pedicab "
                "overcharging. Avoid illegal minicabs. Emergency: 999 or 112."
            ),
        },
    },
    {
        "inputs": {"question": "What are the top attractions in London?"},
        "outputs": {
            "reference": (
                "Top London attractions: Tower of London, Buckingham Palace, "
                "Westminster Abbey, Big Ben, Kensington Palace, Royal Albert Hall, "
                "Borough Market, British Museum. London has 32 boroughs plus the "
                "City of London."
            ),
        },
    },
    # ── Istanbul (3) ─────────────────────────────────────────────────────
    {
        "inputs": {"question": "What street food should I try in Istanbul?"},
        "outputs": {
            "reference": (
                "Istanbul street food: balik-ekmek (grilled mackerel sandwich), doner/durum, "
                "kokorec (grilled lamb intestines), lahmacun ('Turkish pizza'), simit, "
                "kumpir (loaded baked potato in Ortakoy), roasted chestnuts. "
                "Fresh-squeezed pomegranate juice stands are everywhere."
            ),
        },
    },
    {
        "inputs": {"question": "What taxi scams are common in Istanbul?"},
        "outputs": {
            "reference": (
                "Istanbul taxi scams: long routes, bill-switching (50 TL swapped for "
                "5 TL sleight-of-hand), counterfeit bills as change. Tips: sit in front, "
                "watch the meter, know the route. Choose elderly drivers. Also beware "
                "the shoe-shine scam (brush 'falls,' then demands payment) and bar scams "
                "in Taksim where friendly strangers lead to extortionate bills."
            ),
        },
    },
    {
        "inputs": {"question": "How does Istanbul's public transport work?"},
        "outputs": {
            "reference": (
                "Istanbul uses the Istanbulkart for all transit (metro, bus, ferry, tram). "
                "M11 metro from Istanbul Airport. Havaist buses to Aksaray (~€5.42, 90 min). "
                "M4 metro from Sabiha Gokcen. Marmaray train crosses under the Bosphorus. "
                "The city straddles Europe and Asia."
            ),
        },
    },
    # ── Cape Town (3) ────────────────────────────────────────────────────
    {
        "inputs": {"question": "What seafood should I try in Cape Town?"},
        "outputs": {
            "reference": (
                "Cape Town seafood highlights: yellowtail, cape salmon, kingklip, "
                "Knysna oysters (farmed and wild). Hout Bay for fresh crayfish (lobster, "
                "~R650+), Kalk Bay (The Brass Bell) for fresh fish. Ask about daily "
                "linefish. Verify prices before ordering rare dishes like abalone."
            ),
        },
    },
    {
        "inputs": {"question": "Is Cape Town safe for tourists?"},
        "outputs": {
            "reference": (
                "Cape Town requires more vigilance than most cities. Central area is safe "
                "by day but always take taxi/ride-hailing after dark, never walk. "
                "Don't dress like a tourist (no cameras/backpacks on display). "
                "Mountains: go in groups of 4+, avoid walking Table Mountain alone. "
                "Smash-and-grab risk when driving — doors locked, windows up at lights."
            ),
        },
    },
    {
        "inputs": {"question": "What wine regions are near Cape Town?"},
        "outputs": {
            "reference": (
                "Cape Winelands near Cape Town: Franschhoek (culinary capital), "
                "Stellenbosch (Spier, Moyo), Constantia Valley (La Colombe). "
                "Also Paarl. Bo-Kaap is famous for Cape Malay cuisine, especially bobotie."
            ),
        },
    },
    # ── Medellín (2) ─────────────────────────────────────────────────────
    {
        "inputs": {"question": "Is Medellín safe to visit now?"},
        "outputs": {
            "reference": (
                "Medellín has dramatically improved — homicides dropped from 6,500 in "
                "1991 to 392 in 2022 (~15 per 100K, comparable to Denver/Dallas). "
                "Colombia's only Metro system plus Metrocable sky gondolas. Known as "
                "'City of eternal spring' with avg 22°C year-round."
            ),
        },
    },
    {
        "inputs": {"question": "How does the metro work in Medellín?"},
        "outputs": {
            "reference": (
                "Medellín has Colombia's only Metro system with Metrocable sky gondolas "
                "(free transfers). Use Tarjeta Civica card (COP$2,255 reduced fare). "
                "Most restaurants are open-air due to the perfect climate. "
                "Uber/Cabify available but officially illegal."
            ),
        },
    },
    # ── Bogotá (2) ───────────────────────────────────────────────────────
    {
        "inputs": {"question": "How do I safely get a taxi in Bogotá?"},
        "outputs": {
            "reference": (
                "NEVER hail taxis off the street in Bogotá — 'paseo millonario' "
                "kidnap/robbery scam is common. Use dispatch services (599-9999, "
                "311-1111) or ride-hailing apps (InDrive, Uber, Didi — officially "
                "illegal but widely used). Very limited English proficiency citywide."
            ),
        },
    },
    {
        "inputs": {"question": "What are the top things to see in Bogotá?"},
        "outputs": {
            "reference": (
                "Top Bogotá attractions: Gold Museum, La Candelaria historic center, "
                "Monserrate Sanctuary, Teatro Colon, Parque Simon Bolivar (largest "
                "urban park in the Americas). City has 500+ km of bike paths and "
                "Ciclovía car-free Sundays."
            ),
        },
    },
    # ── Lima (2) ─────────────────────────────────────────────────────────
    {
        "inputs": {"question": "How do I get from Lima airport to Miraflores?"},
        "outputs": {
            "reference": (
                "Airport Express bus to Miraflores (20 soles). Green Taxi from airport "
                "(65 soles to Miraflores). Area around airport is unsafe — verify Uber "
                "driver identity, avoid informal taxis. Outside the airport grounds, "
                "taxis cost ~25-30 soles."
            ),
        },
    },
    {
        "inputs": {"question": "Why is Lima considered a food destination?"},
        "outputs": {
            "reference": (
                "Lima is the best Peruvian cuisine hub. The cold Humboldt Current "
                "makes seafood exceptional. Huge variety from coast, mountain, and "
                "Amazon regions. Pre-Inca civilizations (Moche, Chavin, Inca) "
                "influenced the culinary tradition."
            ),
        },
    },
    # ── Mexico City (2) ──────────────────────────────────────────────────
    {
        "inputs": {"question": "What are the best restaurants in Mexico City?"},
        "outputs": {
            "reference": (
                "World-class Mexico City restaurants: Pujol and Quintonil in Polanco, "
                "Ling Ling for skyline views. Street stands are cheap and excellent. "
                "Centro Historico is UNESCO World Heritage. Budget M$150-300/day, "
                "comfortable M$300-500/day."
            ),
        },
    },
    {
        "inputs": {"question": "What should I know about altitude in Mexico City?"},
        "outputs": {
            "reference": (
                "Mexico City sits at 2,240m altitude which can cause breathing issues. "
                "Climate is temperate oceanic monsoon — mornings cold in winter (0°C), "
                "highs 32°C in spring. Air quality much improved but still variable. "
                "Monsoon season June-September."
            ),
        },
    },
    # ── Kraków (2) ───────────────────────────────────────────────────────
    {
        "inputs": {"question": "What should I visit in Kraków?"},
        "outputs": {
            "reference": (
                "Kraków attractions: Main Market Square, Wawel Castle, Sukiennice "
                "(Cloth Hall), St. Mary's Church, Kazimierz (Jewish quarter), "
                "Nowa Huta (communist-era town). Nearby: Auschwitz. "
                "UNESCO World Heritage since 1978."
            ),
        },
    },
    {
        "inputs": {"question": "How to get from Kraków airport to the city center?"},
        "outputs": {
            "reference": (
                "Train from Kraków airport (20 zl, 20 min, every 30 min). "
                "Bus 208/902 (6 zl, need agglomeration Zone I+II ticket). "
                "Uber/Bolt 25-35 zl to centre. Official taxi 90 zl. "
                "Severe air pollution in winter from coal stoves."
            ),
        },
    },
    # ── Marrakech (2) ────────────────────────────────────────────────────
    {
        "inputs": {"question": "What scams should I watch out for in Marrakech?"},
        "outputs": {
            "reference": (
                "Marrakech is known for tourist scams ('Marrakech, Arnakech'). "
                "Aggressive taxi touts at airport/train stations — ignore them. "
                "Taxi drivers lie about bus schedules. Fixed airport taxi 200 MAD "
                "vs 60 MAD from the road. City bus is only 4 MAD."
            ),
        },
    },
    {
        "inputs": {"question": "How do I get from the airport to Djemaa El-Fna?"},
        "outputs": {
            "reference": (
                "L19 airport shuttle (30 MAD one-way) or petit taxi metered at "
                "~12 MAD to Djemaa El-Fna. Avoid fixed-price airport taxis (200 MAD). "
                "Trains from Casablanca cost 84 MAD 2nd class (3 hours)."
            ),
        },
    },
    # ── Buenos Aires (2) ─────────────────────────────────────────────────
    {
        "inputs": {"question": "What's unique about Buenos Aires culture?"},
        "outputs": {
            "reference": (
                "Buenos Aires is famous for tango culture, belle epoque architecture, "
                "and Porteño Spanish where 'll' sounds like English 'sh' (Italian influence). "
                "One of Latin America's biggest LGBT communities, same-sex marriage legal. "
                "Avenida 9 de Julio with the Obelisco is a key landmark."
            ),
        },
    },
    {
        "inputs": {
            "question": "How do I get from Ezeiza airport to downtown Buenos Aires?"
        },
        "outputs": {
            "reference": (
                "Ezeiza airport is ~35 km south (~1 hour by car). SUBE card needed "
                "for buses. Bus line 33 runs from Aeroparque (domestic flights near "
                "downtown). Domestic flights are more expensive for foreigners."
            ),
        },
    },
    # ── Rio de Janeiro (2) ───────────────────────────────────────────────
    {
        "inputs": {"question": "Is Rio de Janeiro safe for tourists?"},
        "outputs": {
            "reference": (
                "Rio is known for crime, especially drug-related violence. "
                "Avoid favelas without official tours. Watch for taxi diversions. "
                "Avoid unofficial airport taxis — pre-set fares are about double "
                "standard yellow taxis (~100m from exit for cheaper rates). "
                "Copacabana and Ipanema are safer but still exercise caution."
            ),
        },
    },
    {
        "inputs": {"question": "What are the top attractions in Rio de Janeiro?"},
        "outputs": {
            "reference": (
                "Top Rio attractions: Christ the Redeemer, Sugarloaf Mountain, "
                "Copacabana and Ipanema beaches, Maracana stadium, Carnival. "
                "The harbor landscape is UNESCO World Heritage. Climate is tropical — "
                "hot humid summer (Dec-Jan) up to 40°C."
            ),
        },
    },
    # ── Cancún (2) ───────────────────────────────────────────────────────
    {
        "inputs": {"question": "How much does a budget trip to Cancun cost per day?"},
        "outputs": {
            "reference": (
                "A budget trip to Cancun costs roughly $50-80 USD per day including "
                "a hostel ($15-25), street food meals ($10-15), local transport ($5), "
                "and one activity ($20-35). Peak season Dec-Apr is more expensive."
            ),
        },
    },
    {
        "inputs": {
            "question": "What's the difference between Cancun Hotel Zone and downtown?"
        },
        "outputs": {
            "reference": (
                "Cancun Hotel Zone is a 22 km strip of Caribbean beaches and resorts — "
                "often called a 'Mexican clone of Florida'. Downtown City Center has "
                "the authentic Mexican feel with supermanzana grid layout. "
                "Cancun had no history before 1970s — entirely government-planned."
            ),
        },
    },
    # ── Cairo (2) ────────────────────────────────────────────────────────
    {
        "inputs": {"question": "What are the must-see attractions in Cairo?"},
        "outputs": {
            "reference": (
                "Must-see Cairo attractions: the Pyramids of Giza and Great Sphinx, "
                "the Egyptian Museum, Khan el-Khalili bazaar, and Coptic Cairo."
            ),
        },
    },
    {
        "inputs": {
            "question": "What cultural customs should I know for visiting Egypt?"
        },
        "outputs": {
            "reference": (
                "Key customs in Egypt: dress modestly (especially at mosques), "
                "remove shoes before entering mosques, bargaining is expected in "
                "markets, tipping (baksheesh) is customary for services."
            ),
        },
    },
    # ── Tallinn (2) ──────────────────────────────────────────────────────
    {
        "inputs": {"question": "What makes Tallinn's Old Town special?"},
        "outputs": {
            "reference": (
                "Tallinn's medieval Old Town is a UNESCO World Heritage site since 1997 "
                "with Toompea fortress, Kadriorg palace/park, Kalamaja wooden houses. "
                "Hanseatic League heritage. ~450K inhabitants with close Finnish/Nordic "
                "cultural ties."
            ),
        },
    },
    {
        "inputs": {"question": "How to get from Helsinki to Tallinn?"},
        "outputs": {
            "reference": (
                "Ferry from Helsinki (1.5-3.5 hours, €16-30 one-way, 20+ daily "
                "departures). Day cruises as low as €19 return. Ferry car from €25. "
                "Tram 2 from the port to Tallinn centre."
            ),
        },
    },
    # ── Moscow (2) ───────────────────────────────────────────────────────
    {
        "inputs": {
            "question": "How to get from Sheremetyevo airport to central Moscow?"
        },
        "outputs": {
            "reference": (
                "Aeroexpress train from Sheremetyevo (~50 min, tickets online). "
                "Extensive Metro system (longest/busiest in Europe). "
                "Yandex Taxi (~RUB 1,000 from airports). Troika transport card "
                "for metro/bus. Bus 851/308 as cheaper options."
            ),
        },
    },
    {
        "inputs": {"question": "What are the top landmarks in Moscow?"},
        "outputs": {
            "reference": (
                "Moscow landmarks: Kremlin, Red Square, St. Basil's Cathedral, "
                "Christ the Savior Cathedral. Moscow Metro is the longest and "
                "busiest in Europe. Northernmost and coldest megacity on Earth "
                "with ~13M population."
            ),
        },
    },
    # ── Quito (2) ────────────────────────────────────────────────────────
    {
        "inputs": {"question": "What's special about Quito's Old Town?"},
        "outputs": {
            "reference": (
                "Quito has the largest intact colonial Old City in the Americas "
                "(UNESCO 1978), with 40+ churches and 16 convents. San Francisco "
                "convent (1535) is the oldest in South America. Independence Plaza "
                "has the Presidential Palace. Mitad del Mundo monument nearby."
            ),
        },
    },
    {
        "inputs": {"question": "What should I know about altitude sickness in Quito?"},
        "outputs": {
            "reference": (
                "Quito sits at 2,850m altitude — expect altitude sickness the first "
                "days. Climate is steady 10°C nights / 21°C days year-round. No AC or "
                "heat needed. Conservative dress — shorts uncommon. Excellent for "
                "learning Spanish (clear, slow speech)."
            ),
        },
    },
    # ── Santiago (2) ─────────────────────────────────────────────────────
    {
        "inputs": {"question": "What's the climate like in Santiago, Chile?"},
        "outputs": {
            "reference": (
                "Santiago has a Mediterranean climate — chilly rainy winters (near 0°C "
                "at night), dry hot summers (35°C+). Wild day-night temperature swings. "
                "Poor air quality due to basin inversion effect. Possible to ski and "
                "visit the beach on the same day."
            ),
        },
    },
    {
        "inputs": {"question": "How to get from Santiago airport to the city?"},
        "outputs": {
            "reference": (
                "Centropuerto/Turbus airport bus (2,000 pesos). Red bus 555 to "
                "Pajaritos metro (800 pesos or less with Metro card). "
                "Gran Torre Santiago is the tallest building in Latin America."
            ),
        },
    },
    # ── Warsaw (2) ───────────────────────────────────────────────────────
    {
        "inputs": {"question": "What's the history behind Warsaw's Old Town?"},
        "outputs": {
            "reference": (
                "Warsaw is a 'Phoenix city' — 80% destroyed in WWII, meticulously "
                "rebuilt from rubble. Attractions: rebuilt Old Town, Royal Castle, "
                "Palace of Culture and Science (Stalinist landmark), Wilanow Palace. "
                "Formerly one of Europe's largest Jewish populations."
            ),
        },
    },
    {
        "inputs": {"question": "Where to eat cheaply in Warsaw?"},
        "outputs": {
            "reference": (
                "Bar mleczny (milk bars) — cheap traditional Polish cafeteria dining "
                "surviving from the communist era. No-frills traditional Polish food at "
                "very low prices. Warsaw has variable weather with very cold winters "
                "(down to -20°C)."
            ),
        },
    },
    # ── Cross-destination comparisons (3) ────────────────────────────────
    {
        "inputs": {
            "question": "Which is cheaper for a budget trip, Bangkok or Cancun?"
        },
        "outputs": {
            "reference": (
                "Bangkok is generally cheaper. Street food from 50 baht (~$1.50), "
                "budget accommodations widely available. Cancun budget is roughly "
                "$50-80 USD per day. Bangkok offers better value for backpackers."
            ),
        },
    },
    {
        "inputs": {
            "question": "Safest cities in Latin America for solo female travelers?"
        },
        "outputs": {
            "reference": (
                "Among the destinations covered, Santiago and Buenos Aires are "
                "generally considered safer. Medellin has improved dramatically. "
                "Bogota requires caution (never hail street taxis). "
                "Rio has higher crime rates including in tourist areas."
            ),
        },
    },
    {
        "inputs": {"question": "Best European cities for medieval history?"},
        "outputs": {
            "reference": (
                "Tallinn (medieval Old Town, UNESCO, Hanseatic heritage), "
                "Krakow (Wawel Castle, Main Market Square, UNESCO since 1978), "
                "and Rome (Colosseum, Roman Forum, 2,500+ years of history) "
                "are top picks for medieval and ancient European history."
            ),
        },
    },
    # ── Edge cases / negative cases (4) ──────────────────────────────────
    {
        "inputs": {"question": "What's the best hotel in Antarctica?"},
        "outputs": {
            "reference": (
                "Antarctica is not covered in the destination guides. "
                "The system should indicate it doesn't have information on this destination."
            ),
        },
    },
    {
        "inputs": {"question": "Tell me about the nightlife in Pyongyang"},
        "outputs": {
            "reference": (
                "Pyongyang is not covered in the destination guides. "
                "The system should indicate it doesn't have information on this destination."
            ),
        },
    },
    {
        "inputs": {"question": "Temples"},
        "outputs": {
            "reference": (
                "The query is ambiguous. Bangkok has Wat Pho and Wat Arun. "
                "Tokyo has temples and shrines. The system should ask for clarification "
                "or provide temples across multiple destinations."
            ),
        },
    },
    {
        "inputs": {"question": "Is the tap water safe to drink in Bangkok?"},
        "outputs": {
            "reference": (
                "Do not drink tap water in Bangkok — drink bottled water only. "
                "Avoid raw leafy vegetables, mayo, and unpackaged ice cream outside hotels. "
                "Round-hole ice is commercially purified; irregular chunks may be unsafe."
            ),
        },
    },
]


def upload_dataset() -> str:
    """Create or update both golden datasets in LangSmith."""
    client = Client()

    # Agent dataset
    for name, data in [
        (DATASET_NAME, GOLDEN_DATASET),
        (RAG_DATASET_NAME, RAG_GOLDEN_DATASET),
    ]:
        try:
            existing = client.read_dataset(dataset_name=name)
            print(
                f"Dataset '{name}' already exists (id={existing.id}). Deleting and recreating."
            )
            client.delete_dataset(dataset_id=existing.id)
        except Exception:
            pass

        dataset = client.create_dataset(
            dataset_name=name,
            description=f"Golden dataset for Wanderlisted evaluation ({name})",
        )
        client.create_examples(
            inputs=[tc["inputs"] for tc in data],
            outputs=[tc["outputs"] for tc in data],
            dataset_id=dataset.id,
        )
        print(f"  Uploaded {len(data)} examples to '{name}' (id={dataset.id})")

    return "done"


async def wanderlisted_target(inputs: dict) -> dict:
    """Run the full Wanderlisted graph and return structured results for evaluation."""
    from langchain_core.messages import HumanMessage
    from src.agent.stage4_graph import create_multiagent_travel_graph
    from langgraph.checkpoint.memory import InMemorySaver

    graph = create_multiagent_travel_graph(checkpointer=InMemorySaver())

    try:
        result = await asyncio.wait_for(
            graph.ainvoke(
                {"messages": [HumanMessage(content=inputs["question"])]},
                config={"configurable": {"thread_id": f"eval-{uuid.uuid4()}"}},
            ),
            timeout=180,
        )
    except asyncio.TimeoutError:
        return {"output": "TIMEOUT", "destinations_covered": [], "agents_routed": []}
    except Exception as e:
        return {
            "output": f"ERROR: {e}",
            "destinations_covered": [],
            "agents_routed": [],
        }

    components = result.get("itinerary_components", {})
    return {
        "output": result["messages"][-1].content,
        "destinations_covered": result.get("destinations", []),
        "agents_routed": components.get("routing", []),
        "budget_structured": components.get("budget_structured", {}),
        "tools_called": components.get("tools_called", []),
    }


async def rag_target(inputs: dict) -> dict:
    """Run the RAG pipeline only and return contexts + response for RAG evaluation."""
    from src.tools.destination_rag import search_destination_guides
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage

    question = inputs["question"]

    # Retrieve
    try:
        rag_result = await search_destination_guides.ainvoke({"query": question})
    except Exception as e:
        return {"output": f"ERROR: {e}", "retrieved_contexts": []}

    # Parse contexts
    contexts = []
    if isinstance(rag_result, str):
        for chunk in rag_result.split("\n\n"):
            chunk = chunk.strip()
            if chunk and len(chunk) > 20:
                contexts.append(chunk)

    # Generate
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    response = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "You are a travel assistant. Answer the question using ONLY the "
                    "provided context. If the context doesn't contain the answer, say so."
                )
            ),
            HumanMessage(content=f"Context:\n{rag_result}\n\nQuestion: {question}"),
        ]
    )

    return {
        "output": response.content,
        "retrieved_contexts": contexts if contexts else [str(rag_result)[:500]],
    }


def run_evaluation(
    prefix: str = "wanderlisted-eval",
    use_llm_judge: bool = True,
    mode: str = "all",
):
    """Run evaluation experiments against the golden datasets.

    Args:
        mode: "agent" (agent evaluators only), "rag" (RAG evaluators only), or "all"
    """
    metadata = {
        "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        "prompt_version": "v1",
    }

    if mode in ("agent", "all"):
        agent_evaluators = [
            correct_tool_routing,
            valid_routing_decision,
            budget_completeness,
            correct_destination,
            non_empty_response,
            handbook_section_completeness,
        ]
        if use_llm_judge:
            agent_evaluators.append(travel_quality_judge)

        print(f"Running AGENT evaluation with {len(agent_evaluators)} evaluators...")
        evaluate(
            wanderlisted_target,
            data=DATASET_NAME,
            evaluators=agent_evaluators,
            experiment_prefix=f"{prefix}-agent",
            max_concurrency=2,
            metadata=metadata,
        )

    if mode in ("rag", "all"):
        rag_evaluators = [
            context_precision,
            context_recall,
            context_entity_recall,
            noise_sensitivity,
            response_relevancy,
            faithfulness,
        ]
        print(f"Running RAG evaluation with {len(rag_evaluators)} evaluators...")
        evaluate(
            rag_target,
            data=RAG_DATASET_NAME,
            evaluators=rag_evaluators,
            experiment_prefix=f"{prefix}-rag",
            max_concurrency=2,
            metadata=metadata,
        )

    print("\nDone. View results at https://smith.langchain.com")


def main():
    parser = argparse.ArgumentParser(description="Wanderlisted Agent Evaluation")
    parser.add_argument(
        "--upload-dataset",
        action="store_true",
        help="Upload golden datasets to LangSmith",
    )
    parser.add_argument("--run", action="store_true", help="Run evaluation experiments")
    parser.add_argument(
        "--prefix", default="wanderlisted-eval", help="Experiment prefix"
    )
    parser.add_argument(
        "--mode", choices=["agent", "rag", "all"], default="all", help="Evaluation mode"
    )
    parser.add_argument(
        "--no-llm-judge", action="store_true", help="Disable LLM-as-Judge evaluator"
    )
    args = parser.parse_args()

    if args.upload_dataset:
        upload_dataset()

    if args.run:
        run_evaluation(
            prefix=args.prefix,
            use_llm_judge=not args.no_llm_judge,
            mode=args.mode,
        )

    if not args.upload_dataset and not args.run:
        parser.print_help()


if __name__ == "__main__":
    main()
