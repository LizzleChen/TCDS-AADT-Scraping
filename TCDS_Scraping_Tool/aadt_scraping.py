from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
import time
import random
import re
import pandas as pd
import argparse
import csv
from typing import List, Dict
from pathlib import Path

def open_tcds_detail_page(id):
    """
    Setup the the chromedriver and open the TCDS detail page.
    Args:
        id: station ID
    """
    global driver
    options = webdriver.ChromeOptions()
    options.browser_version = 'stable'
    options.capabilities['browserVersion'] = 'stable'
    driver = webdriver.Chrome()
    driver.get(
        f'https://txdot.public.ms2soft.com/tcds/set_session.asp?ext=y&loc=txdot&LOCAL_ID={id}&MASTER_LOCAL_ID={id}'
        )
    return

def scrape_aadt_data(tablediv_xpath = ".//tr[@class='FormRowLabel']/following-sibling::tr", timeout=20):
    """
    Extract AADT data page by page and export the AADT data to a CSV file
    Returns:
        Dictionary containing the scraped AADT data [{year: aadt}, ...]
    """
    
    global driver
    all_aadt = []
    
    while True:
        try:
            time.sleep(random.randint(3,5)) #have to wait a few seconds before selenium be able to use the same element after page changes.
            # Wait for table to be present and visible
            table_div = WebDriverWait(driver, timeout).until(
                EC.visibility_of_element_located((By.ID, "TCDS_TDETAIL_AADT_DIV"))
            )
            
            # Get the data from current page
            rows = table_div.find_elements(By.XPATH, tablediv_xpath)
            for row in rows:
                cells = row.find_elements(By.CLASS_NAME, "FormRow")
                if len(cells) >= 3:
                    all_aadt.append({
                        'year': cells[1].get_attribute('innerHTML'),
                        'aadt': re.sub(r'<sup>.*?</sup>', '', cells[2].get_attribute('innerHTML'))
                    })
            
            # Find and click next button
            button = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, '//div[@id="TCDS_TDETAIL_AADT_DIV"]//input[@type="button" and @value=">" and @name="a_first"]'))
            )
            
            if not button.is_enabled():
                print("Reached last page")
                break
                
            button.click()
            
            
        except TimeoutException as e:
            print("Timeout waiting for elements")
            break
        except Exception as e:
            print(f"Error occurred: {e}")
            break

    driver.quit()
    
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

def process_single_id(id: str) -> None:
    """
    Process a single TCDS ID
    Args:
        id: The TCDS identifier
        output_file: Path to the output CSV file
    """
    print(f"Processing ID: {id}")
    open_tcds_detail_page(id)
    aadt = scrape_aadt_data()
    export_to_csv(id, aadt)

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
        for id in ids:
            process_single_id(id)
    

if __name__ == "__main__":
    main()