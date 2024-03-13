import streamlit as st
from streamlit_extras.switch_page_button import switch_page


def main() -> None:
    """Main function for the Invit(ai)tions Streamlit app."""

    st.set_page_config(page_title="Welcome", page_icon=":wave:")

    st.title("Welcome to CareGiver Scheduler :rocket:")

    # Container to hold the content above the button
    content_container = st.container()

    with content_container:
        st.markdown(
            """

        Your solution for optimizing caregiver schedules and maximizing efficiency in providing care services! Whether you're managing a home care agency or coordinating caregiver assignments, our platform is designed to streamline your scheduling process and enhance the quality of care provided to clients.

        ## What We Offer

        - **Schedule Optimization**: Utilize advanced algorithms to optimize caregiver schedules based on key constraints such as commute time, service offerings, and caregiver availability. Maximize efficiency and minimize downtime to ensure optimal care delivery.

        - **Route Planning**: Leverage our route planning tools to minimize travel time and optimize caregiver routes between client visits. Reduce fuel consumption, carbon emissions, and overall travel costs while improving caregiver productivity.

        - **Service Matching**: Match caregivers with clients based on their specific service offerings and client needs. Ensure that caregivers are assigned tasks that align with their skillset and expertise, resulting in better quality care and client satisfaction.

        ## How It Works

        1. **Input Caregiver Data**: Start by inputting caregiver profiles, including their availability, service offerings, and location. Our platform allows you to easily manage caregiver information and preferences.

        2. **Define Client Needs**: Define the specific care services required by each client, including service type, frequency, and preferred caregiver attributes. Our platform enables you to customize client profiles and preferences to ensure personalized care.

        3. **Optimize Schedules**: Our scheduling algorithm analyzes caregiver availability, service offerings, and commute times to generate optimized schedules. Seamlessly assign caregivers to client visits while minimizing travel time and maximizing productivity.

        4. **Review and Adjust**: Review the generated schedules and make any necessary adjustments based on client preferences, caregiver availability, or unexpected changes. Our platform provides flexibility to accommodate last-minute changes and optimize schedules in real-time.

        ## Get Started Today!

        Ready to optimize your caregiver schedules and improve the quality of care provided to your clients?
        """
        )

    # Button to navigate to the inner page
    get_started_button = st.button("Get Started")

    if get_started_button:
        switch_page("data_analysis")


if __name__ == "__main__":
    main()
