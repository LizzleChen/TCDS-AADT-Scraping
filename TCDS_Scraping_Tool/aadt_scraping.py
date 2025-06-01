from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, NoSuchElementException
import time
import random
import re
import pandas as pd
import argparse
import csv
from typing import List, Dict
from pathlib import Path
import os
import json
import logging

logging.basicConfig(
    filename='scraper.log',
    level=logging.INFO,
    format='%(asctime)s - %(funcName)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def open_tcds_detail_page(id):
    """
    Setup the the chromedriver and open the TCDS detail page.
    Args:
        id: station ID
    """
    global driver
    options = webdriver.ChromeOptions()
    # options.browser_version = 'stable'
    # options.capabilities['browserVersion'] = 'stable'
    driver = webdriver.Chrome()
    driver.get(
        f'https://txdot.public.ms2soft.com/tcds/set_session.asp?ext=y&loc=txdot&LOCAL_ID={id}'
        )
    #Sleep for at least 8 seconds in case the AADT table doesn't load 
    time.sleep(random.randint(8,10)) 

    return

def check_dir():
    """
    Check if there are multiple directions in AADT page. 
    If it is only two-way, proceed with just one scraping process.
    If there are different directions, after finishing the two-way, scrape each direction. 

    Returns: 
        A list of available directions ["NB", "SB"] or None for "two-way" only
    """

    # One-way or Two-way X-Path: //*[@id="DIR_BUTTONS_DIV"]/span/div[2]/input
    global driver
    input_elements = driver.find_elements(By.XPATH, "//div[@id='DIR_BUTTONS_DIV']//input")
    values = [element.get_attribute('value') for element in input_elements if element.get_attribute('value') in ["NB", "SB", "EB", "WB"]]
    return values

def click_dir_button(dir: str, timeout = 20):
    global driver
    xpath = f"//div[@id='DIR_BUTTONS_DIV']//input[@value='{dir}']"
    print(f"Getting Direction {dir} direction")
    logger.info(f"Getting Direction {dir} direction")
    try:
        element = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xpath)))
        element.click()

        time.sleep(2)

        # Check if that direction button is click by checking onClick is "javascript:void(0)" - if so, exit
        element = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.XPATH, xpath))) #Webpage will refresh, so we will re-locate the element
        onclick_value = element.get_attribute('onclick')
        if onclick_value == "javascript:void(0)":
            print(f"'{dir}' has been clicked")
            return True
    
    except NoSuchElementException:
        print(f"Element with direction value of '{dir}' not found")
        logger.info(f"Element with direction value of '{dir}' not found")
        return False
    
    return False


def scrape_aadt_data(tablediv_xpath = ".//tr[@class='FormRowLabel']/following-sibling::tr", timeout=20):
    """
    Extract AADT data page by page and export the AADT data to a CSV file
    Returns:
        Dictionary containing the scraped AADT data [{year: aadt}, ...]
    """
    
    global driver
    all_aadt = []

    #Create check set to check for repetitive years. Sometimes the website is slow responding to next page button click, and we will get duplicated years in our outputs. 
    seen_year = set()
    
    while True:
        try:
            # Wait for table to be present and visible
            table_div = WebDriverWait(driver, timeout).until(
                EC.visibility_of_element_located((By.ID, "TCDS_TDETAIL_AADT_DIV"))
            )
            
            #have to wait a few seconds before selenium be able to use the same element after page changes.
            time.sleep(random.randrange(5,6)) 



            # Get the data from current page
            rows = table_div.find_elements(By.XPATH, tablediv_xpath)
            for row in rows:
                cells = row.find_elements(By.CLASS_NAME, "FormRow")
                if len(cells) >= 3:
                    year = cells[1].get_attribute('innerHTML')
                    aadt = re.sub(r'<sup>.*?</sup>', '', cells[2].get_attribute('innerHTML'))

                    if year not in seen_year:
                        seen_year.add(year)
                        all_aadt.append({
                            'year': year,
                            'aadt': aadt
                        })
            
            # Find and click next button
            try:
                button = WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.XPATH, '//div[@id="TCDS_TDETAIL_AADT_DIV"]//input[@type="button" and @value=">" and @name="a_first"]'))
                )
                
                if not button.is_enabled():
                    print("Reached last page")
                    break
                    
                button.click()

            except TimeoutException as e:
                print("Next page button not found, might be the only AADT page")
                logger.info("Next page button not found, might be the only AADT page")
                return all_aadt
            
            except Exception as e:
                print(f"Error occurred: {e}. Exporting AADT data fetched so far.")
                logger.info(f"Error occurred: {e}. Exporting AADT data fetched so far.")
                return all_aadt
            
            
        except TimeoutException as e:
            print("Timeout waiting for elements")
            logger.info("Timeout waiting for elements. ")
            break
        except Exception as e:
            print(f"Error occurred: {e}")
            logger.info(f"Error occurred: {e}")
            break
    
    return all_aadt

def export_to_csv(id, aadt):
    """
    Exports the AADT data to a CSV file
    Args:
        id: The TCDS identifier
        data: Dictionary containing the AADT data
    Output:
        AADT in csv format
    """
    # Create a DataFrame from the extracted data and save as a csv file
    df = pd.DataFrame(aadt).sort_values(by="year").reset_index(drop=True)
    df.to_csv(f'historical_aadt_{id}.csv', index=False)  
    print('Data saved as csv file')

def append_to_json(id, filename, aadt):
    data = {}
    if os.path.exists(filename):
        with open(filename, 'a') as f:
            f.write('\n' + json.dumps({"id": id, "aadt": aadt}))
    else:
        # Create new file if json file doesn't exists
        with open(filename, 'w') as f:
            json.dump({"id": id, "aadt": aadt}, f)
    logger.info(f'Station {id} added to json file.')

def process_single_id(id: str) -> None:
    """
    Process a single TCDS ID
    Args:
        id: The TCDS identifier
        output_file: Path to the output CSV file
    """
    global driver

    print(f"Processing ID: {id}")
    logger.info(f"Processing ID: {id}")

    open_tcds_detail_page(id)
    aadt = scrape_aadt_data()
    append_to_json(id, "output.json", aadt)
    directions = check_dir()
    if directions:
        for dir in directions:
            #click direction function
            if click_dir_button(dir):
                aadt = scrape_aadt_data()
                append_to_json(id+"_"+dir, "output.json", aadt)
            else:
                print(f"Failed to retrieve Station {id} directional information")

    # export_to_csv(id, aadt)
    driver.quit()

def read_ids_from_file(file_path: str) -> List[str]:
    """
    Read TCDS IDs from a file
    Args:
        file_path: Path to the input file
    Returns:
        List of TCDS IDs
    """
    with open(file_path, 'r') as f:
        return [line.strip() for line in f if line.strip()]

def main():

    parser = argparse.ArgumentParser(description='TCDS Data Scraper')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-i', '--id', help='Single TCDS ID to process')
    group.add_argument('-f', '--file', help='File containing list of TCDS IDs')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Process based on input type
    if args.id:
        process_single_id(args.id)
    else:
        ids = read_ids_from_file(args.file)
        print(f"Found {len(ids)} IDs to process")
        logger.info(f"Found {len(ids)} IDs to process")
        for id in ids:
            process_single_id(id)
    

if __name__ == "__main__":
    main()