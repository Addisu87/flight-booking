import sys
import os
import asyncio
import datetime
import streamlit as st
import logfire

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.flight_models import (
    FlightClass,
    FlightSearchRequest,
    NoFlightFound,
    BookingConfirmation,
    FlightSearchResult,
)
from app.agents.flight_search_agent import (
    flight_search_agent,
    FlightDeps,
)
from app.agents.booking_agent import booking_agent, BookingDeps
from app.agents.summarize_agent import (
    summarize_agent,
    SummarizeDeps,
)
from app.utils.logging import setup_logfire
# from pydantic_ai.usage import RunUsage

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
            placeholder="JFK",
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
            placeholder="LAX",
            help="3-letter airport code (e.g., SFO, JFK, LAX)",
        ).upper()

        seat_preference = st.text_input(
            "Seat Preference (Optional)",
            placeholder="e.g., 'window seat', '12A', 'aisle seat near front'",
            help="Describe your preferred seat",
        )

    return origin, destination, departure_date, seat_preference, settings


def render_flight_results(result):
    """Render flight search results."""
    if isinstance(result, NoFlightFound):
        st.warning(f"❌ {result.message}")
        st.info("💡 Suggestions: " + ", ".join(result.suggestions))
        return

    st.success(f"🎉 Found {len(result.flights)} flights!")

    # Summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Cheapest", f"${result.cheapest_price:.2f}")
    with col2:
        st.metric("Average", f"${result.average_price:.2f}")
    with col3:
        st.metric("Best Value", result.best_value_flight.flight_number)

    # Flight list
    st.subheader("✈️ Available Flights")
    for flight in result.flights[:5]:
        with st.expander(
            f"**{flight.airline} {flight.flight_number}** - ${flight.price:.2f}"
        ):
            st.write(f"**Duration:** {flight.duration}")
            st.write(f"**Stops:** {flight.stops}")
            st.write(f"**Departure:** {flight.departure_time}")
            st.write(f"**Arrival:** {flight.arrival_time}")


def render_booking_confirmation(booking: BookingConfirmation):
    """Render booking confirmation."""
    st.success("🎉 Booking Confirmed!")

    # Use display helper
    booking_dict = booking.model_dump_for_display()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📋 Flight Details")
        st.write(f"**Flight:** {booking_dict['flight_number']}")
        st.write(f"**Airline:** {booking_dict['airline']}")
        st.write(f"**Route:** {booking_dict['route']}")
        st.write(f"**Price:** ${booking_dict['price']:.2f}")

    with col2:
        st.subheader("💺 Seat & Confirmation")
        st.write(f"**Seat:** {booking_dict['seat']}")
        if booking_dict.get("has_extra_legroom"):
            st.write("✅ Extra legroom included")
        st.write(f"**Confirmation:** {booking_dict['confirmation_number']}")
        st.write(f"**Status:** {booking_dict['status']}")


