from datetime import datetime, timezone
from typing import Literal, List
from pydantic import BaseModel, Field, ConfigDict, field_validator
from enum import Enum
import uuid

class FlightClass(str, Enum):
    ECONOMY = 'economy'
    PREMIUM_ECONOMY = 'premium_economy'
    BUSINESS = 'business'
    FIRST = 'first'
    
class SeatType(str, Enum):
    WINDOW = 'window'
    AISLE = 'aisle'
    MIDDLE = 'middle'
    
class FlightStatus(str, Enum):
    AVAILABLE = 'available'
    BOOKED = 'booked'
    CANCELLED = 'cancelled'
    
class FlightDetails(BaseModel):
    """Details of a flight."""
    model_config = ConfigDict(str_strip_whitespace=True, frozen=True)
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    airline: str
    flight_number: str
    price: float
    origin: str = Field(..., pattern=r'^[A-Z]{3}$', description="ETH airport code")
    destination: str = Field(..., pattern=r'^[A-Z]{3}$', description="ETH airport code")
    departure_time: str
    arrival_time: str
    duration: str
    date: datetime.date
    flight_class: FlightClass = Field(default=FlightClass.ECONOMY)
    aircraft: str | None = None
    stops: int = Field(default=0, ge=0)
    booking_url: str | None = Field(None, pattern=r'^https?://')
    
    @field_validator('departure_time', 'arrival_time')
    def validate_time_format(cls, v):
        try: 
            datetime.datetime.strptime(v, '%H:%M')
            return v 
        except ValueError: 
            raise ValueError('Time must be in HH:MM format')
        
    @property
    def is_direct(self) -> bool: 
        return self.stops == 0
    
class FlightSearchRequest(BaseModel):
    """Flight search request parameters."""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    origin: str = Field(..., pattern=r'^[A-Z]{3}$')
    destination: str = Field(..., pattern=r'^[A-Z]{3}$')
    departure_date: datetime.date
    return_date: datetime.date  | None = None
    passengers: int 
    flight_class: FlightClass = Field(default=FlightClass.ECONOMY)
    max_price: float  | None = Field(None, gt=0)
    direct_only: bool = False
    
    @field_validator('return_date')
    def validate_return_date(cls, v, values):
        if v and 'departure_date' in values and v < values['departure_date']:
            raise ValueError('Return date must be after departure date')
        return v
    
    @property
    def is_round_trip(self) -> bool: 
        return self.return_date is not None


class FlightSearchResult(BaseModel):
    """Result of flight search with analytics."""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    request: FlightSearchRequest
    flights: List[FlightDetails]
    total_found: int 
    cheapest_flight: float | None = None 
    fastest_flight: str | None = None 
    best_value_flight: FlightDetails | None = None
    summary: str
    
    def calculate_analytics(self):
        """Calculate search analytics"""
        if self.flights: 
            self.cheapest_flights = min(flight.price for flight in self.flights)


class NoFlightFound(BaseModel):
    """When no valid flight is found."""
    message: str = "No flights found matching your criteria."
    search_request: FlightSearchRequest
    suggestions: List[str] 
    alternative_dates: List[datetime.date]


class SeatPreference(BaseModel):
    """Seat selection preferences."""
    model_config = ConfigDict(str_strip_whitespace=True)
     
    row: int = Field(..., ge=1, le=30, description="Row number between 1 and 30")
    seat: Literal["A", "B", "C", "D", "E", "F"] = Field(description="Seat position")
    seat_type: SeatType = Field(description='Type of seat')
    
    def __init__(self, **data):
        super().__init__(**data)
        # Automatically determine seat type 
        if not hasattr(self, 'seat_type'):
            self.seat_type = SeatType.WINDOW
        elif self.seat in ['C', 'D']:
            self.seat_type = SeatType.AISLE
        else: 
            self.seat_type = SeatType.MIDDLE
            
    @property
    def has_extra_legroom(self) -> bool: 
        return self.row in [1, 14, 20]
    
    def __str__(self):
        return f"{self.row}{self.seat} {self.seat_type.value}"


class SeatSelectionFailed(BaseModel):
    """Unable to extract a seat selection."""
    message: str = "Failed to process seat selection."
    user_input: str 
    reason: str

class BookingConfirmation(BaseModel):
    """Flight booking confirmation with full details."""
    model_config = ConfigDict(str_strip_whitespace=True, frozen=True)
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    flight: FlightDetails
    seat: SeatPreference
    passengers: int = Field(1, ge=1, le=9)
    total_price: float
    confirmation_number: str = Field(..., pattern=r'^[A-Z0-9]{6, 10}$')
    booking_time: datetime.datetime.now(timezone.utc)
    status: FlightStatus = Field(default = FlightStatus.BOOKED)
    
    
    @field_validator('total_price')
    def validate_total_price(cls, v, values):
        if 'flight' in values and v < values['flight'].price: 
            raise ValueError('Total price cannot be less than flight price')
        return v 
    
    @property
    def is_active(self) -> bool: 
        return self.status == FlightStatus.BOOKED
    
class FlightSummary(BaseModel):
    """Summary output using existing FlightDetails model."""
    model_config = ConfigDict(str_strip_whitespace=True, frozen=True)
    
    total_flights: int 
    price_range: str
    best_deal: FlightDetails 
    best_timing: FlightDetails 
    airlines: List[str] 
    direct_flights: int 
    connecting_flights: int 
    summary_text: str = Field(..., description="Human-readable summary")
    recommendations: List[str] 
    key_insights: List[str]