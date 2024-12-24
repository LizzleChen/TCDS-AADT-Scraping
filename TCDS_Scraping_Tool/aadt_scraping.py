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

def open_tcds_detail_page(id):
    global driver
    options = webdriver.ChromeOptions()
    options.browser_version = 'stable'
    options.capabilities['browserVersion'] = 'stable'
    driver = webdriver.Chrome()
    driver.get(
        f'https://txdot.public.ms2soft.com/tcds/set_session.asp?ext=y&loc=txdot&LOCAL_ID={id}&MASTER_LOCAL_ID={id}'
        )
    return

def scrape_aadt_data(tablediv_xpath = ".//tr[@class='FormRowLabel']/following-sibling::tr", timeout=10):
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
    # Create a DataFrame from the extracted data and save as a csv file
    df = pd.DataFrame(aadt).sort_values(by="year").reset_index(drop=True)
    df.to_csv(f'historical_aadt_{id}.csv', index=False)  
    print('Data saved as csv file')

def main():
    id = "43H1A"
    open_tcds_detail_page(id)
    aadt = scrape_aadt_data()
    export_to_csv(id, aadt)
    

if __name__ == "__main__":
    main()