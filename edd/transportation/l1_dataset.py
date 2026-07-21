"""Golden route-decision dataset for TransportationAgent.

Each item uses the component EDD schema shared by the completed agents:
``name``, ``tags``, ``query``, and a ground-truth ``expected`` mapping. Every
expected route preserves the user-requested origin, destination, mode, optional
waypoints, and whether actionable steps are required. Location sets represent
valid equivalent address or airport-code forms; they are not agent output.
"""

from __future__ import annotations

DATASET_VERSION = "1.0.0"
DATASET_SIZE = 40

DATASET: list[dict] = [
    {
        "name": "rome-fco-to-hotel-transit",
        "tags": ["airport-transfer", "transit", "baseline"],
        "query": "How do I get by public transport from Fiumicino Airport to Hotel Artemide in Rome?",
        "expected": {
            "routes": [
                {
                    "origin": {"FCO", "FCO Airport", "Fiumicino Airport"},
                    "destination": {"Hotel Artemide", "Hotel Artemide Rome"},
                    "travel_mode": "TRANSIT",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "london-heathrow-to-soho-transit",
        "tags": ["airport-transfer", "transit"],
        "query": "Give me transit directions from Heathrow Airport to The Resident Soho in London.",
        "expected": {
            "routes": [
                {
                    "origin": {"Heathrow Airport", "LHR", "LHR Airport"},
                    "destination": {"The Resident Soho", "The Resident Soho London"},
                    "travel_mode": "TRANSIT",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "paris-cdg-to-saint-germain-transit",
        "tags": ["airport-transfer", "transit", "metro-code"],
        "query": "What public transport should I take from Charles de Gaulle Airport to Hotel Le Six in Saint-Germain-des-Pres?",
        "expected": {
            "routes": [
                {
                    "origin": {"Charles de Gaulle Airport", "CDG", "CDG Airport"},
                    "destination": {"Hotel Le Six", "Hotel Le Six Paris"},
                    "travel_mode": "TRANSIT",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "tokyo-haneda-to-shibuya-transit",
        "tags": ["airport-transfer", "transit"],
        "query": "Find a transit route from Haneda Airport to Shibuya Crossing in Tokyo.",
        "expected": {
            "routes": [
                {
                    "origin": {"Haneda Airport", "HND", "HND Airport"},
                    "destination": {"Shibuya Crossing", "Shibuya Station"},
                    "travel_mode": "TRANSIT",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "new-york-jfk-to-midtown-transit",
        "tags": ["airport-transfer", "transit"],
        "query": "I need public transit directions from JFK Airport to Bryant Park in Midtown Manhattan.",
        "expected": {
            "routes": [
                {
                    "origin": {"JFK", "JFK Airport", "John F Kennedy Airport"},
                    "destination": {"Bryant Park", "Bryant Park Manhattan"},
                    "travel_mode": "TRANSIT",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "barcelona-airport-to-sagrada-transit",
        "tags": ["airport-transfer", "transit"],
        "query": "How can I get by train or metro from Barcelona El Prat Airport to Sagrada Familia?",
        "expected": {
            "routes": [
                {
                    "origin": {"Barcelona El Prat Airport", "BCN Airport", "BCN"},
                    "destination": {
                        "Sagrada Familia",
                        "Basilica de la Sagrada Familia",
                    },
                    "travel_mode": "TRANSIT",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "amsterdam-schiphol-to-jordaan-transit",
        "tags": ["airport-transfer", "transit"],
        "query": "Give transit directions from Schiphol Airport to the Jordaan in Amsterdam.",
        "expected": {
            "routes": [
                {
                    "origin": {"Schiphol Airport", "AMS Airport", "AMS"},
                    "destination": {"Jordaan", "Jordaan Amsterdam"},
                    "travel_mode": "TRANSIT",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "lisbon-airport-to-alfama-transit",
        "tags": ["airport-transfer", "transit"],
        "query": "What is the public transport route from Lisbon Airport to Alfama?",
        "expected": {
            "routes": [
                {
                    "origin": {"Lisbon Airport", "LIS Airport", "LIS"},
                    "destination": {"Alfama", "Alfama Lisbon"},
                    "travel_mode": "TRANSIT",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "venice-airport-to-san-marco-transit",
        "tags": ["airport-transfer", "transit"],
        "query": "Plan the public transport trip from Venice Marco Polo Airport to Piazza San Marco.",
        "expected": {
            "routes": [
                {
                    "origin": {"Venice Marco Polo Airport", "VCE Airport", "VCE"},
                    "destination": {"Piazza San Marco", "St Marks Square Venice"},
                    "travel_mode": "TRANSIT",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "athens-airport-to-acropolis-transit",
        "tags": ["airport-transfer", "transit"],
        "query": "How do I take public transport from Athens International Airport to the Acropolis Museum?",
        "expected": {
            "routes": [
                {
                    "origin": {"Athens International Airport", "ATH Airport", "ATH"},
                    "destination": {"Acropolis Museum", "Acropolis Museum Athens"},
                    "travel_mode": "TRANSIT",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "rome-hotel-to-colosseum-walk",
        "tags": ["walk", "short-route"],
        "query": "Give me walking directions from Hotel Artemide in Rome to the Colosseum.",
        "expected": {
            "routes": [
                {
                    "origin": {"Hotel Artemide", "Hotel Artemide Rome"},
                    "destination": {"Colosseum", "Colosseo Rome"},
                    "travel_mode": "WALK",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "paris-louvre-to-notre-dame-walk",
        "tags": ["walk", "short-route"],
        "query": "Walk me from the Louvre Museum to Notre Dame Cathedral in Paris.",
        "expected": {
            "routes": [
                {
                    "origin": {"Louvre Museum", "Louvre"},
                    "destination": {"Notre Dame Cathedral", "Notre Dame Paris"},
                    "travel_mode": "WALK",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "kyoto-gion-to-kiyomizu-walk",
        "tags": ["walk", "short-route"],
        "query": "What is the walking route from Gion Corner to Kiyomizu dera in Kyoto?",
        "expected": {
            "routes": [
                {
                    "origin": {"Gion Corner", "Gion Corner Kyoto"},
                    "destination": {"Kiyomizu dera", "Kiyomizu Temple"},
                    "travel_mode": "WALK",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "amsterdam-anne-frank-to-rijksmuseum-bicycle",
        "tags": ["bicycle", "city-route"],
        "query": "Find a bike route from the Anne Frank House to the Rijksmuseum in Amsterdam.",
        "expected": {
            "routes": [
                {
                    "origin": {"Anne Frank House", "Anne Frank Huis"},
                    "destination": {"Rijksmuseum", "Rijksmuseum Amsterdam"},
                    "travel_mode": "BICYCLE",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "copenhagen-nyhavn-to-little-mermaid-bicycle",
        "tags": ["bicycle", "city-route"],
        "query": "Can you give me cycling directions from Nyhavn to The Little Mermaid in Copenhagen?",
        "expected": {
            "routes": [
                {
                    "origin": {"Nyhavn", "Nyhavn Copenhagen"},
                    "destination": {"The Little Mermaid", "Little Mermaid Copenhagen"},
                    "travel_mode": "BICYCLE",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "rome-to-pompeii-drive",
        "tags": ["drive", "intercity"],
        "query": "I am driving from Hotel Artemide in Rome to the Pompeii Archaeological Park. Route me there.",
        "expected": {
            "routes": [
                {
                    "origin": {"Hotel Artemide", "Hotel Artemide Rome"},
                    "destination": {"Pompeii Archaeological Park", "Pompeii"},
                    "travel_mode": "DRIVE",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "los-angeles-to-santa-monica-drive",
        "tags": ["drive", "city-route"],
        "query": "Give me driving directions from the Hollywood Roosevelt Hotel to Santa Monica Pier.",
        "expected": {
            "routes": [
                {
                    "origin": {
                        "Hollywood Roosevelt Hotel",
                        "Hollywood Roosevelt Hotel Los Angeles",
                    },
                    "destination": {
                        "Santa Monica Pier",
                        "Santa Monica Pier California",
                    },
                    "travel_mode": "DRIVE",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "bangkok-sukhumvit-to-grand-palace-drive",
        "tags": ["drive", "city-route"],
        "query": "Please calculate a car route from Sukhumvit to the Grand Palace in Bangkok.",
        "expected": {
            "routes": [
                {
                    "origin": {"Sukhumvit", "Sukhumvit Bangkok"},
                    "destination": {"Grand Palace", "Grand Palace Bangkok"},
                    "travel_mode": "DRIVE",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "hanoi-old-quarter-to-temple-two-wheeler",
        "tags": ["two-wheeler", "city-route"],
        "query": "Find a scooter route from Hanoi Old Quarter to the Temple of Literature.",
        "expected": {
            "routes": [
                {
                    "origin": {"Hanoi Old Quarter", "Old Quarter Hanoi"},
                    "destination": {
                        "Temple of Literature",
                        "Temple of Literature Hanoi",
                    },
                    "travel_mode": "TWO_WHEELER",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "bali-canggu-to-uluwatu-two-wheeler",
        "tags": ["two-wheeler", "intercity"],
        "query": "I will be on a motorbike. Route me from Canggu to Uluwatu Temple in Bali.",
        "expected": {
            "routes": [
                {
                    "origin": {"Canggu", "Canggu Bali"},
                    "destination": {"Uluwatu Temple", "Pura Luhur Uluwatu"},
                    "travel_mode": "TWO_WHEELER",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "rome-hotel-attraction-comparison",
        "tags": ["comparison", "transit", "multi-route"],
        "query": "Compare public transport from Hotel Artemide in Rome to the Colosseum and to Vatican Museums.",
        "expected": {
            "min_route_calls": 2,
            "routes": [
                {
                    "origin": {"Hotel Artemide", "Hotel Artemide Rome"},
                    "destination": {"Colosseum", "Colosseo Rome"},
                    "travel_mode": "TRANSIT",
                    "include_steps": True,
                },
                {
                    "origin": {"Hotel Artemide", "Hotel Artemide Rome"},
                    "destination": {"Vatican Museums", "Musei Vaticani"},
                    "travel_mode": "TRANSIT",
                    "include_steps": True,
                },
            ],
        },
    },
    {
        "name": "london-hotel-attraction-comparison",
        "tags": ["comparison", "transit", "multi-route"],
        "query": "Compare the transit trip from The Resident Soho to the British Museum and the Tower of London.",
        "expected": {
            "min_route_calls": 2,
            "routes": [
                {
                    "origin": {"The Resident Soho", "The Resident Soho London"},
                    "destination": {"British Museum", "The British Museum"},
                    "travel_mode": "TRANSIT",
                    "include_steps": True,
                },
                {
                    "origin": {"The Resident Soho", "The Resident Soho London"},
                    "destination": {"Tower of London", "Tower of London London"},
                    "travel_mode": "TRANSIT",
                    "include_steps": True,
                },
            ],
        },
    },
    {
        "name": "rome-walking-multi-stop",
        "tags": ["waypoints", "walk", "multi-stop"],
        "query": "Plan a walking route from Hotel Artemide to Trastevere via Piazza Navona and the Pantheon.",
        "expected": {
            "routes": [
                {
                    "origin": {"Hotel Artemide", "Hotel Artemide Rome"},
                    "destination": {"Trastevere", "Trastevere Rome"},
                    "travel_mode": "WALK",
                    "waypoints": [{"Piazza Navona"}, {"Pantheon"}],
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "paris-driving-multi-stop",
        "tags": ["waypoints", "drive", "multi-stop"],
        "query": "Drive from Gare du Nord to the Eiffel Tower via the Louvre and Champs Elysees.",
        "expected": {
            "routes": [
                {
                    "origin": {"Gare du Nord", "Paris Gare du Nord"},
                    "destination": {"Eiffel Tower", "Tour Eiffel"},
                    "travel_mode": "DRIVE",
                    "waypoints": [
                        {"Louvre Museum", "Louvre"},
                        {"Champs Elysees", "Avenue des Champs Elysees"},
                    ],
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "amsterdam-cycling-multi-stop",
        "tags": ["waypoints", "bicycle", "multi-stop"],
        "query": "Create a bike route from Hotel Estherea to the Rijksmuseum via the Anne Frank House and Vondelpark.",
        "expected": {
            "routes": [
                {
                    "origin": {"Hotel Estherea", "Hotel Estherea Amsterdam"},
                    "destination": {"Rijksmuseum", "Rijksmuseum Amsterdam"},
                    "travel_mode": "BICYCLE",
                    "waypoints": [
                        {"Anne Frank House", "Anne Frank Huis"},
                        {"Vondelpark"},
                    ],
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "berlin-german-ubahn-transit",
        "tags": ["multilingual", "transit"],
        "query": "Wie komme ich mit der U-Bahn vom Berliner Hauptbahnhof zum Brandenburger Tor?",
        "expected": {
            "routes": [
                {
                    "origin": {"Berlin Hauptbahnhof", "Berliner Hauptbahnhof"},
                    "destination": {"Brandenburger Tor", "Brandenburg Gate"},
                    "travel_mode": "TRANSIT",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "madrid-spanish-walking-route",
        "tags": ["multilingual", "walk"],
        "query": "Dame indicaciones a pie desde la Puerta del Sol hasta el Museo del Prado en Madrid.",
        "expected": {
            "routes": [
                {
                    "origin": {"Puerta del Sol", "Puerta del Sol Madrid"},
                    "destination": {"Museo del Prado", "Prado Museum"},
                    "travel_mode": "WALK",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "paris-french-cycling-route",
        "tags": ["multilingual", "bicycle"],
        "query": "Je veux un itineraire a velo de Montmartre au Canal Saint Martin a Paris.",
        "expected": {
            "routes": [
                {
                    "origin": {"Montmartre", "Montmartre Paris"},
                    "destination": {"Canal Saint Martin", "Canal St Martin"},
                    "travel_mode": "BICYCLE",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "florence-italian-driving-route",
        "tags": ["multilingual", "drive"],
        "query": "Dammi il percorso in auto da Firenze Santa Maria Novella a Piazzale Michelangelo.",
        "expected": {
            "routes": [
                {
                    "origin": {
                        "Firenze Santa Maria Novella",
                        "Florence Santa Maria Novella",
                    },
                    "destination": {
                        "Piazzale Michelangelo",
                        "Piazzale Michelangelo Florence",
                    },
                    "travel_mode": "DRIVE",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "rome-destination-correction",
        "tags": ["correction", "context-resistance", "walk"],
        "query": "Walk from Hotel Artemide to the Louvre - sorry, I mean the Colosseum in Rome, not Paris.",
        "expected": {
            "routes": [
                {
                    "origin": {"Hotel Artemide", "Hotel Artemide Rome"},
                    "destination": {"Colosseum", "Colosseo Rome"},
                    "travel_mode": "WALK",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "tokyo-mode-correction",
        "tags": ["correction", "context-resistance", "transit"],
        "query": "Route me from Tokyo Station to Senso ji by taxi - correction, use public transit instead.",
        "expected": {
            "routes": [
                {
                    "origin": {"Tokyo Station", "Tokyo Eki"},
                    "destination": {"Senso ji", "Sensoji Temple"},
                    "travel_mode": "TRANSIT",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "london-origin-correction",
        "tags": ["correction", "context-resistance", "transit"],
        "query": "I need the Tube from Paddington to Tate Modern; actually start at King's Cross St Pancras, not Paddington.",
        "expected": {
            "routes": [
                {
                    "origin": {"Kings Cross St Pancras", "King's Cross St Pancras"},
                    "destination": {"Tate Modern", "Tate Modern London"},
                    "travel_mode": "TRANSIT",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "portland-maine-airport-disambiguation",
        "tags": ["disambiguation", "airport-transfer", "drive"],
        "query": "Drive from Portland International Jetport in Maine, not Portland Oregon, to Old Port.",
        "expected": {
            "routes": [
                {
                    "origin": {"Portland International Jetport", "PWM Airport", "PWM"},
                    "destination": {"Old Port Portland Maine", "Old Port Maine"},
                    "travel_mode": "DRIVE",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "san-jose-costa-rica-disambiguation",
        "tags": ["disambiguation", "airport-transfer", "transit"],
        "query": "Use public transport from Juan Santamaria Airport to Hotel Grano de Oro in San Jose, Costa Rica, not California.",
        "expected": {
            "routes": [
                {
                    "origin": {"Juan Santamaria Airport", "SJO Airport", "SJO"},
                    "destination": {
                        "Hotel Grano de Oro",
                        "Hotel Grano de Oro San Jose",
                    },
                    "travel_mode": "TRANSIT",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "london-ontario-disambiguation",
        "tags": ["disambiguation", "walk"],
        "query": "Give a walking route from Museum London in Ontario, Canada, not London England, to Victoria Park.",
        "expected": {
            "routes": [
                {
                    "origin": {"Museum London", "Museum London Ontario"},
                    "destination": {
                        "Victoria Park London Ontario",
                        "Victoria Park Ontario",
                    },
                    "travel_mode": "WALK",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "rome-hotel-to-fco-transit",
        "tags": ["airport-transfer", "transit", "outbound"],
        "query": "What public transport route gets me from Hotel Artemide in Rome back to Fiumicino Airport?",
        "expected": {
            "routes": [
                {
                    "origin": {"Hotel Artemide", "Hotel Artemide Rome"},
                    "destination": {"Fiumicino Airport", "FCO Airport", "FCO"},
                    "travel_mode": "TRANSIT",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "paris-gare-du-nord-to-eiffel-transit",
        "tags": ["transit", "city-route"],
        "query": "Give Metro directions from Gare du Nord to the Eiffel Tower in Paris.",
        "expected": {
            "routes": [
                {
                    "origin": {"Gare du Nord", "Paris Gare du Nord"},
                    "destination": {"Eiffel Tower", "Tour Eiffel"},
                    "travel_mode": "TRANSIT",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "barcelona-accessible-transit-route",
        "tags": ["accessibility", "transit", "city-route"],
        "query": "Find public transit from Hotel Jazz Barcelona to Museu Picasso; I use a wheelchair, so include the route steps.",
        "expected": {
            "routes": [
                {
                    "origin": {"Hotel Jazz Barcelona", "Hotel Jazz"},
                    "destination": {"Museu Picasso", "Picasso Museum Barcelona"},
                    "travel_mode": "TRANSIT",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "sydney-circular-quay-to-bondi-transit",
        "tags": ["transit", "city-route"],
        "query": "How do I get on public transport from Circular Quay to Bondi Beach in Sydney?",
        "expected": {
            "routes": [
                {
                    "origin": {"Circular Quay", "Circular Quay Sydney"},
                    "destination": {"Bondi Beach", "Bondi Beach Sydney"},
                    "travel_mode": "TRANSIT",
                    "include_steps": True,
                }
            ]
        },
    },
    {
        "name": "cape-town-waterfront-to-table-mountain-drive",
        "tags": ["drive", "city-route"],
        "query": "I have a rental car. Drive me from the V&A Waterfront to the Table Mountain Aerial Cableway in Cape Town.",
        "expected": {
            "routes": [
                {
                    "origin": {"V&A Waterfront", "VA Waterfront Cape Town"},
                    "destination": {
                        "Table Mountain Aerial Cableway",
                        "Table Mountain Cableway",
                    },
                    "travel_mode": "DRIVE",
                    "include_steps": True,
                }
            ]
        },
    },
]