async def main_application_flow():
    """Main application flow using agent-centric pattern."""
    setup_streamlit_app()
    sidebar_settings = render_sidebar()

    origin, destination, departure_date, seat_preference, settings = (
        render_booking_form(sidebar_settings)
    )

    # Create tabs
    tab1, tab2 = st.tabs(["🚀 Book Flight", "📊 Analyze Flights"])

    with tab1:
        if st.button("🚀 Complete Booking", type="primary", use_container_width=True):
            if not origin or not destination:
                st.error("❌ Please enter both airport codes")
                return

            with st.spinner("🔄 Processing booking... This may take 60-90 seconds."):
                try:
                    search_request = FlightSearchRequest(
                        origin=origin,
                        destination=destination,
                        departure_date=departure_date,
                        passengers=settings["default_passengers"],
                        flight_class=settings["flight_class"],
                    )

                    # ✅ STEP 1: Search for flights FIRST
                    search_result = await flight_search_agent.run(
                        f"Search flights {origin}→{destination}",
                        deps=FlightDeps(search_request=search_request),
                    )

                    # ✅ STEP 2: Handle "no flights" IMMEDIATELY
                    if isinstance(search_result.data, NoFlightFound):
                        st.warning(f"❌ {search_result.data.message}")
                        st.info(
                            "💡 Suggestions: "
                            + ", ".join(search_result.data.suggestions)
                        )
                        return  # Early exit - no booking possible

                    # ✅ STEP 3: Extract best flight
                    if (
                        not isinstance(search_result.data, FlightSearchResult)
                        or not search_result.data.flights
                    ):
                        st.error("❌ Unexpected error: No flights found")
                        return

                    best_flight = search_result.data.best_value_flight

                    # ✅ STEP 4: Only now call booking agent with CONFIRMED flight

                    # ✅ Create usage tracker at top level
                    # usage = RunUsage()

                    # ✅ Call booking agent directly
                    booking_result = await booking_agent.run(
                        "Complete flight booking workflow",
                        deps=BookingDeps(
                            search_request=search_request,
                            selected_flight=best_flight,
                            seat_preference_prompt=seat_preference,
                        ),
                        # usage=usage,
                        # usage_limits=BOOKING_USAGE_LIMITS,
                    )

                    logfire.debug(
                        "Booking agent result",
                        result_type=type(booking_result.data),
                        result=booking_result.data,
                    )

                    # ✅ STEP 5: Display confirmation
                    render_booking_confirmation(booking_result.data)

                except Exception as e:
                    logfire.error("Booking failed", error=str(e), exc_info=True)
                    st.error(f"🚨 Booking failed: {str(e)}")

    with tab2:
        if origin and destination:
            search_request = FlightSearchRequest(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                passengers=settings["default_passengers"],
                flight_class=settings["flight_class"],
            )

            with st.spinner("🔄 Analyzing flights..."):
                try:
                    # ✅ Create usage tracker at top level
                    # usage = RunUsage()

                    # ✅ Call flight search agent
                    search_result = await flight_search_agent.run(
                        f"Analyze flights from {origin} to {destination}",
                        deps=FlightDeps(search_request=search_request),
                        # usage=usage,
                        # usage_limits=FLIGHT_SEARCH_USAGE_LIMITS,
                    )

                    if isinstance(search_result.data, NoFlightFound):
                        st.warning("No flights found for analysis")
                    else:
                        # ✅ Call summarize agent
                        summary_result = await summarize_agent.run(
                            "Generate comprehensive flight summary",
                            deps=SummarizeDeps(
                                search_request=search_request,
                                flights=search_result.data.flights,
                            ),
                            # usage=usage,
                            # usage_limits=SUMMARIZE_USAGE_LIMITS,
                        )

                        # Display results
                        render_flight_results(search_result.data)

                        st.markdown("---")
                        st.subheader("🤖 AI Analysis")
                        st.write(summary_result.data.summary_text)

                        if summary_result.data.recommendations:
                            st.subheader("🎯 Recommendations")
                            for rec in summary_result.data.recommendations:
                                st.write(f"• {rec}")

                except Exception as e:
                    logfire.error("Analysis failed", error=str(e), exc_info=True)
                    st.error(f"🚨 Analysis failed: {str(e)}")
        else:
            st.info("✈️ Enter airport codes to see flight analysis")

    # How it works
    with st.sidebar:
        st.markdown("---")
        st.subheader("💡 How It Works")
        st.info(
            """
            **Agent-Based Workflow:**
            1. **Search Agent** fetches & extracts real flights
            2. **Booking Agent** coordinates seat selection
            3. **Summarize Agent** provides AI insights
            
            *Direct agent orchestration - no service layer*
            """
        )


def main():
    """Entry point."""
    try:
        asyncio.run(main_application_flow())
    except Exception as e:
        st.error(f"🚨 Failed to start: {str(e)}")
        logfire.error("Startup error", error=str(e), exc_info=True)


if __name__ == "__main__":
    main()
