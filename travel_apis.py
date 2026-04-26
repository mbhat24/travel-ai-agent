"""
Travel API Integrations Module
Provides integrations with external travel services:
- Weather API (OpenWeatherMap)
- Amadeus (Flight/Hotel search)
- Currency Exchange
- Travel advisories
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import urllib.request
import urllib.error
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# API Keys from environment
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
AMADEUS_API_KEY = os.getenv("AMADEUS_API_KEY", "")
AMADEUS_SECRET = os.getenv("AMADEUS_SECRET", "")
EXCHANGE_RATE_API_KEY = os.getenv("EXCHANGE_RATE_API_KEY", "")

class WeatherAPI:
    """OpenWeatherMap API integration"""
    
    BASE_URL = "https://api.openweathermap.org/data/2.5"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or OPENWEATHER_API_KEY
    
    def is_available(self) -> bool:
        """Check if API key is configured"""
        return bool(self.api_key)
    
    def get_current_weather(self, city: str, country: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get current weather for a destination"""
        if not self.is_available():
            return None
        
        try:
            query = f"{city},{country}" if country else city
            params = {
                "q": query,
                "appid": self.api_key,
                "units": "metric"
            }
            url = f"{self.BASE_URL}/weather?{urlencode(params)}"
            
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
            
            return {
                "temperature": data["main"]["temp"],
                "feels_like": data["main"]["feels_like"],
                "humidity": data["main"]["humidity"],
                "description": data["weather"][0]["description"],
                "icon": data["weather"][0]["icon"],
                "wind_speed": data["wind"]["speed"],
                "city": data["name"],
                "country": data["sys"]["country"]
            }
        except Exception as e:
            logger.warning(f"Weather API error: {e}")
            return None
    
    def get_forecast(self, city: str, country: Optional[str] = None, days: int = 5) -> Optional[List[Dict[str, Any]]]:
        """Get weather forecast for a destination"""
        if not self.is_available():
            return None
        
        try:
            query = f"{city},{country}" if country else city
            params = {
                "q": query,
                "appid": self.api_key,
                "units": "metric",
                "cnt": days * 8  # API returns 3-hour intervals
            }
            url = f"{self.BASE_URL}/forecast?{urlencode(params)}"
            
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
            
            # Group by day
            daily_forecasts = []
            current_day = None
            day_data = []
            
            for item in data.get("list", []):
                date = datetime.fromtimestamp(item["dt"]).strftime("%Y-%m-%d")
                
                if date != current_day:
                    if day_data:
                        daily_forecasts.append(self._aggregate_day_forecast(current_day, day_data))
                    current_day = date
                    day_data = []
                
                day_data.append(item)
            
            if day_data:
                daily_forecasts.append(self._aggregate_day_forecast(current_day, day_data))
            
            return daily_forecasts[:days]
            
        except Exception as e:
            logger.warning(f"Weather forecast API error: {e}")
            return None
    
    def _aggregate_day_forecast(self, date: str, items: List[Dict]) -> Dict[str, Any]:
        """Aggregate hourly forecasts into daily summary"""
        temps = [item["main"]["temp"] for item in items]
        descriptions = [item["weather"][0]["description"] for item in items]
        
        # Get most common description
        description = max(set(descriptions), key=descriptions.count)
        
        return {
            "date": date,
            "temp_min": min(temps),
            "temp_max": max(temps),
            "temp_avg": sum(temps) / len(temps),
            "description": description,
            "icon": items[0]["weather"][0]["icon"]
        }


