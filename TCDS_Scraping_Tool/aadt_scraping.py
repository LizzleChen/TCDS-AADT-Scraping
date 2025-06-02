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
from datetime import datetime, timedelta

class BatchScrapper:

    def __init__(self, 
                 batch_size: int = 50,
                 delay_between_requests: tuple = (2, 5),
                 delay_between_batches: tuple = (300, 600), 
                 max_retries: int = 3,
                 progress_file: str = "scraping_progress.json"):
        
        self.batch_size = batch_size
        self.delay_between_requests = delay_between_requests
        self.delay_between_batches = delay_between_batches
        self.max_retries = max_retries
        self.progress_file = progress_file
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('scraping.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Load or initialize progress
        self.progress = self.load_progress()

    def load_progress(self) -> dict:
        """Load scraping progress from file"""
        if os.path.exists(self.progress_file):
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {
            'completed_ids': [],
            'failed_ids': [],
            'last_batch': 0,
            'total_processed': 0
        }
    
    def save_progress(self):
        """Save current progress to file"""
        with open(self.progress_file, 'w') as f:
            json.dump(self.progress, f, indent=2)
    
    def read_ids_from_file(self, file_path: str) -> List[str]:
        """Read all ids from the input file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return [id.strip() for id in f if id.strip()]
    
    def get_pending_ids(self, all_ids: List[str]) -> List[str]:
        """Get ids that haven't been processed yet"""
        completed = set(self.progress['completed_ids'])
        return [id for id in all_ids if id not in completed]
    
    def create_batches(self, ids: List[str]) -> List[List[str]]:
        """Divide lines into batches"""
        batches = []
        for i in range(0, len(ids), self.batch_size):
            batches.append(ids[i:i + self.batch_size])
        return batches
    
    def open_tcds_detail_page(self, id: str):
        """
        Setup the the chromedriver and open the TCDS detail page.
        Args:
            id: station ID
        """
        global driver
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')  
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        ]
        options.add_argument(f'--user-agent={random.choice(user_agents)}')

        driver = webdriver.Chrome()
        driver.get(
            f'https://txdot.public.ms2soft.com/tcds/set_session.asp?ext=y&loc=txdot&LOCAL_ID={id}'
            )
        #Sleep for at least 8 seconds in case the AADT table doesn't load 
        time.sleep(random.randint(8,10)) 

        return

    def check_dir(self):
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

    def click_dir_button(self, dir: str, timeout = 20):
        global driver
        xpath = f"//div[@id='DIR_BUTTONS_DIV']//input[@value='{dir}']"
        print(f"Getting Direction {dir} direction")
        self.logger.info(f"Getting Direction {dir} direction")
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
            self.logger.info(f"Element with direction value of '{dir}' not found")
            return False
    
        return False


    def scrape_aadt_data(self, tablediv_xpath = ".//tr[@class='FormRowLabel']/following-sibling::tr", timeout=20):
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
                rows = WebDriverWait(driver,timeout).until(
                    EC.visibility_of_all_elements_located((By.XPATH, tablediv_xpath))
                    )
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
                    self.logger.info("Next page button not found, might be the only AADT page")
                    driver.quit()
                    return all_aadt
                
                except Exception as e:
                    print(f"Error occurred: {e}. Exporting AADT data fetched so far.")
                    self.logger.info(f"Error occurred: {e}. Exporting AADT data fetched so far.")
                    return all_aadt
                
                
            except TimeoutException as e:
                print("Timeout waiting for elements")
                self.logger.info("Timeout waiting for elements. ")
                break
            except Exception as e:
                print(f"Error occurred: {e}")
                self.logger.info(f"Error occurred: {e}")
                break
        
        return all_aadt

    def process_batch(self, batch: List[str], batch_num: int) -> dict:
        self.logger.info(f"Starting batch {batch_num + 1} with {len(batch)} IDs")

        batch_results = {
            'batch_number': batch_num + 1,
            'successful': [],
            'failed': [],
            'start_time': datetime.now().isoformat()
        }

        try:
            for i, id in enumerate(batch):
                if id in self.progress['completed_ids']:
                    self.logger.info(f"Skipping already completed ID: {id}")
                    batch_results['successful'].append(id)
                    continue

                single_id_result = self.process_single_id(id)

                if single_id_result:
                        self.progress['completed_ids'].append(id)
                        batch_results['successful'].append(id)
                        self.logger.info(f"Completed {i+1}/{len(batch)}: {id}")
                else:
                        self.progress['failed_ids'].append(id)
                        batch_results['failed'].append(id)
                        self.logger.error(f"Failed to retrieve ID:{id}")

                # Random delay between requests (except for last item in batch)
                if i < len(batch) - 1:
                    delay = random.uniform(*self.delay_between_requests)
                    self.logger.debug(f"Waiting {delay:.1f} seconds before next request")
                    time.sleep(delay)

        except Exception as e:
            self.logger.error(f"Critical error in batch {batch_num + 1}: {str(e)}")

        
        batch_results['end_time'] = datetime.now().isoformat()
        self.progress['total_processed'] += len(batch)
        self.progress['last_batch'] = batch_num
        self.save_progress()

        # Save batch results
        batch_file = f"batch_{batch_num + 1}_results.json"
        with open(batch_file, 'w') as f:
            json.dump(batch_results, f, indent=2)

        return batch_results

    def process_file_in_batches(self, file_path, start_batch: int = 0):
        self.logger.info(f"Starting batch processing from file: {file_path}")

        # Read all IDs
        all_ids = self.read_ids_from_file(file_path)
        self.logger.info(f"Total IDs in file: {len(all_ids)}")

        # Get pending IDs
        pending_ids = self.get_pending_ids(all_ids)
        self.logger.info(f"Pending IDs to process: {len(pending_ids)}")

        if not pending_ids:
            self.logger.info("No pending IDs to process!")
            return
        
        # Create batches
        batches = self.create_batches(pending_ids)
        total_batches = len(batches)
        self.logger.info(f"Created {total_batches} batches of size {self.batch_size}")

        # Process each batch
        for batch_num, batch in enumerate(batches[start_batch:], start=start_batch):
            try:
                self.logger.info(f"Processing batch {batch_num + 1}/{total_batches}")
                
                batch_results = self.process_batch(batch, batch_num)
                
                # Log batch summary
                successful = len(batch_results['successful'])
                failed = len(batch_results['failed'])
                self.logger.info(f"Batch {batch_num + 1} completed: {successful} successful, {failed} failed")
                
                # Delay between batches (except for the last batch)
                if batch_num < total_batches - 1:
                    delay = random.uniform(*self.delay_between_batches)
                    next_time = datetime.now() + timedelta(seconds=delay)
                    self.logger.info(f"Waiting {delay/60:.1f} minutes until next batch (resume at {next_time.strftime('%H:%M:%S')})")
                    time.sleep(delay)
                
            except KeyboardInterrupt:
                self.logger.info("Batch processing interrupted by user. Progress saved.")
                break
            except Exception as e:
                self.logger.error(f"Error in batch {batch_num + 1}: {str(e)}")
                continue
        
        self.logger.info("Batch processing completed!")

    def export_to_csv(self, id, aadt):
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

    def append_to_json(self, id, filename, aadt):
        data = {}
        if os.path.exists(filename):
            with open(filename, 'a') as f:
                f.write('\n' + json.dumps({"id": id, "aadt": aadt}))
        else:
            # Create new file if json file doesn't exists
            with open(filename, 'w') as f:
                json.dump({"id": id, "aadt": aadt}, f)
        self.logger.info(f'Station {id} added to json file.')

    def process_single_id(self, id: str) -> None:
        """
        Process a single TCDS ID
        Args:
            id: The TCDS identifier
            output_file: Path to the output CSV file
        """
        global driver

        print(f"Processing ID: {id}")
        self.logger.info(f"Processing ID: {id}")

        self.open_tcds_detail_page(id)
        aadt = self.scrape_aadt_data()
        if aadt:
            self.append_to_json(id, "output.json", aadt)
        else:
            self.logger.info(f"Failed to retrieve ID:{id}")
            return False
        directions = self.check_dir()
        if directions:
            for dir in directions:
                #click direction function
                if self.click_dir_button(dir):
                    aadt = self.scrape_aadt_data()
                    self.append_to_json(id+"_"+dir, "output.json", aadt)
                else:
                    self.logger.info(f"Failed to retrieve Station {id} directional information")
                    return False

        # export_to_csv(id, aadt)
        driver.quit()
        return True

    def read_ids_from_file(self, file_path: str) -> List[str]:
        """
        Read TCDS IDs from a file
        Args:
            file_path: Path to the input file
        Returns:
            List of TCDS IDs
        """
        with open(file_path, 'r') as f:
            return [line.strip() for line in f if line.strip()]

    def main(self):

        parser = argparse.ArgumentParser(description='TCDS Data Scraper')
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('-i', '--id', help='Single TCDS ID to process')
        group.add_argument('-f', '--file', help='File containing list of TCDS IDs')
        parser.add_argument('--batch-size', type=int, default=50, help='Number of IDs per batch (default: 50)')
        
        # Parse arguments
        args = parser.parse_args()

        # Update instance variables based on arguments
        self.batch_size = args.batch_size
        # self.delay_between_requests = (args.min_delay, args.max_delay)
        # self.delay_between_batches = (args.batch_delay_min, args.batch_delay_max)
        # self.max_retries = args.max_retries

        
        # Process based on input type
        if args.id:
            self.process_single_id(args.id)
        else:
            self.process_file_in_batches(args.file,0)
            # ids = self.read_ids_from_file(args.file)
            # print(f"Found {len(ids)} IDs to process")
            # self.logger.info(f"Found {len(ids)} IDs to process")
            # for id in ids:
            #     self.process_single_id(id)
        

if __name__ == "__main__":
    scraper = BatchScrapper()
    scraper.main()