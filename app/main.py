import sys
import os
import asyncio
import datetime
import streamlit as st
import logfire

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.flight_models import FlightClass, FlightSearchRequest
from app.utils.logging import setup_logfire
from app.services.booking_services import complete_booking_workflow
from app.services.summarize_services import generate_flight_summary, generate_quick_insights

# Initialize logging
logfire = setup_logfire()

st.set_page_config(
    page_title="✈️ FlightFinder Pro",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def setup_streamlit_app():
    """Configure Streamlit application with enhanced UI."""
    # Custom CSS for better styling
    st.markdown(
        """
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
    """,
        unsafe_allow_html=True,
    )


def render_sidebar():
    """Render the configuration sidebar."""
    with st.sidebar:
        st.header("⚙️ Booking Settings")
        st.markdown("---")

        default_passengers = st.number_input(
            "Passengers", min_value=1, max_value=9, value=1, help="Number of passengers"
        )

        flight_class = st.selectbox(
            "Flight Class",
            options=[fc.value for fc in FlightClass],
            index=0,
            help="Preferred flight class",
        )

        return {
            "default_passengers": default_passengers,
            "flight_class": FlightClass(flight_class),
        }


def render_booking_form(settings: dict):
    """Render the complete booking form."""
    st.markdown(
        '<div class="main-header">✈️ FlightFinder Pro</div>', unsafe_allow_html=True
    )
    st.markdown(
        '<div class="subheader">Complete AI-Powered Flight Booking</div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.header("🔍 Book Your Flight")

    col1, col2 = st.columns(2)

    with col1:
        origin = st.text_input(
            "Departure Airport Code",
            value="",
            placeholder="ADD",
            help="3-letter airport code (e.g., SFO, JFK, LAX)",
        ).upper()
        
        departure_date = st.date_input(
            "Departure Date",
            datetime.date.today() + datetime.timedelta(days=30),
            help="Select your departure date",
        )

    with col2:
        destination = st.text_input(
            "Arrival Airport Code",
            value="",
            placeholder="JFK",
            help="3-letter airport code (e.g., SFO, JFK, LAX)",
        ).upper()
        
        seat_preference = st.text_input(
            "Seat Preference (Optional)",
            placeholder="e.g., 'window seat', '12A', 'aisle seat near front'",
            help="Describe your preferred seat",
        )

    return origin, destination, departure_date, seat_preference, settings


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
        st.write(f"**Flight:** {result.get('flight_number', 'N/A')}")
        st.write(f"**Airline:** {result.get('airline', 'N/A')}")
        st.write(f"**Route:** {result.get('route', 'N/A')}")
        st.write(f"**Price:** ${result.get('price', 'N/A')}")
        st.write(f"**Departure:** {result.get('departure_time', 'N/A')}")

    with col2:
        st.subheader("💺 Seat & Confirmation")
        st.write(f"**Seat:** {result.get('seat', 'N/A')}")
        st.write(f"**Seat Type:** {result.get('seat_type', 'N/A')}")
        st.write(f"**Confirmation:** {result.get('confirmation_number', 'N/A')}")
        st.write(f"**Status:** {result.get('status', 'N/A')}")

    # Usage stats if available
    if "usage_stats" in result:
        st.subheader("📊 Performance")
        st.write(f"**Total Tokens:** {result['usage_stats'].get('total_tokens', 'N/A')}")
        st.write(f"**Total Cost:** ${result['usage_stats'].get('total_cost', 0):.4f}")


def render_summary_tab(search_request, flights):
    """Render the summary analysis tab."""
    st.header("📊 Flight Analysis")
    
    if not flights:
        st.warning("No flights available for analysis")
        return

    # Quick insights
    insights = generate_quick_insights(flights)
    st.subheader("📈 Quick Insights")
    for insight in insights["insights"]:
        st.write(f"• {insight}")

    # AI-powered summary
    with st.spinner("🤖 Generating AI analysis..."):
        summary = asyncio.run(generate_flight_summary(search_request, flights))
        
        if summary.get("summary_text"):
            st.subheader("🤖 AI Analysis")
            st.write(summary["summary_text"])
            
        if summary.get("key_insights"):
            st.subheader("💡 Key Insights")
            for insight in summary["key_insights"]:
                st.write(f"• {insight}")
                
        if summary.get("recommendations"):
            st.subheader("🎯 Recommendations")
            for rec in summary["recommendations"]:
                st.write(f"• {rec}")


async def main_application_flow():
    """Main application flow using complete booking workflow."""
    # Setup
    setup_streamlit_app()
    sidebar_settings = render_sidebar()

    try:
        # Booking form
        origin, destination, departure_date, seat_preference, settings = (
            render_booking_form(sidebar_settings)
        )

        # Create tabs for different views
        tab1, tab2 = st.tabs(["🚀 Book Flight", "📊 Analyze Flights"])

        with tab1:
            book_button = st.button(
                "🚀 Complete Booking", type="primary", use_container_width=True
            )

            # Complete booking workflow
            if book_button:
                if not origin or not destination:
                    st.error("❌ Please enter both origin and destination airport codes")
                    return

                with st.spinner("🔄 Processing complete booking... This may take a minute."):
                    search_request = FlightSearchRequest(
                        origin=origin,
                        destination=destination,
                        departure_date=departure_date,
                        passengers=settings["default_passengers"],
                        flight_class=settings["flight_class"],
                    )

                    # Use the complete booking workflow (usage is handled internally)
                    result = await complete_booking_workflow(
                        search_request=search_request,
                        seat_preference_prompt=seat_preference if seat_preference else None,
                    )

                    render_booking_result(result)

        with tab2:
            if origin and destination:
                search_request = FlightSearchRequest(
                    origin=origin,
                    destination=destination,
                    departure_date=departure_date,
                    passengers=settings["default_passengers"],
                    flight_class=settings["flight_class"],
                )
                
                # For analysis, we need to get flights first
                from app.services.flight_services import search_flights
                search_result = await search_flights(search_request)
                flights = getattr(search_result, 'flights', []) if hasattr(search_result, 'flights') else []
                
                render_summary_tab(search_request, flights)
            else:
                st.info("✈️ Enter airport codes above to see flight analysis")

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