class AmadeusAPI:
    """Amadeus Travel API integration for flights and hotels"""
    
    BASE_URL = "https://api.amadeus.com/v2"
    TEST_URL = "https://api.amadeus.com/v2"
    
    def __init__(self, api_key: Optional[str] = None, secret: Optional[str] = None):
        self.api_key = api_key or AMADEUS_API_KEY
        self.secret = secret or AMADEUS_SECRET
        self._access_token = None
        self._token_expires = None
    
    def is_available(self) -> bool:
        """Check if API credentials are configured"""
        return bool(self.api_key and self.secret)
    
    def _get_access_token(self) -> Optional[str]:
        """Get or refresh Amadeus access token"""
        if self._access_token and self._token_expires and datetime.now() < self._token_expires:
            return self._access_token
        
        try:
            import urllib.request
            import base64
            
            credentials = base64.b64encode(f"{self.api_key}:{self.secret}".encode()).decode()
            
            req = urllib.request.Request(
                "https://api.amadeus.com/v1/security/oauth2/token",
                data=b"grant_type=client_credentials",
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
            
            self._access_token = data["access_token"]
            expires_in = data.get("expires_in", 1800)
            self._token_expires = datetime.now() + timedelta(seconds=expires_in - 60)
            
            return self._access_token
            
        except Exception as e:
            logger.error(f"Amadeus authentication failed: {e}")
            return None
    
    def search_flights(self, origin: str, destination: str, 
                       departure_date: str, return_date: Optional[str] = None,
                       adults: int = 1) -> Optional[List[Dict[str, Any]]]:
        """Search for flights"""
        token = self._get_access_token()
        if not token:
            return None
        
        try:
            params = {
                "originLocationCode": origin,
                "destinationLocationCode": destination,
                "departureDate": departure_date,
                "adults": adults,
                "max": 5
            }
            if return_date:
                params["returnDate"] = return_date
            
            url = f"{self.BASE_URL}/shopping/flight-offers?{urlencode(params)}"
            
            req = urllib.request.Request(
                url,
                headers={"Authorization": f"Bearer {token}"},
                method="GET"
            )
            
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode())
            
            flights = []
            for offer in data.get("data", []):
                price = offer.get("price", {})
                itineraries = offer.get("itineraries", [])
                
                flight_info = {
                    "id": offer.get("id"),
                    "price": float(price.get("total", 0)),
                    "currency": price.get("currency", "USD"),
                    "outbound": self._parse_itinerary(itineraries[0]) if itineraries else None,
                    "return": self._parse_itinerary(itineraries[1]) if len(itineraries) > 1 else None
                }
                flights.append(flight_info)
            
            return flights
            
        except Exception as e:
            logger.warning(f"Flight search error: {e}")
            return None
    
    def _parse_itinerary(self, itinerary: Dict) -> Dict[str, Any]:
        """Parse flight itinerary"""
        segments = itinerary.get("segments", [])
        if not segments:
            return None
        
        first_segment = segments[0]
        last_segment = segments[-1]
        
        return {
            "departure": {
                "airport": first_segment.get("departure", {}).get("iataCode"),
                "time": first_segment.get("departure", {}).get("at"),
                "terminal": first_segment.get("departure", {}).get("terminal")
            },
            "arrival": {
                "airport": last_segment.get("arrival", {}).get("iataCode"),
                "time": last_segment.get("arrival", {}).get("at"),
                "terminal": last_segment.get("arrival", {}).get("terminal")
            },
            "duration": itinerary.get("duration"),
            "stops": len(segments) - 1,
            "carrier": first_segment.get("carrierCode")
        }
    
    def search_hotels(self, city_code: str, check_in: str, check_out: str,
                      adults: int = 1) -> Optional[List[Dict[str, Any]]]:
        """Search for hotels"""
        token = self._get_access_token()
        if not token:
            return None
        
        try:
            params = {
                "cityCode": city_code,
                "checkInDate": check_in,
                "checkOutDate": check_out,
                "adults": adults,
                "max": 5
            }
            
            url = f"{self.BASE_URL}/shopping/hotel-offers?{urlencode(params)}"
            
            req = urllib.request.Request(
                url,
                headers={"Authorization": f"Bearer {token}"},
                method="GET"
            )
            
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode())
            
            hotels = []
            for offer in data.get("data", []):
                hotel = offer.get("hotel", {})
                price = offer.get("offers", [{}])[0].get("price", {})
                
                hotel_info = {
                    "id": hotel.get("hotelId"),
                    "name": hotel.get("name"),
                    "rating": hotel.get("rating"),
                    "price": float(price.get("total", 0)),
                    "currency": price.get("currency", "USD"),
                    "address": hotel.get("address", {})
                }
                hotels.append(hotel_info)
            
            return hotels
            
        except Exception as e:
            logger.warning(f"Hotel search error: {e}")
            return None


