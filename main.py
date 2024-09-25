import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import pandas as pd
from dotenv import load_dotenv
import os
import sys

#getting the api_key
load_dotenv()
api_key = os.getenv('API_KEY')


#this function queries google places api, the information of the place that we want like pricing levels and the rating that we want to add to the dataframe
def query_google_places(venue_name, venue_address):
    print('Querying Google Places...')
    url = "https://places.googleapis.com/v1/places:searchText"

    # Defining request headers
    headers = {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': api_key,
        'X-Goog-FieldMask': 'places.displayName,places.formattedAddress,places.priceLevel,places.rating,places.reviews'
    }

    # Defining the request body
    payload = {
        "textQuery": f"{venue_name} {venue_address}"
    }

    # Sending the POST request
    response = requests.post(url, headers=headers, json=payload)

    # Checking if the request was successful
    if response.status_code == 200:
        data = response.json()

        if 'places' in data and len(data['places']) > 0:
            place = data['places'][0]

            # Safely extracting details
            display_name = place.get('displayName', venue_name)
            address = place.get('formattedAddress', venue_address)
            price_level = place.get('priceLevel', 'N/A')
            rating = place.get('rating', 'N/A')

            # Extracting the first review if available
            reviews = place.get('reviews', [])
            first_review = reviews[0].get('text', 'No reviews available')['text'] if reviews and isinstance(reviews[0], dict) else 'No reviews available'
            

            return price_level, rating, first_review
        else:
            return "N/A", "N/A", "No reviews available"
    else:
        print(f"Request failed with status code: {response.status_code}")
        return "N/A", "N/A", "No reviews available"

    

def scrape_meetup_events(city, state, country, day):
    # Setting up Selenium WebDriver
    driver = webdriver.Chrome()
    driver.maximize_window()
    
    # Navigating to the Meetup page, I have chosen to find events. Here I have chosen the page within "2 miles radius" of the region, the events are supposed to be "in person" and the events are sorted by "relevance"
    url = f"https://www.meetup.com/find/?location={country}--{state}--{city}&source=EVENTS&distance=twoMiles&dateRange={day}&eventType=inPerson"
    driver.get(url)

    # Waiting for the event cards to load
    wait = WebDriverWait(driver, 10)
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='categoryResults-eventCard']")))
    except TimeoutException:
        print("Timed out waiting for event cards to load")
        driver.quit()
        return

    # Scrolling until no new events are loaded
    def get_event_count():
        return len(driver.find_elements(By.CSS_SELECTOR, "[data-testid='categoryResults-eventCard']"))

    last_count = 0
    while True:
        # Scrolling to the bottom of the page
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)  # Waiting for new content to load
        current_count = get_event_count()
        if current_count == last_count:
            break
        last_count = current_count

    # Storing the event links
    event_links = []
    event_cards = driver.find_elements(By.CSS_SELECTOR, "[data-testid='categoryResults-eventCard']")

    events_data = []
    for card in event_cards:
        # Extracting event name
        event_name = card.find_element(By.CSS_SELECTOR, "h2").text

        # Extracting organizer name
        organizer = card.find_element(By.CSS_SELECTOR, "p.text-gray6").text.replace("Group name:", "").strip()

        # Extracting number of attendees
        try:
            attendees_element = card.find_element(By.CSS_SELECTOR, "div[aria-label$=' attendees']")
            attendees = attendees_element.get_attribute("aria-label").split()[0]
        except NoSuchElementException:
            attendees = "N/A"  # Some events might not have attendee information

        # Trying to get the event link
        try:
            event_link = card.find_element(By.TAG_NAME, 'a').get_attribute('href')
            event_links.append(event_link)
        except Exception as e:
            print(f"Error getting link: {e}")
            continue

        # Appending the partial data (event_name, organizer, attendees, and event_link)
        events_data.append({
            "event_name": event_name,
            "organizer": organizer,
            "attendees": attendees,
            "event_date_time": "N/A",  # Placeholder
            "venue_name": "N/A",        # Placeholder
            "venue_address": "N/A",     # Placeholder
            "cost_of_attendance": "N/A",# Placeholder
            "event_url": event_link,
            "price_level":"N/A",        # Placeholder
            "rating": "N/A",            # Placeholder
            "first_review":"N/A",       # Placeholder
        })

    # Looping through each event link to get additional details
    for i, event_link in enumerate(event_links):
        try:
            # Navigating to the event details page
            driver.get(event_link)

            time.sleep(2)  # Waiting 2 seconds before extracting event details to avoid pinging the server constantly

            # Waiting for the event details to load
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.bg-white.px-5")))

            # Extracting event date and time
            try:
                date_time_element = driver.find_element(By.CSS_SELECTOR, "time")
                event_date_time = date_time_element.text
            except NoSuchElementException:
                event_date_time = "N/A"

            # Extracting the venue information (name and address)
            try:
                venue_name_element = driver.find_element(By.CSS_SELECTOR, "[data-testid='venue-name-link']")
                venue_name = venue_name_element.text
                venue_address_element = venue_name_element.find_element(By.XPATH, "./following-sibling::div")
                venue_address = venue_address_element.text
            except NoSuchElementException:
                venue_name = "N/A"
                venue_address = "N/A"

            # Extracting the cost of attendance
            try:
                cost_element = driver.find_element(By.CSS_SELECTOR, "div.flex.justify-between.text-gray7 span.font-semibold")
                cost_of_attendance = cost_element.text
            except NoSuchElementException:
                cost_of_attendance = "FREE"

            if venue_name!="N/A" and venue_address!="N/A":
                price_level, rating, first_review = query_google_places(venue_name, venue_address) #using the function to query 
            else:
                price_level, rating, first_review="N/A","N/A","No reviews available"

            # Updating the corresponding event's remaining details
            events_data[i].update({
                "event_date_time": event_date_time,
                "venue_name": venue_name,
                "venue_address": venue_address,
                "cost_of_attendance": cost_of_attendance,
                "price_level":price_level,
                 "rating": rating, 
                 "first_review":first_review, 
            })

            # Going back to the main events list
            driver.back()

        except Exception as e:
            print(f"Error extracting data from event page: {e}")
            continue

    # Closing the browser
    driver.quit()

    # Returning the extracted data
    return events_data

unformatted_city=input("Enter the name of your city/area in the US (e.g. Manhattan): ") 
city = '%20'.join(part.capitalize() for part in unformatted_city.split())
state=input("Enter the two-letter state/territory abbreviation in the US (like NY for New York, CA for California): ").lower()
country="us"
option=input("DO you want the dataset for today or tomorrow (Enter 0 for today; 1 or tomorrow): ")
if option=="0": 
    day="today"
elif option=="1":
    day="tomorrow"
else:
    print("Error: you had to enter 0 for today or 1 or tomorrow. To continue, run the program again")
    sys.exit()
# Running the scraper
events = scrape_meetup_events(city, state, country, day)

# Creating a DataFrame with the correct column order
df = pd.DataFrame(events, columns=["event_name", "organizer", "attendees", "event_date_time", "venue_name", "venue_address", "cost_of_attendance", "event_url", "price_level", "rating","first_review" ])



# Printing the DataFrame
print(df.head(20))

# Saving the DataFrame to a CSV file
df.to_csv('meetup_events.csv', index=False)
if len(df)==0:
    print("Sorry, no events found in 2 mile radius of your entered location for", day)
else:
    print(f"\nTotal number of events scraped: {len(df)}")

