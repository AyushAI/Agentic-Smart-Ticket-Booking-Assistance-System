import os
import logging
from fastmcp import FastMCP
from amadeus import Client, ResponseError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

mcp = FastMCP("travel-tools")

amadeus = Client(
    client_id=os.getenv("AMADEUS_API_KEY"),
    client_secret=os.getenv("AMADEUS_API_SECRET"),
)


@mcp.tool()
def search_flights(origin: str, destination: str, date: str) -> list[dict]:
    """Search real flights via Amadeus API and return top 5 cheapest offers."""
    try:
        response = amadeus.shopping.flight_offers_search.get(
            originLocationCode=origin,
            destinationLocationCode=destination,
            departureDate=date,
            adults=1,
            currencyCode="INR",     #specify currency so prices are in INR, not USD
            max=5,                  #FIX: cap at API level, not just in slicing
        )

        # Airline code → full name mapping for display
        AIRLINE_NAMES = {
            "AI": "Air India", "6E": "IndiGo", "SG": "SpiceJet",
            "UK": "Vistara", "G8": "Go First", "QP": "Akasa Air",
            "IX": "Air India Express", "I5": "AirAsia India",
        }

        flights = []
        for offer in response.data:
            try:
                segment    = offer["itineraries"][0]["segments"][0]
                duration   = offer["itineraries"][0]["duration"]        # e.g. "PT2H30M"
                carrier    = segment.get("carrierCode", "")             # e.g. "6E"
                flight_num = segment.get("number", "")                  # e.g. "101"
                operator   = AIRLINE_NAMES.get(carrier, carrier)        # e.g. "IndiGo"
                name       = f"{operator} {carrier}{flight_num}"        # e.g. "IndiGo 6E101"
                departure  = segment["departure"]["at"][11:16]          # "HH:MM" from ISO string
                arrival    = segment["arrival"]["at"][11:16]            # "HH:MM"
            except (KeyError, IndexError):
                duration  = "N/A"
                name      = "Unknown Flight"
                departure = "N/A"
                arrival   = "N/A"

            flights.append(
                {
                    "mode": "flight",
                    "operator": name,
                    "departure": departure,
                    "arrival": arrival,
                    "price": float(offer["price"]["total"]),
                    "currency": offer["price"].get("currency", "INR"),
                    "time": duration,
                }
            )

        logger.info("Flight search returned %d results", len(flights))
        return flights

    except ResponseError as e:
        
        logger.error("Amadeus flight search error: %s", e)
        return []
    except Exception as e:
        logger.error("Unexpected flight search error: %s", e)
        return []


@mcp.tool()
def search_trains(origin: str, destination: str, date: str) -> list[dict]:
    """
    Simulated train results.
    """
    
    return [
        {"mode": "train", "operator": "Rajdhani Express", "departure": "06:00", "arrival": "16:00", "price": 800, "currency": "INR", "time": "10h"},
        {"mode": "train", "operator": "Shatabdi Express", "departure": "07:00", "arrival": "16:00", "price": 950, "currency": "INR", "time": "9h"},
    ]


@mcp.tool()
def search_buses(origin: str, destination: str, date: str) -> list[dict]:
    """
    Simulated bus results.
    """
    return [
        {"mode": "bus", "operator": "RedBus Travels", "departure": "20:00", "arrival": "08:00", "price": 700, "currency": "INR", "time": "12h"},
        {"mode": "bus", "operator": "AbhiBus Express", "departure": "21:00", "arrival": "08:00", "price": 650, "currency": "INR", "time": "11h"},
    ]


if __name__ == "__main__":
    mcp.run()