class CurrencyAPI:
    """Currency exchange rates API"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or EXCHANGE_RATE_API_KEY
    
    def get_exchange_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Get exchange rate between two currencies"""
        try:
            # Using a free API (exchangerate-api.com)
            url = f"https://api.exchangerate-api.com/v4/latest/{from_currency.upper()}"
            
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
            
            rates = data.get("rates", {})
            return rates.get(to_currency.upper())
            
        except Exception as e:
            logger.warning(f"Exchange rate API error: {e}")
            return None
    
    def convert_currency(self, amount: float, from_currency: str, to_currency: str) -> Optional[float]:
        """Convert amount from one currency to another"""
        rate = self.get_exchange_rate(from_currency, to_currency)
        if rate:
            return amount * rate
        return None


class TravelAdvisoryAPI:
    """Travel advisory information"""
    
    # Country code to advisory level mapping (simplified)
    ADVISORY_DATA = {
        "US": {"level": 1, "advice": "Exercise normal precautions"},
        "CA": {"level": 1, "advice": "Exercise normal precautions"},
        "GB": {"level": 2, "advice": "Exercise increased caution"},
        "FR": {"level": 2, "advice": "Exercise increased caution"},
        "DE": {"level": 2, "advice": "Exercise increased caution"},
        "IT": {"level": 2, "advice": "Exercise increased caution"},
        "ES": {"level": 2, "advice": "Exercise increased caution"},
        "JP": {"level": 1, "advice": "Exercise normal precautions"},
        "AU": {"level": 1, "advice": "Exercise normal precautions"},
        "IN": {"level": 2, "advice": "Exercise increased caution"},
        "CN": {"level": 3, "advice": "Reconsider travel"},
        "MX": {"level": 3, "advice": "Reconsider travel"},
        "BR": {"level": 2, "advice": "Exercise increased caution"},
        "RU": {"level": 4, "advice": "Do not travel"},
        "UA": {"level": 4, "advice": "Do not travel"},
    }
    
    def get_advisory(self, country_code: str) -> Dict[str, Any]:
        """Get travel advisory for a country"""
        country_code = country_code.upper()
        advisory = self.ADVISORY_DATA.get(country_code, {
            "level": 1,
            "advice": "Exercise normal precautions - no specific advisory available"
        })
        
        level_descriptions = {
            1: "Level 1 - Exercise normal precautions",
            2: "Level 2 - Exercise increased caution",
            3: "Level 3 - Reconsider travel",
            4: "Level 4 - Do not travel"
        }
        
        return {
            "country": country_code,
            "level": advisory["level"],
            "level_description": level_descriptions.get(advisory["level"], "Unknown"),
            "advice": advisory["advice"],
            "source": "Travel AI Agent Advisory System"
        }


# Global API instances
weather_api = WeatherAPI()
amadeus_api = AmadeusAPI()
currency_api = CurrencyAPI()
advisory_api = TravelAdvisoryAPI()


def enrich_travel_plan(destination: str, country_code: Optional[str] = None,
                       start_date: Optional[str] = None, budget: Optional[float] = None,
                       home_currency: str = "USD") -> Dict[str, Any]:
    """Enrich travel plan with real-time data from APIs"""
    enrichment = {
        "weather": None,
        "advisory": None,
        "local_budget": None,
        "flights": None,
        "hotels": None
    }
    
    # Get weather
    weather = weather_api.get_current_weather(destination, country_code)
    if weather:
        enrichment["weather"] = weather
        
        # Get forecast if start_date provided
        if start_date:
            forecast = weather_api.get_forecast(destination, country_code, days=5)
            if forecast:
                enrichment["weather_forecast"] = forecast
    
    # Get travel advisory
    if country_code:
        enrichment["advisory"] = advisory_api.get_advisory(country_code)
    
    # Convert budget to local currency (simplified - would need country to currency mapping)
    if budget:
        # Example: Assume EUR for European destinations
        local_currency = "EUR" if country_code in ["FR", "DE", "IT", "ES"] else "USD"
        local_amount = currency_api.convert_currency(budget, home_currency, local_currency)
        if local_amount:
            enrichment["local_budget"] = {
                "amount": local_amount,
                "currency": local_currency,
                "original": {"amount": budget, "currency": home_currency}
            }
    
    return enrichment
