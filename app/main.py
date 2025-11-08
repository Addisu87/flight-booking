import asyncio
import datetime
import streamlit as st
import os
import time
from typing import Optional
import logfire

from app.services.flight_service import FlightService
from app.models.flight_models import (
    FlightSearchRequest,
    FlightClass,
    SeatPreference
)
from app.utils.config import settings
from app.utils.logging import setup_logfire


# Initialize logging
logfire = setup_logfire()


@logfire.instrument("setup_streamlit_app")
def setup_streamlit_app():
    """Configure Streamlit application with enhanced UI."""
    st.set_page_config(
        page_title="✈️ FlightFinder Pro",
        page_icon="✈️",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS for better styling
    st.markdown("""
    <style>
    .main-header {
        font-size: 3rem;
        color: #0066cc;
        text-align: center;
        margin-bottom: 1rem;
    }
    .subheader {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .info-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        color: #0c5460;
    }
    .flight-card {
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 0.5rem;
        border: 1px solid #ddd;
        background-color: #f8f9fa;
    }
    </style>
    """, unsafe_allow_html=True)


@logfire.instrument("render_sidebar")
def render_sidebar():
    """Render the configuration sidebar."""
    with st.sidebar:
        col1, col2 = st.columns([1, 3])
        with col1:
            st.write("")
            st.image("https://browserbase.ai/favicon-32x32.png", width=65)
        with col2:
            st.header("🔧 Configuration")
        
        st.markdown("---")
        
        # API Key Sections
        st.subheader("🔑 API Keys")
        st.markdown("[Get Browserbase API key](https://browserbase.ai)")
        st.markdown("[Get OpenAI API key](https://platform.openai.com/)")
        
        browserbase_api_key = st.text_input(
            "Browserbase API Key",
            type="password",
            help="Required for web scraping flight data"
        )
        openai_api_key = st.text_input(
            "OpenAI API Key", 
            type="password",
            help="Required for AI-powered flight analysis"
        )
        
        # Store API keys
        if browserbase_api_key:
            os.environ["BROWSERBASE_API_KEY"] = browserbase_api_key
            st.success("✅ Browserbase API Key stored")
        if openai_api_key:
            os.environ["OPENAI_API_KEY"] = openai_api_key
            st.success("✅ OpenAI API Key stored")
        
        st.markdown("---")
        
        # Settings
        st.subheader("⚙️ Search Settings")
        default_passengers = st.number_input(
            "Passengers", 
            min_value=1, 
            max_value=9, 
            value=1,
            help="Number of passengers"
        )
        
        flight_class = st.selectbox(
            "Flight Class",
            options=[fc.value for fc in FlightClass],
            index=0,
            help="Preferred flight class"
        )
        
        direct_only = st.checkbox(
            "Direct flights only", 
            value=False,
            help="Show only non-stop flights"
        )
        
        return {
            "default_passengers": default_passengers,
            "flight_class": FlightClass(flight_class),
            "direct_only": direct_only
        }


@logfire.instrument("render_search_form")
def render_search_form(settings: dict):
    """Render the flight search form."""
    st.markdown('<div class="main-header">✈️ FlightFinder Pro</div>', unsafe_allow_html=True)
    st.markdown('<div class="subheader">AI-Powered Flight Search with Real-Time Data</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    st.header("🔍 Search for Flights")
    
    col1, col2 = st.columns(2)
    
    with col1:
        origin = st.text_input(
            "Departure Airport Code", 
            "SFO",
            help="3-letter airport code (e.g., SFO, JFK, LAX)"
        ).upper()
        
        departure_date = st.date_input(
            "Departure Date",
            datetime.date.today() + datetime.timedelta(days=30),
            help="Select your departure date"
        )
    
    with col2:
        destination = st.text_input(
            "Arrival Airport Code", 
            "JFK",
            help="3-letter airport code (e.g., SFO, JFK, LAX)"
        ).upper()
        
        return_date = st.date_input(
            "Return Date (Optional)",
            value=None,
            help="For round-trip flights"
        )
    
    return origin, destination, departure_date, return_date, settings


@logfire.instrument("render_flight_results")
def render_flight_results(result):
    """Render flight search results with enhanced UI."""
    if hasattr(result, 'message'):  # NoFlightFound
        st.error(f"❌ {result.message}")
        
        if hasattr(result, 'suggestions') and result.suggestions:
            st.info("💡 Suggestions:")
            for suggestion in result.suggestions:
                st.write(f"- {suggestion}")
        return
    
    # Successful search results
    st.success(f"✅ Found {len(result.flights)} flights")
    
    # Search analytics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Cheapest", f"${result.cheapest_flight}" if result.cheapest_flight else "N/A")
    with col2:
        st.metric("Fastest", result.fastest_flight or "N/A")
    with col3:
        st.metric("Search Time", f"{result.search_duration:.1f}s")
    
    # Flight cards
    st.subheader("🎫 Available Flights")
    
    for i, flight in enumerate(result.flights[:10]):  # Show top 10
        with st.container():
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                st.write(f"**{flight.airline} {flight.flight_number}**")
                st.write(f"🛫 {flight.origin} → 🛬 {flight.destination}")
                st.write(f"📅 {flight.date} | ⏱️ {flight.duration}")
                st.write(f"🕒 {flight.departure_time} - {flight.arrival_time}")
                
            with col2:
                if flight.is_direct:
                    st.success("✈️ Direct flight")
                else:
                    st.warning(f"🔀 {flight.stops} stop(s)")
                
                st.write(f"🎫 {flight.flight_class.value.title()}")
                
            with col3:
                st.metric("Price", f"${flight.price}")
                
                if flight.booking_url:
                    st.link_button("📖 Book Now", flight.booking_url)
            
            st.markdown("---")


@logfire.instrument("render_seat_selection")
def render_seat_selection():
    """Render seat selection interface."""
    st.header("💺 Seat Selection")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        seat_preference = st.text_input(
            "Enter seat preference",
            placeholder="e.g., '12A', 'window seat', 'aisle seat row 5'",
            help="Specify your preferred seat (row 1-30, seat A-F)"
        )
    
    with col2:
        st.write("")  # Spacing
        st.write("")  # Spacing
        select_seat_btn = st.button("Select Seat", use_container_width=True)
    
    return seat_preference, select_seat_btn


@logfire.instrument("render_seat_result")
def render_seat_result(seat: SeatPreference):
    """Render seat selection results."""
    st.success(f"✅ Seat selected: **{seat}**")
    
    # Seat features
    features = []
    if seat.seat_type.value == "window":
        features.append("🌅 Window view")
    elif seat.seat_type.value == "aisle":
        features.append("🛣️ Easy access")
    else:
        features.append("💺 Middle seat")
    
    if seat.has_extra_legroom:
        features.append("🦵 Extra legroom")
    
    if features:
        st.info(" | ".join(features))
    
    # Seat map visualization
    st.subheader("🗺️ Seat Map Reference")
    st.markdown("""
    ```
    Window     Aisle      Window
    [A] [B] [C]  |  [D] [E] [F]
    ```
    """)
    
    st.caption("💡 Tips: A/F = Window, C/D = Aisle, B/E = Middle. Rows 1, 14, 20 have extra legroom.")


@logfire.instrument("main_application_flow")
async def main_application_flow():
    """Main application flow with comprehensive error handling."""
    # Setup
    setup_streamlit_app()
    sidebar_settings = render_sidebar()
    
    # Check API keys
    if not os.environ.get("BROWSERBASE_API_KEY") or not os.environ.get("OPENAI_API_KEY"):
        st.warning("⚠️ Please configure your API keys in the sidebar to get started.")
        return
    
    try:
        # Initialize services
        flight_service = FlightService()
        
        # Search form
        origin, destination, departure_date, return_date, settings = render_search_form(sidebar_settings)
        search_button = st.button("🚀 Search Flights", type="primary", use_container_width=True)
        
        # Flight search
        if search_button:
            with st.spinner("🔍 Searching for flights... This may take 30-60 seconds."):
                search_request = FlightSearchRequest(
                    origin=origin,
                    destination=destination,
                    departure_date=departure_date,
                    return_date=return_date,
                    passengers=settings["default_passengers"],
                    flight_class=settings["flight_class"],
                    direct_only=settings["direct_only"]
                )
                
                result = await flight_service.search_flights(search_request)
                render_flight_results(result)
                
                # Store result in session state for seat selection
                st.session_state.last_search_result = result
        
        # Seat selection (if we have results)
        if hasattr(st.session_state, 'last_search_result') and not hasattr(st.session_state.last_search_result, 'message'):
            st.markdown("---")
            seat_preference, select_seat_btn = render_seat_selection()
            
            if select_seat_btn and seat_preference:
                with st.spinner("💺 Processing seat selection..."):
                    seat = await flight_service.select_seat(seat_preference)
                    render_seat_result(seat)
        
        # Usage statistics
        with st.sidebar:
            st.markdown("---")
            st.subheader("📊 Usage")
            usage_stats = flight_service.get_usage_stats()
            st.metric("API Requests", usage_stats["total_requests"])
            st.metric("Total Tokens", f"{usage_stats['total_tokens']:,}")
            st.metric("Total Duration", f"{usage_stats['total_duration']:.1f}s")
    
    except Exception as e:
        logfire.error("Application error", error=str(e))
        st.error(f"🚨 An unexpected error occurred: {str(e)}")
        st.info("💡 Please try refreshing the page or check the console for details.")


def main():
    """Main entry point with async support."""
    try:
        asyncio.run(main_application_flow())
    except Exception as e:
        st.error(f"Failed to start application: {str(e)}")


if __name__ == "__main__":
    main()