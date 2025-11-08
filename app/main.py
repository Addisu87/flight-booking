import asyncio
import datetime
import streamlit as st
import os

from app.agents.flight_agent import (
    flight_extraction_agent, 
    flight_search_agent, 
    FlightDeps,
)
from app.agents.seat_agent import seat_selection_agent
from app.models.flight_models import (
    FlightSearchRequest,
    FlightDetails,
    SeatPreference,
    BookingConfirmation
)
from app.tools.browserbase_tool import browserbase_tool
from app.tools.kayak_tool import kayak_search_tool
from app.utils.config import settings


# Page configuration
st.set_page_config(page_title="✈️ FlightFinder Pro", layout="wide")

# Title and subtitle
st.markdown("<h1 style='color: #0066cc;'>✈️ FlightFinder Pro</h1>", unsafe_allow_html=True)
st.subheader("Powered by Browserbase and Pydantic AI")

# Sidebar for API key input
with st.sidebar:
    col1, col2 = st.columns([1, 3])
    with col1:
        st.write("")
        st.image("https://browserbase.ai/favicon-32x32.png", width=65)
    with col2:
        st.header("Configuration")
    
    st.markdown("[Get Browserbase API key](https://browserbase.ai)", unsafe_allow_html=True)
    st.markdown("[Get OpenAI API key](https://platform.openai.com/)", unsafe_allow_html=True)
    
    browserbase_api_key = st.text_input("Browserbase API Key", type="password")
    openai_api_key = st.text_input("OpenAI API Key", type="password")
    
    # Store API keys
    if browserbase_api_key:
        os.environ["BROWSERBASE_API_KEY"] = browserbase_api_key
    if openai_api_key:
        os.environ["OPENAI_API_KEY"] = openai_api_key


async def search_flights(search_request: FlightSearchRequest) -> str:
    """Search for flights using the agent system."""
    try:
        # Generate Kayak URL
        kayak_url = kayak_search_tool(search_request)
        
        # Use Browserbase to get page content
        page_content = browserbase_tool(kayak_url)
        
        # Extract flights from page content
        extraction_result = await flight_extraction_agent.run(page_content)
        available_flights = extraction_result.data
        
        if not available_flights:
            return "No flights found for your search criteria."
        
        # Search for best flights
        deps = FlightDeps(
            search_request=search_request,
            available_flights=available_flights
        )
        
        search_result = await flight_search_agent.run(
            f"Find the best flights from {search_request.origin} to {search_request.destination} on {search_request.departure_date}",
            deps=deps
        )
        
        return str(search_result.data)
        
    except Exception as e:
        return f"Error searching flights: {str(e)}"


async def select_seat(seat_preference: str) -> SeatPreference:
    """Process seat selection using the seat agent."""
    try:
        result = await seat_selection_agent.run(seat_preference)
        if hasattr(result.data, 'row') and hasattr(result.data, 'seat'):
            return result.data
        else:
            # Return default seat if selection fails
            return SeatPreference(row=10, seat="C")
    except Exception:
        return SeatPreference(row=10, seat="C")


def main():
    """Main Streamlit application."""
    st.markdown("---")
    
    # Flight search form
    st.header("Search for Flights")
    col1, col2 = st.columns(2)
    
    with col1:
        origin = st.text_input("Origin City (Airport Code)", "SFO")
        departure_date = st.date_input("Departure Date", datetime.date.today() + datetime.timedelta(days=30))
    
    with col2:
        destination = st.text_input("Destination City (Airport Code)", "JFK")
        return_date = st.date_input("Return Date (Optional)", value=None)
    
    search_button = st.button("Search Flights")
    
    # Search functionality
    if search_button:
        if not os.environ.get("BROWSERBASE_API_KEY"):
            st.error("Please enter your Browserbase API Key in the sidebar first!")
        elif not os.environ.get("OPENAI_API_KEY"):
            st.error("Please enter your OpenAI API Key in the sidebar first!")
        else:
            with st.spinner("Searching for flights... This may take a few minutes."):
                search_request = FlightSearchRequest(
                    origin=origin.upper(),
                    destination=destination.upper(),
                    departure_date=departure_date,
                    return_date=return_date
                )
                
                # Run async function
                result = asyncio.run(search_flights(search_request))
                
                st.success("Search completed!")
                st.markdown("## Flight Results")
                st.markdown(result)
    
    # Seat selection section
    st.markdown("---")
    st.header("Seat Selection")
    
    seat_preference = st.text_input("Enter your seat preference (e.g., '12A' or 'window seat'):")
    if st.button("Select Seat"):
        if seat_preference:
            with st.spinner("Processing seat selection..."):
                seat = asyncio.run(select_seat(seat_preference))
                st.success(f"Seat selected: {seat.row}{seat.seat}")
                
                # Show seat info
                if seat.seat in ["A", "F"]:
                    st.info("🌅 Window seat selected")
                elif seat.seat in ["C", "D"]:
                    st.info("🛣️ Aisle seat selected")
                else:
                    st.info("💺 Middle seat selected")
                    
                if seat.row in [1, 14, 20]:
                    st.info("🦵 Extra leg room available")
        else:
            st.warning("Please enter a seat preference")
    
    # About section
    st.markdown("---")
    st.markdown("""
    ### About FlightFinder Pro
    This application uses AI agents powered by Pydantic AI to search for flights 
    and find the best deals for you. The system:
    - Searches Kayak for flight options
    - Uses Browserbase for web scraping
    - Extracts and analyzes flight data using AI
    - Helps with seat selection
    """)


if __name__ == "__main__":
    main()