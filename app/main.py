import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import datetime
import streamlit as st
import logfire

from app. models.flight_models import FlightClass, FlightSearchRequest
from app.utils.logging import setup_logfire
from app.services.booking_services import complete_booking_workflow


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
        st.header("⚙️ Booking Settings")
        
        st.markdown("---")
        
        # Settings
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
        
        max_seat_attempts = st.slider(
            "Max Seat Selection Attempts",
            min_value=1,
            max_value=5,
            value=3,
            help="Number of attempts for AI to find your preferred seat"
        )
        
        return {
            "default_passengers": default_passengers,
            "flight_class": FlightClass(flight_class),
            "max_seat_attempts": max_seat_attempts
        }


@logfire.instrument("render_booking_form")
def render_booking_form(settings: dict):
    """Render the complete booking form."""
    st.markdown('<div class="main-header">✈️ FlightFinder Pro</div>', unsafe_allow_html=True)
    st.markdown('<div class="subheader">Complete AI-Powered Flight Booking</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    st.header("🔍 Book Your Flight")
    
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
        
        seat_preference = st.text_input(
            "Seat Preference (Optional)",
            placeholder="e.g., 'window seat', '12A', 'aisle seat near front'",
            help="Describe your preferred seat"
        )
    
    return origin, destination, departure_date, seat_preference, settings


@logfire.instrument("render_booking_result")
def render_booking_result(result):
    """Render complete booking results."""
    if result["status"] == "error":
        st.error(f"❌ {result['reason']}")
        return
    
    # Successful booking
    st.success("🎉 Booking Confirmed!")
    
    # Booking details
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📋 Flight Details")
        st.write(f"**Flight:** {result['flight_number']}")
        st.write(f"**Airline:** {result['airline']}")
        st.write(f"**Route:** {result['route']}")
        st.write(f"**Date:** {result['date']}")
        st.write(f"**Time:** {result['departure_time']} - {result['arrival_time']}")
    
    with col2:
        st.subheader("💺 Seat & Payment")
        st.write(f"**Seat:** {result['seat']}")
        st.write(f"**Seat Type:** {result['seat_type'].title()}")
        st.write(f"**Extra Legroom:** {'Yes' if result['has_extra_legroom'] else 'No'}")
        st.write(f"**Price:** ${result['price']}")
        st.write(f"**Confirmation:** {result['confirmation_number']}")
    
    # Workflow stats
    st.subheader("📊 Booking Summary")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Seat Attempts", result["workflow_steps"]["seat_selection_attempts"])
    with col2:
        st.metric("Total Duration", f"{result['workflow_steps']['total_duration']:.1f}s")
    with col3:
        st.metric("Status", result["status"].title())
    
    # Purchase info
    st.info(f"🕒 Booked at: {result['purchase_time']}")


@logfire.instrument("main_application_flow")
async def main_application_flow():
    """Main application flow using complete booking workflow."""
    # Setup
    setup_streamlit_app()
    sidebar_settings = render_sidebar()
    
    try:
        # Booking form
        origin, destination, departure_date, seat_preference, settings = render_booking_form(sidebar_settings)
        
        # For demo purposes - you would replace this with actual flight data
        available_flights = []  # This would come from your flight search
        
        book_button = st.button("🚀 Complete Booking", type="primary", use_container_width=True)
        
        # Complete booking workflow
        if book_button:
            with st.spinner("🔄 Processing complete booking... This may take a minute."):
                search_request = FlightSearchRequest(
                    origin=origin,
                    destination=destination,
                    departure_date=departure_date,
                    passengers=settings["default_passengers"],
                    flight_class=settings["flight_class"]
                )
                
                # Use the complete booking workflow
                result = await complete_booking_workflow(
                    search_request=search_request,
                    available_flights=available_flights,  # You'll need to populate this
                    seat_preference_prompt=seat_preference,
                    max_seat_retries=settings["max_seat_attempts"]
                )
                
                render_booking_result(result)
        
        # How it works info
        with st.sidebar:
            st.markdown("---")
            st.subheader("💡 How It Works")
            st.info("""
            **Complete Booking Workflow:**
            1. **Search** for available flights
            2. **Select** the best flight option  
            3. **Choose** your preferred seat using AI
            4. **Generate** booking confirmation
            
            *API keys are configured via .env file*
            """)
    
    except Exception as e:
        logfire.error("Application error", error=str(e))
        st.error(f"🚨 An unexpected error occurred: {str(e)}")
        st.info("💡 Please check the console for details.")


def main():
    """Main entry point with async support."""
    try:
        asyncio.run(main_application_flow())
    except Exception as e:
        st.error(f"Failed to start application: {str(e)}")


if __name__ == "__main__":
    main()